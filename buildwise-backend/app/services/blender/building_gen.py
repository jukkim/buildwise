"""BPS → Blender 3D building generation.

Converts a BPS (Building Performance Specification) JSON into either:
  - A single BMesh Python script for high-quality rendering (execute_code)
  - Legacy command dicts for simple/fallback mode
"""

from __future__ import annotations

import math
import textwrap
from typing import Any

_ASPECT_RATIOS: dict[str, float] = {
    "large_office": 1.5,
    "medium_office": 1.5,
    "small_office": 1.5,
    "standalone_retail": 2.0,
    "primary_school": 2.5,
    "hospital": 1.8,
}

_FLOOR_HEIGHTS: dict[str, float] = {
    "large_office": 3.96,
    "medium_office": 3.96,
    "small_office": 3.05,
    "standalone_retail": 6.1,
    "primary_school": 4.0,
    "hospital": 3.96,
}

_MATERIALS: dict[str, dict[str, Any]] = {
    "large_office": {
        "wall_color": (0.65, 0.72, 0.78, 1.0),
        "name": "Glass_Curtainwall",
        "roughness": 0.3,
    },
    "medium_office": {
        "wall_color": (0.55, 0.55, 0.60, 1.0),
        "name": "Metal_Panel",
        "roughness": 0.5,
    },
    "small_office": {
        "wall_color": (0.82, 0.78, 0.72, 1.0),
        "name": "Brick_Facade",
        "roughness": 0.8,
    },
    "standalone_retail": {
        "wall_color": (0.85, 0.85, 0.82, 1.0),
        "name": "Precast_Concrete",
        "roughness": 0.7,
    },
    "primary_school": {
        "wall_color": (0.80, 0.70, 0.55, 1.0),
        "name": "Brick_School",
        "roughness": 0.75,
    },
    "hospital": {
        "wall_color": (0.88, 0.88, 0.86, 1.0),
        "name": "White_Panel",
        "roughness": 0.7,
    },
}


def _extract_params(bps: dict) -> dict:
    """Extract and validate building parameters from BPS."""
    building = bps.get("building", {})
    envelope = bps.get("envelope", {})

    building_type: str = building.get("building_type", "large_office")
    floors: int = max(building.get("floors", 1), 1)
    total_area: float = max(building.get("floor_area_m2", 5000), 1.0)
    wwr: float = max(0.0, min(envelope.get("wwr", 0.4), 1.0))
    floor_height: float = building.get(
        "floor_height_m", _FLOOR_HEIGHTS.get(building_type, 3.5)
    )

    per_floor_area = total_area / floors
    aspect = _ASPECT_RATIOS.get(building_type, 1.5)
    width = math.sqrt(per_floor_area / aspect)
    length = per_floor_area / width

    return {
        "building_type": building_type,
        "floors": floors,
        "total_area": total_area,
        "wwr": wwr,
        "floor_height": floor_height,
        "per_floor_area": per_floor_area,
        "width": width,
        "length": length,
    }


def bps_to_bmesh_script(bps: dict) -> str:
    """Generate a BMesh-based Python script for Blender execute_code.

    Produces a single mesh building with:
      - Extruded box with floor-level bisect planes
      - Glass window planes flush with walls
      - PBR materials (wall + glass + roof)
      - Floor reveal strips, ground plane
      - Sun + area lighting, sky world, camera
    """
    p = _extract_params(bps)
    mat_info = _MATERIALS.get(p["building_type"], _MATERIALS["large_office"])

    return textwrap.dedent(f"""\
        import bpy, bmesh, math

        # ── Clear ─────────────────────────────────────
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for m in list(bpy.data.materials):
            bpy.data.materials.remove(m)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh)

        # ── Parameters ────────────────────────────────
        FLOORS = {p['floors']}
        FH = {p['floor_height']:.4f}
        LENGTH = {p['length']:.4f}
        WIDTH = {p['width']:.4f}
        WWR = {p['wwr']:.4f}
        TOTAL_H = FLOORS * FH
        HX = LENGTH / 2
        HY = WIDTH / 2
        WIN_H = FH * WWR
        WIN_SILL = (FH - WIN_H) / 2

        # ── Materials ─────────────────────────────────
        def make_wall_mat():
            mat = bpy.data.materials.new("{mat_info['name']}")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = {mat_info['wall_color']}
            bsdf.inputs['Roughness'].default_value = {mat_info['roughness']}
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 50.0
            noise.inputs['Detail'].default_value = 8.0
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.12
            links.new(noise.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_glass_mat():
            mat = bpy.data.materials.new("Glass_Window")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.6, 0.75, 0.85, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.05
            if 'Transmission Weight' in bsdf.inputs:
                bsdf.inputs['Transmission Weight'].default_value = 0.8
            elif 'Transmission' in bsdf.inputs:
                bsdf.inputs['Transmission'].default_value = 0.8
            bsdf.inputs['IOR'].default_value = 1.45
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_roof_mat():
            mat = bpy.data.materials.new("Roof_Surface")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.4, 0.42, 0.45, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.85
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        wall_mat = make_wall_mat()
        glass_mat = make_glass_mat()
        roof_mat = make_roof_mat()

        # ── Building body (single BMesh) ──────────────
        mesh = bpy.data.meshes.new("Building_Mesh")
        obj = bpy.data.objects.new("{p['building_type']}", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= LENGTH
            v.co.y *= WIDTH
            v.co.z *= TOTAL_H
            v.co.z += TOTAL_H / 2

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for i in range(1, FLOORS):
            z = i * FH
            bmesh.ops.bisect_plane(
                bm,
                geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                plane_co=(0, 0, z),
                plane_no=(0, 0, 1),
            )

        bm.to_mesh(mesh)
        bm.free()
        obj.data.materials.append(wall_mat)

        # ── Windows (thin glass cubes protruding from walls) ──
        WIN_THICK = 0.03
        for i in range(FLOORS):
            z = i * FH + WIN_SILL + WIN_H / 2
            wl = LENGTH * 0.9
            ww = WIDTH * 0.9
            for name_suffix, cx, cy, sx, sy, sz in [
                ("N", 0, HY + WIN_THICK, wl/2, WIN_THICK, WIN_H/2),
                ("S", 0, -HY - WIN_THICK, wl/2, WIN_THICK, WIN_H/2),
                ("E", HX + WIN_THICK, 0, WIN_THICK, ww/2, WIN_H/2),
                ("W", -HX - WIN_THICK, 0, WIN_THICK, ww/2, WIN_H/2),
            ]:
                bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, z))
                win = bpy.context.active_object
                win.name = f"Win_F{{i+1}}_{{name_suffix}}"
                win.scale = (sx, sy, sz)
                win.data.materials.append(glass_mat)

        # ── Roof slab ─────────────────────────────────
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H + 0.15))
        roof = bpy.context.active_object
        roof.name = "Roof"
        roof.scale = (HX + 0.5, HY + 0.5, 0.15)
        roof.data.materials.append(roof_mat)

        # ── Floor reveals ─────────────────────────────
        reveal_mat = bpy.data.materials.new("Floor_Reveal")
        reveal_mat.use_nodes = True
        reveal_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)
        for i in range(1, FLOORS):
            z = i * FH
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
            r = bpy.context.active_object
            r.name = f"FloorReveal_{{i}}"
            r.scale = (HX + 0.05, HY + 0.05, 0.02)
            r.data.materials.append(reveal_mat)

        # ── Ground ────────────────────────────────────
        bpy.ops.mesh.primitive_plane_add(size=max(LENGTH, WIDTH) * 3, location=(0, 0, -0.01))
        gnd = bpy.context.active_object
        gnd.name = "Ground"
        gnd_mat = bpy.data.materials.new("Ground")
        gnd_mat.use_nodes = True
        gnd_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.35, 0.38, 0.32, 1.0)
        gnd_mat.node_tree.nodes["Principled BSDF"].inputs['Roughness'].default_value = 0.9
        gnd.data.materials.append(gnd_mat)

        # ── Lighting ──────────────────────────────────
        bpy.ops.object.light_add(type='SUN', location=(20, -20, 50))
        sun = bpy.context.active_object
        sun.name = "Sun"
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))

        bpy.ops.object.light_add(type='AREA', location=(-30, 30, 40))
        fill = bpy.context.active_object
        fill.name = "Fill_Light"
        fill.data.energy = 500
        fill.data.size = 20

        # ── World (sky) ───────────────────────────────
        world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
        bpy.context.scene.world = world
        world.use_nodes = True
        wn = world.node_tree.nodes
        wl = world.node_tree.links
        wn.clear()
        bg = wn.new('ShaderNodeBackground')
        bg.inputs['Color'].default_value = (0.53, 0.68, 0.85, 1.0)
        bg.inputs['Strength'].default_value = 0.8
        wo = wn.new('ShaderNodeOutputWorld')
        wl.new(bg.outputs['Background'], wo.inputs['Surface'])

        # ── Camera ────────────────────────────────────
        bpy.ops.object.camera_add(
            location=(LENGTH * 1.2, -WIDTH * 1.0, TOTAL_H * 0.8)
        )
        cam = bpy.context.active_object
        cam.name = "BuildingCam"
        from mathutils import Vector
        direction = Vector((0, 0, TOTAL_H * 0.4)) - cam.location
        rot = direction.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot.to_euler()
        cam.data.lens = 35
        bpy.context.scene.camera = cam

        # ── Render settings ───────────────────────────
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = 64
        bpy.context.scene.render.resolution_x = 1920
        bpy.context.scene.render.resolution_y = 1080

        obj_count = len(bpy.data.objects)
        print(
            f"{{'{p['building_type']}'}} generated: "
            f"{{obj_count}} objects, {{FLOORS}} floors, "
            f"{{LENGTH:.1f}}x{{WIDTH:.1f}}m"
        )
    """)


def bps_to_blender_commands(bps: dict) -> list[dict]:
    """Convert a BPS dict to a list of Blender MCP commands.

    Legacy mode: returns command dicts for per-command execution.
    Prefer bps_to_bmesh_script() for better visual quality.
    """
    p = _extract_params(bps)
    mat_info = _MATERIALS.get(p["building_type"], _MATERIALS["large_office"])

    commands: list[dict] = []

    commands.append({"type": "execute_script", "params": {"script": _CLEAR_SCRIPT}})

    for i in range(p["floors"]):
        z = i * p["floor_height"] + p["floor_height"] / 2
        commands.append(
            {
                "type": "create_object",
                "params": {
                    "type": "cube",
                    "name": f"Floor_{i + 1}",
                    "location": [0, 0, z],
                    "scale": [
                        p["length"] / 2,
                        p["width"] / 2,
                        p["floor_height"] / 2,
                    ],
                },
            }
        )

    window_height = p["floor_height"] * p["wwr"]
    for i in range(p["floors"]):
        z = i * p["floor_height"] + p["floor_height"] / 2
        for sign, direction in [(1, "N"), (-1, "S")]:
            commands.append(
                {
                    "type": "create_object",
                    "params": {
                        "type": "cube",
                        "name": f"Win_F{i + 1}_{direction}",
                        "location": [0, sign * (p["width"] / 2 + 0.01), z],
                        "scale": [p["length"] / 2 * 0.95, 0.02, window_height / 2],
                    },
                }
            )
        for sign, direction in [(1, "E"), (-1, "W")]:
            commands.append(
                {
                    "type": "create_object",
                    "params": {
                        "type": "cube",
                        "name": f"Win_F{i + 1}_{direction}",
                        "location": [sign * (p["length"] / 2 + 0.01), 0, z],
                        "scale": [0.02, p["width"] / 2 * 0.95, window_height / 2],
                    },
                }
            )

    roof_z = p["floors"] * p["floor_height"] + 0.1
    commands.append(
        {
            "type": "create_object",
            "params": {
                "type": "cube",
                "name": "Roof",
                "location": [0, 0, roof_z],
                "scale": [
                    p["length"] / 2 + 0.2,
                    p["width"] / 2 + 0.2,
                    0.1,
                ],
            },
        }
    )

    for i in range(p["floors"]):
        commands.append(
            {
                "type": "set_material",
                "params": {
                    "object": f"Floor_{i + 1}",
                    "material": mat_info["name"],
                    "color": list(mat_info["wall_color"][:3]),
                },
            }
        )

    commands.append(
        {
            "type": "execute_script",
            "params": {"script": _GLASS_MATERIAL_SCRIPT},
        }
    )

    return commands


def bps_to_zone_info(bps: dict) -> list[dict]:
    """Extract thermal zone definitions from BPS for IDF generation."""
    p = _extract_params(bps)
    perimeter_depth = 4.57

    zones: list[dict] = []

    for i in range(p["floors"]):
        if (
            p["building_type"] in ("large_office", "hospital")
            and p["per_floor_area"] > 1000
        ):
            core_length = max(p["length"] - 2 * perimeter_depth, 1)
            core_width = max(p["width"] - 2 * perimeter_depth, 1)
            core_area = core_length * core_width
            perim_area = (p["per_floor_area"] - core_area) / 4

            zones.append(
                {
                    "name": f"F{i + 1}_Core",
                    "floor": i + 1,
                    "area_m2": core_area,
                    "height_m": p["floor_height"],
                    "type": "core",
                }
            )
            for d in ("N", "S", "E", "W"):
                zones.append(
                    {
                        "name": f"F{i + 1}_{d}",
                        "floor": i + 1,
                        "area_m2": perim_area,
                        "height_m": p["floor_height"],
                        "type": "perimeter",
                        "direction": d,
                    }
                )
        else:
            zones.append(
                {
                    "name": f"F{i + 1}",
                    "floor": i + 1,
                    "area_m2": p["per_floor_area"],
                    "height_m": p["floor_height"],
                    "type": "single",
                }
            )

    return zones


_CLEAR_SCRIPT = """\
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
"""

_GLASS_MATERIAL_SCRIPT = """\
import bpy
mat = bpy.data.materials.new(name='Glass_Window')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.75, 0.85, 1.0)
    bsdf.inputs['Alpha'].default_value = 0.3
    bsdf.inputs['Roughness'].default_value = 0.05
mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None

for obj in bpy.data.objects:
    if obj.name.startswith('Win_'):
        obj.data.materials.clear()
        obj.data.materials.append(mat)
"""
