"""BPS → Blender 3D building generation commands.

Converts a BPS (Building Performance Specification) JSON into a sequence
of Blender MCP commands that create a parametric building model.
"""

from __future__ import annotations

import math
from typing import Any


# DOE Reference building typical aspect ratios (length / width)
_ASPECT_RATIOS: dict[str, float] = {
    "large_office": 1.5,
    "medium_office": 1.5,
    "small_office": 1.5,
    "standalone_retail": 2.0,
    "primary_school": 2.5,
    "hospital": 1.8,
}

# Default floor-to-floor heights (m)
_FLOOR_HEIGHTS: dict[str, float] = {
    "large_office": 3.96,
    "medium_office": 3.96,
    "small_office": 3.05,
    "standalone_retail": 6.1,
    "primary_school": 4.0,
    "hospital": 3.96,
}

# Materials per building type
_MATERIALS: dict[str, dict[str, Any]] = {
    "large_office": {"color": [0.65, 0.72, 0.78], "name": "Glass_Curtainwall"},
    "medium_office": {"color": [0.55, 0.55, 0.60], "name": "Metal_Panel"},
    "small_office": {"color": [0.82, 0.78, 0.72], "name": "Brick_Facade"},
    "standalone_retail": {"color": [0.85, 0.85, 0.82], "name": "Precast_Concrete"},
    "primary_school": {"color": [0.80, 0.70, 0.55], "name": "Brick_School"},
    "hospital": {"color": [0.90, 0.90, 0.88], "name": "White_Panel"},
}


def bps_to_blender_commands(bps: dict) -> list[dict]:
    """Convert a BPS dict to a list of Blender MCP commands.

    The commands create:
      1. Per-floor slabs (cubes) with correct area and height
      2. Window strips per floor face (based on WWR)
      3. A flat roof
      4. Materials
    """
    building = bps.get("building", {})
    envelope = bps.get("envelope", {})

    building_type: str = building.get("building_type", "large_office")
    floors: int = building.get("floors", 1)
    total_area: float = building.get("floor_area_m2", 5000)
    wwr: float = envelope.get("wwr", 0.4)
    floor_height: float = building.get(
        "floor_height_m", _FLOOR_HEIGHTS.get(building_type, 3.5)
    )

    per_floor_area = total_area / max(floors, 1)
    aspect = _ASPECT_RATIOS.get(building_type, 1.5)
    width = math.sqrt(per_floor_area / aspect)
    length = per_floor_area / width

    commands: list[dict] = []

    # -- clear scene --------------------------------------------------------
    commands.append({"type": "execute_script", "params": {"script": _CLEAR_SCRIPT}})

    # -- floor slabs --------------------------------------------------------
    for i in range(floors):
        z = i * floor_height + floor_height / 2
        commands.append(
            {
                "type": "create_object",
                "params": {
                    "type": "cube",
                    "name": f"Floor_{i + 1}",
                    "location": [0, 0, z],
                    "scale": [length / 2, width / 2, floor_height / 2],
                },
            }
        )

    # -- windows (per floor, 4 faces) --------------------------------------
    window_height = floor_height * wwr
    for i in range(floors):
        z = i * floor_height + floor_height / 2
        # N/S faces (along length)
        for sign, direction in [(1, "N"), (-1, "S")]:
            commands.append(
                {
                    "type": "create_object",
                    "params": {
                        "type": "cube",
                        "name": f"Win_F{i + 1}_{direction}",
                        "location": [0, sign * (width / 2 + 0.01), z],
                        "scale": [length / 2 * 0.95, 0.02, window_height / 2],
                    },
                }
            )
        # E/W faces (along width)
        for sign, direction in [(1, "E"), (-1, "W")]:
            commands.append(
                {
                    "type": "create_object",
                    "params": {
                        "type": "cube",
                        "name": f"Win_F{i + 1}_{direction}",
                        "location": [sign * (length / 2 + 0.01), 0, z],
                        "scale": [0.02, width / 2 * 0.95, window_height / 2],
                    },
                }
            )

    # -- roof ---------------------------------------------------------------
    roof_z = floors * floor_height + 0.1
    commands.append(
        {
            "type": "create_object",
            "params": {
                "type": "cube",
                "name": "Roof",
                "location": [0, 0, roof_z],
                "scale": [length / 2 + 0.2, width / 2 + 0.2, 0.1],
            },
        }
    )

    # -- materials ----------------------------------------------------------
    mat = _MATERIALS.get(building_type, _MATERIALS["large_office"])
    for i in range(floors):
        commands.append(
            {
                "type": "set_material",
                "params": {
                    "object": f"Floor_{i + 1}",
                    "material": mat["name"],
                    "color": mat["color"],
                },
            }
        )

    # glass material for windows
    commands.append(
        {
            "type": "execute_script",
            "params": {
                "script": _GLASS_MATERIAL_SCRIPT,
            },
        }
    )

    return commands


def bps_to_zone_info(bps: dict) -> list[dict]:
    """Extract thermal zone definitions from BPS for IDF generation.

    Returns a list of zone dicts: {name, floor, area_m2, height_m, perimeter}.
    Large offices get core + 4 perimeter zones per floor; others get 1 zone/floor.
    """
    building = bps.get("building", {})
    building_type: str = building.get("building_type", "large_office")
    floors: int = building.get("floors", 1)
    total_area: float = building.get("floor_area_m2", 5000)
    floor_height: float = building.get(
        "floor_height_m", _FLOOR_HEIGHTS.get(building_type, 3.5)
    )

    per_floor_area = total_area / max(floors, 1)
    aspect = _ASPECT_RATIOS.get(building_type, 1.5)
    width = math.sqrt(per_floor_area / aspect)
    length = per_floor_area / width
    perimeter_depth = 4.57  # DOE standard ~15 ft

    zones: list[dict] = []

    for i in range(floors):
        if building_type in ("large_office", "hospital") and per_floor_area > 1000:
            # core + 4 perimeter zones
            core_length = max(length - 2 * perimeter_depth, 1)
            core_width = max(width - 2 * perimeter_depth, 1)
            core_area = core_length * core_width
            perim_area = (per_floor_area - core_area) / 4

            zones.append(
                {
                    "name": f"F{i + 1}_Core",
                    "floor": i + 1,
                    "area_m2": core_area,
                    "height_m": floor_height,
                    "type": "core",
                }
            )
            for d in ("N", "S", "E", "W"):
                zones.append(
                    {
                        "name": f"F{i + 1}_{d}",
                        "floor": i + 1,
                        "area_m2": perim_area,
                        "height_m": floor_height,
                        "type": "perimeter",
                        "direction": d,
                    }
                )
        else:
            zones.append(
                {
                    "name": f"F{i + 1}",
                    "floor": i + 1,
                    "area_m2": per_floor_area,
                    "height_m": floor_height,
                    "type": "single",
                }
            )

    return zones


# -- Blender Python scripts sent via execute_script -------------------------

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
