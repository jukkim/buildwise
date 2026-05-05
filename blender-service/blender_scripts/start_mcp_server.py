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
    obj_type = params.get("type", "cube")
    name = params.get("name", "Object")
    location = params.get("location", [0, 0, 0])
    scale = params.get("scale", [1, 1, 1])

    if obj_type == "cube":
        bpy.ops.mesh.primitive_cube_add(size=2, location=location)
    elif obj_type == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=location)
    elif obj_type == "plane":
        bpy.ops.mesh.primitive_plane_add(size=2, location=location)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2, location=location)

    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale

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
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if fmt in ("gltf", "glb"):
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")
    else:
        return {"status": "error", "message": f"Unsupported format: {fmt}"}

    return {"status": "ok", "result": {"path": path}}


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


# Run server in a background thread so Blender's main loop stays alive
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# Keep Blender alive
logger.info("Blender MCP server started, waiting for connections...")
