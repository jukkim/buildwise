"""Start the MCP TCP server inside headless Blender.

This script runs inside Blender's Python environment.  It opens a TCP
socket on port 9876 and processes JSON commands from the BuildWise
backend.
"""

import bpy
import json
import logging
import math
import socket
import threading
import traceback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("blender-mcp")

HOST = "0.0.0.0"
PORT = 9876


def handle_command(data: dict) -> dict:
    """Dispatch a single MCP command and return the result."""
    cmd_type = data.get("type", "")
    params = data.get("params", {})

    try:
        if cmd_type == "create_object":
            return _create_object(params)
        elif cmd_type == "set_material":
            return _set_material(params)
        elif cmd_type == "execute_script":
            return _execute_script(params)
        elif cmd_type == "get_scene_info":
            return _get_scene_info()
        elif cmd_type == "export":
            return _export(params)
        elif cmd_type == "ping":
            return {"status": "ok", "result": "pong"}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
    except Exception as exc:
        logger.error("Command %s failed: %s", cmd_type, exc)
        return {"status": "error", "message": str(exc)}


def _create_object(params: dict) -> dict:
    import bmesh

    obj_type = params.get("type", "cube")
    name = params.get("name", "Object")
    location = params.get("location", [0, 0, 0])
    scale = params.get("scale", [1, 1, 1])

    mesh = bpy.data.meshes.new(name + "_mesh")
    bm = bmesh.new()

    if obj_type == "cube":
        bmesh.ops.create_cube(bm, size=2.0)
    elif obj_type == "cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False,
                              segments=32, radius1=1.0, radius2=1.0, depth=2.0)
    elif obj_type == "plane":
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    else:
        bmesh.ops.create_cube(bm, size=2.0)

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.scale = scale
    bpy.context.scene.collection.objects.link(obj)

    return {"status": "ok", "result": {"name": obj.name}}


def _set_material(params: dict) -> dict:
    obj_name = params.get("object", "")
    mat_name = params.get("material", "Material")
    color = params.get("color", [0.8, 0.8, 0.8])

    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        return {"status": "error", "message": f"Object '{obj_name}' not found"}

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)

    obj.data.materials.clear()
    obj.data.materials.append(mat)

    return {"status": "ok", "result": {"material": mat_name}}


def _execute_script(params: dict) -> dict:
    script = params.get("script", "")
    exec(compile(script, "<mcp-script>", "exec"), {"bpy": bpy, "math": math})
    return {"status": "ok"}


def _get_scene_info() -> dict:
    objects = []
    for obj in bpy.data.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
        })
    return {
        "status": "ok",
        "result": {
            "object_count": len(objects),
            "objects": objects,
        },
    }


def _export(params: dict) -> dict:
    fmt = params.get("format", "gltf")
    path = params.get("path", "/tmp/export/scene.glb")

    import os
    import struct

    os.makedirs(os.path.dirname(path), exist_ok=True)

    if fmt in ("gltf", "glb"):
        _export_glb_manual(path)
    elif fmt == "obj":
        _export_obj(path)
    else:
        return {"status": "error", "message": f"Unsupported format: {fmt}"}

    size = os.path.getsize(path) if os.path.exists(path) else 0
    return {"status": "ok", "result": {"path": path, "size_bytes": size}}


def _export_glb_manual(path: str) -> None:
    """Export scene to GLB without bpy.ops (works in background mode)."""
    import struct

    scene = bpy.context.scene
    meshes_data = []

    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()

        verts = []
        for v in mesh.vertices:
            co = obj.matrix_world @ v.co
            verts.extend([co.x, co.y, co.z])

        indices = []
        for tri in mesh.loop_triangles:
            indices.extend(tri.vertices)

        if verts and indices:
            meshes_data.append({"name": obj.name, "verts": verts, "indices": indices})

    # Build minimal glTF JSON + binary buffer
    import json as json_mod

    all_verts = []
    all_indices = []
    accessors = []
    buffer_views = []
    meshes_gltf = []
    nodes = []
    byte_offset = 0

    for i, md in enumerate(meshes_data):
        v_data = struct.pack(f"<{len(md['verts'])}f", *md["verts"])
        i_data = struct.pack(f"<{len(md['indices'])}I", *md["indices"])

        # Buffer view for vertices
        buffer_views.append({
            "buffer": 0, "byteOffset": byte_offset,
            "byteLength": len(v_data), "target": 34962
        })
        v_bv_idx = len(buffer_views) - 1
        byte_offset += len(v_data)

        # Buffer view for indices
        buffer_views.append({
            "buffer": 0, "byteOffset": byte_offset,
            "byteLength": len(i_data), "target": 34963
        })
        i_bv_idx = len(buffer_views) - 1
        byte_offset += len(i_data)

        # Compute min/max for vertices
        n_verts = len(md["verts"]) // 3
        xs = md["verts"][0::3]
        ys = md["verts"][1::3]
        zs = md["verts"][2::3]

        # Accessor for vertices
        accessors.append({
            "bufferView": v_bv_idx, "componentType": 5126,
            "count": n_verts, "type": "VEC3",
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)]
        })
        v_acc_idx = len(accessors) - 1

        # Accessor for indices
        accessors.append({
            "bufferView": i_bv_idx, "componentType": 5125,
            "count": len(md["indices"]), "type": "SCALAR",
            "min": [min(md["indices"])], "max": [max(md["indices"])]
        })
        i_acc_idx = len(accessors) - 1

        meshes_gltf.append({
            "name": md["name"],
            "primitives": [{"attributes": {"POSITION": v_acc_idx}, "indices": i_acc_idx}]
        })
        nodes.append({"name": md["name"], "mesh": i})

        all_verts.append(v_data)
        all_indices.append(i_data)

    bin_data = b"".join(all_verts) + b"".join(all_indices)
    # Recalculate with interleaved v/i per mesh
    bin_data = b""
    for md in meshes_data:
        bin_data += struct.pack(f"<{len(md['verts'])}f", *md["verts"])
        bin_data += struct.pack(f"<{len(md['indices'])}I", *md["indices"])

    # Pad to 4-byte boundary
    while len(bin_data) % 4 != 0:
        bin_data += b"\x00"

    gltf_json = {
        "asset": {"version": "2.0", "generator": "BuildWise-Blender-MCP"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes_gltf,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_data)}]
    }

    json_bytes = json_mod.dumps(gltf_json, separators=(",", ":")).encode()
    # Pad JSON to 4-byte boundary
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    # GLB structure: header + JSON chunk + BIN chunk
    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(bin_data), b"BIN\x00") + bin_data

    with open(path, "wb") as f:
        f.write(header + json_chunk + bin_chunk)


def _export_obj(path: str) -> None:
    """Simple OBJ export for fallback."""
    scene = bpy.context.scene
    with open(path, "w") as f:
        v_offset = 0
        for obj in scene.objects:
            if obj.type != "MESH":
                continue
            mesh = obj.data
            mesh.calc_loop_triangles()
            f.write(f"o {obj.name}\n")
            for v in mesh.vertices:
                co = obj.matrix_world @ v.co
                f.write(f"v {co.x:.6f} {co.y:.6f} {co.z:.6f}\n")
            for tri in mesh.loop_triangles:
                f.write(f"f {tri.vertices[0]+1+v_offset} {tri.vertices[1]+1+v_offset} {tri.vertices[2]+1+v_offset}\n")
            v_offset += len(mesh.vertices)


def client_handler(conn: socket.socket, addr: tuple) -> None:
    logger.info("Client connected: %s", addr)
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    command = json.loads(line.decode())
                except json.JSONDecodeError as exc:
                    response = {"status": "error", "message": f"Invalid JSON: {exc}"}
                else:
                    response = handle_command(command)
                conn.sendall(json.dumps(response, ensure_ascii=False).encode() + b"\n")
    except (ConnectionError, BrokenPipeError):
        pass
    finally:
        conn.close()
        logger.info("Client disconnected: %s", addr)


def start_server() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    logger.info("Blender MCP server listening on %s:%d", HOST, PORT)

    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=client_handler, args=(conn, addr), daemon=True)
        t.start()


# Run server on the main thread (blocks forever, keeps Blender alive)
logger.info("Blender MCP server starting, waiting for connections...")
start_server()
