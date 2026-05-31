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
        "wall_color": (0.45, 0.55, 0.70, 1.0),
        "name": "Glass_Curtainwall",
        "roughness": 0.25,
        "texture": "curtainwall",
    },
    "medium_office": {
        "wall_color": (0.30, 0.32, 0.38, 1.0),
        "name": "Metal_Panel",
        "roughness": 0.45,
        "texture": "metal_panel",
    },
    "small_office": {
        "wall_color": (0.72, 0.25, 0.12, 1.0),
        "name": "Brick_Facade",
        "roughness": 0.85,
        "texture": "brick",
        "mortar_color": (0.82, 0.78, 0.72, 1.0),
    },
    "standalone_retail": {
        "wall_color": (0.75, 0.68, 0.55, 1.0),
        "name": "Precast_Concrete",
        "roughness": 0.7,
        "texture": "concrete",
    },
    "primary_school": {
        "wall_color": (0.82, 0.35, 0.15, 1.0),
        "name": "Brick_School",
        "roughness": 0.80,
        "texture": "brick",
        "mortar_color": (0.85, 0.80, 0.72, 1.0),
    },
    "hospital": {
        "wall_color": (0.88, 0.91, 0.96, 1.0),
        "name": "White_Panel",
        "roughness": 0.25,
        "texture": "white_panel",
    },
}

_HAS_MECH_EQUIP = {"large_office", "hospital"}


def _extract_params(bps: dict) -> dict:
    """Extract and validate building parameters from BPS."""
    building = bps.get("building", {})
    envelope = bps.get("envelope", {})

    building_type: str = building.get("building_type", "large_office")
    floors: int = max(building.get("floors", 1), 1)
    total_area: float = max(building.get("floor_area_m2", 5000), 1.0)
    wwr: float = max(0.0, min(envelope.get("wwr", 0.4), 1.0))
    floor_height: float = building.get("floor_height_m", _FLOOR_HEIGHTS.get(building_type, 3.5))

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

    6-phase rendering pipeline:
      1. Per-building-type procedural wall textures
      2. Realistic glass (dark base + reflection, EEVEE compatible)
      3. Roof with parapet + membrane + mechanical equipment
      4. Ground zones (sidewalk/parking/landscaping)
      5. Nishita procedural sky + 3-point lighting
      6. Entrance canopy + mechanical penthouse
    """
    p = _extract_params(bps)
    btype = p["building_type"]
    mat_info = _MATERIALS.get(btype, _MATERIALS["large_office"])
    texture_type = mat_info.get("texture", "concrete")
    has_mech = btype in _HAS_MECH_EQUIP

    mortar_color = mat_info.get("mortar_color", (0.75, 0.73, 0.70, 1.0))

    return textwrap.dedent(f"""\
        import bpy, bmesh, math
        from mathutils import Vector

        # ── Clear ─────────────────────────────────────
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for m in list(bpy.data.materials):
            bpy.data.materials.remove(m)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh)

        # ── Parameters ────────────────────────────────
        FLOORS = {p["floors"]}
        FH = {p["floor_height"]:.4f}
        LENGTH = {p["length"]:.4f}
        WIDTH = {p["width"]:.4f}
        WWR = {p["wwr"]:.4f}
        TOTAL_H = FLOORS * FH
        HX = LENGTH / 2
        HY = WIDTH / 2
        WIN_H = FH * 0.6
        WIN_SILL = FH * 0.25

        # ══════════════════════════════════════════════
        # Phase 1 — Per-building-type wall material
        # ══════════════════════════════════════════════
        def make_wall_mat():
            mat = bpy.data.materials.new("{mat_info["name"]}")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Roughness'].default_value = {mat_info["roughness"]}
            tc = nodes.new('ShaderNodeTexCoord')
            mp = nodes.new('ShaderNodeMapping')
            mp.inputs['Scale'].default_value = (1, 1, 1)
            links.new(tc.outputs['Object'], mp.inputs['Vector'])
            tex_type = "{texture_type}"

            if tex_type == "brick":
                brick = nodes.new('ShaderNodeTexBrick')
                brick.inputs['Color1'].default_value = {mat_info["wall_color"]}
                brick.inputs['Color2'].default_value = {mortar_color}
                brick.inputs['Mortar Size'].default_value = 0.015
                brick.inputs['Scale'].default_value = 12.0
                brick.offset = 0.5
                links.new(mp.outputs['Vector'], brick.inputs['Vector'])
                links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.25
                links.new(brick.outputs['Fac'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            elif tex_type == "metal_panel":
                bsdf.inputs['Base Color'].default_value = {mat_info["wall_color"]}
                bsdf.inputs['Metallic'].default_value = 0.6
                vor = nodes.new('ShaderNodeTexVoronoi')
                vor.distance = 'MANHATTAN'
                vor.inputs['Scale'].default_value = 3.0
                links.new(mp.outputs['Vector'], vor.inputs['Vector'])
                cr = nodes.new('ShaderNodeValToRGB')
                cr.color_ramp.elements[0].position = 0.0
                cr.color_ramp.elements[0].color = (0.25, 0.27, 0.32, 1.0)
                cr.color_ramp.elements[1].position = 0.05
                cr.color_ramp.elements[1].color = (0.35, 0.38, 0.44, 1.0)
                links.new(vor.outputs['Distance'], cr.inputs['Fac'])
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.15
                links.new(vor.outputs['Distance'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            elif tex_type == "curtainwall":
                bsdf.inputs['Base Color'].default_value = {mat_info["wall_color"]}
                bsdf.inputs['Metallic'].default_value = 0.7
                noise = nodes.new('ShaderNodeTexNoise')
                noise.inputs['Scale'].default_value = 80.0
                noise.inputs['Detail'].default_value = 2.0
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.05
                links.new(noise.outputs['Fac'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            elif tex_type == "concrete":
                bsdf.inputs['Base Color'].default_value = {mat_info["wall_color"]}
                n1 = nodes.new('ShaderNodeTexNoise')
                n1.inputs['Scale'].default_value = 25.0
                n1.inputs['Detail'].default_value = 10.0
                n1.inputs['Roughness'].default_value = 0.7
                n2 = nodes.new('ShaderNodeTexNoise')
                n2.inputs['Scale'].default_value = 120.0
                n2.inputs['Detail'].default_value = 4.0
                mix = nodes.new('ShaderNodeMix')
                mix.data_type = 'FLOAT'
                mix.inputs[0].default_value = 0.3
                links.new(mp.outputs['Vector'], n1.inputs['Vector'])
                links.new(mp.outputs['Vector'], n2.inputs['Vector'])
                links.new(n1.outputs['Fac'], mix.inputs[2])
                links.new(n2.outputs['Fac'], mix.inputs[3])
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.18
                links.new(mix.outputs[0], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            elif tex_type == "white_panel":
                bsdf.inputs['Base Color'].default_value = {mat_info["wall_color"]}
                bsdf.inputs['Metallic'].default_value = 0.15
                brick = nodes.new('ShaderNodeTexBrick')
                brick.inputs['Color1'].default_value = (0.88, 0.91, 0.96, 1.0)
                brick.inputs['Color2'].default_value = (0.65, 0.68, 0.72, 1.0)
                brick.inputs['Mortar Size'].default_value = 0.008
                brick.inputs['Scale'].default_value = 4.0
                brick.squash = 3.0
                links.new(mp.outputs['Vector'], brick.inputs['Vector'])
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.10
                links.new(brick.outputs['Fac'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            else:
                bsdf.inputs['Base Color'].default_value = {mat_info["wall_color"]}
                noise = nodes.new('ShaderNodeTexNoise')
                noise.inputs['Scale'].default_value = 50.0
                noise.inputs['Detail'].default_value = 8.0
                bump = nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.12
                links.new(noise.outputs['Fac'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        # ══════════════════════════════════════════════
        # Phase 2 — Realistic glass (Glass + Glossy mix)
        # ══════════════════════════════════════════════
        def make_glass_mat():
            mat = bpy.data.materials.new("Glass_Window")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            glass = nodes.new('ShaderNodeBsdfGlass')
            glass.inputs['Color'].default_value = (0.82, 0.90, 0.95, 1.0)
            glass.inputs['Roughness'].default_value = 0.01
            glass.inputs['IOR'].default_value = 1.52
            glossy = nodes.new('ShaderNodeBsdfGlossy')
            glossy.inputs['Color'].default_value = (0.75, 0.82, 0.90, 1.0)
            glossy.inputs['Roughness'].default_value = 0.03
            fresnel = nodes.new('ShaderNodeFresnel')
            fresnel.inputs['IOR'].default_value = 1.52
            mix = nodes.new('ShaderNodeMixShader')
            links.new(fresnel.outputs['Fac'], mix.inputs['Fac'])
            links.new(glass.outputs['BSDF'], mix.inputs[1])
            links.new(glossy.outputs['BSDF'], mix.inputs[2])
            links.new(mix.outputs['Shader'], out.inputs['Surface'])
            mat.shadow_method = 'NONE' if hasattr(mat, 'shadow_method') else 'NONE'
            return mat

        # ── Roof membrane material ────────────────────
        def make_roof_mat():
            mat = bpy.data.materials.new("Roof_Membrane")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.35, 0.37, 0.40, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.90
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 60.0
            noise.inputs['Detail'].default_value = 4.0
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.08
            links.new(noise.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_mullion_mat():
            mat = bpy.data.materials.new("Mullion_Frame")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.12, 0.12, 0.14, 1.0)
            bsdf.inputs['Metallic'].default_value = 0.9
            bsdf.inputs['Roughness'].default_value = 0.25
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_parapet_mat():
            mat = bpy.data.materials.new("Parapet_Cap")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.50, 0.50, 0.48, 1.0)
            bsdf.inputs['Metallic'].default_value = 0.5
            bsdf.inputs['Roughness'].default_value = 0.40
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_mech_mat():
            mat = bpy.data.materials.new("Mechanical_Unit")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.45, 0.48, 0.50, 1.0)
            bsdf.inputs['Metallic'].default_value = 0.8
            bsdf.inputs['Roughness'].default_value = 0.50
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_grass_mat():
            mat = bpy.data.materials.new("Grass")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Roughness'].default_value = 0.92
            tc = nodes.new('ShaderNodeTexCoord')
            n1 = nodes.new('ShaderNodeTexNoise')
            n1.inputs['Scale'].default_value = 15.0
            n1.inputs['Detail'].default_value = 8.0
            n2 = nodes.new('ShaderNodeTexNoise')
            n2.inputs['Scale'].default_value = 80.0
            n2.inputs['Detail'].default_value = 3.0
            links.new(tc.outputs['Object'], n1.inputs['Vector'])
            links.new(tc.outputs['Object'], n2.inputs['Vector'])
            cr = nodes.new('ShaderNodeValToRGB')
            cr.color_ramp.elements[0].position = 0.3
            cr.color_ramp.elements[0].color = (0.12, 0.22, 0.06, 1.0)
            cr.color_ramp.elements[1].position = 0.7
            cr.color_ramp.elements[1].color = (0.20, 0.35, 0.10, 1.0)
            links.new(n1.outputs['Fac'], cr.inputs['Fac'])
            links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.15
            links.new(n2.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_asphalt_mat():
            mat = bpy.data.materials.new("Asphalt")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.08, 0.08, 0.09, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.88
            tc = nodes.new('ShaderNodeTexCoord')
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 200.0
            noise.inputs['Detail'].default_value = 12.0
            noise.inputs['Roughness'].default_value = 0.8
            links.new(tc.outputs['Object'], noise.inputs['Vector'])
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.20
            links.new(noise.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_sidewalk_mat():
            mat = bpy.data.materials.new("Sidewalk")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Roughness'].default_value = 0.80
            tc = nodes.new('ShaderNodeTexCoord')
            brick = nodes.new('ShaderNodeTexBrick')
            brick.inputs['Color1'].default_value = (0.62, 0.60, 0.56, 1.0)
            brick.inputs['Color2'].default_value = (0.50, 0.48, 0.45, 1.0)
            brick.inputs['Mortar Size'].default_value = 0.02
            brick.inputs['Scale'].default_value = 2.5
            brick.squash = 1.0
            links.new(tc.outputs['Object'], brick.inputs['Vector'])
            links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.12
            links.new(brick.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_plinth_mat():
            mat = bpy.data.materials.new("Granite_Plinth")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.22, 0.20, 0.18, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.35
            bsdf.inputs['Metallic'].default_value = 0.05
            tc = nodes.new('ShaderNodeTexCoord')
            vor = nodes.new('ShaderNodeTexVoronoi')
            vor.inputs['Scale'].default_value = 30.0
            links.new(tc.outputs['Object'], vor.inputs['Vector'])
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 60.0
            noise.inputs['Detail'].default_value = 6.0
            links.new(tc.outputs['Object'], noise.inputs['Vector'])
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.08
            mix_b = nodes.new('ShaderNodeMath')
            mix_b.operation = 'ADD'
            links.new(vor.outputs['Distance'], mix_b.inputs[0])
            links.new(noise.outputs['Fac'], mix_b.inputs[1])
            links.new(mix_b.outputs[0], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_canopy_mat():
            mat = bpy.data.materials.new("Entrance_Canopy")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.18, 0.18, 0.20, 1.0)
            bsdf.inputs['Metallic'].default_value = 0.90
            bsdf.inputs['Roughness'].default_value = 0.15
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_foliage_mat():
            mat = bpy.data.materials.new("Foliage")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Roughness'].default_value = 0.85
            tc = nodes.new('ShaderNodeTexCoord')
            noise = nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 12.0
            noise.inputs['Detail'].default_value = 6.0
            links.new(tc.outputs['Object'], noise.inputs['Vector'])
            cr = nodes.new('ShaderNodeValToRGB')
            cr.color_ramp.elements[0].position = 0.35
            cr.color_ramp.elements[0].color = (0.08, 0.18, 0.04, 1.0)
            cr.color_ramp.elements[1].position = 0.65
            cr.color_ramp.elements[1].color = (0.15, 0.30, 0.08, 1.0)
            links.new(noise.outputs['Fac'], cr.inputs['Fac'])
            links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])
            bump = nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = 0.30
            links.new(noise.outputs['Fac'], bump.inputs['Height'])
            links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_trunk_mat():
            mat = bpy.data.materials.new("Trunk")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.18, 0.12, 0.07, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.95
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_curb_mat():
            mat = bpy.data.materials.new("Curb")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.55, 0.53, 0.50, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.75
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        def make_line_mat():
            mat = bpy.data.materials.new("RoadLine")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            out = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.90, 0.88, 0.70, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.60
            links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            return mat

        wall_mat = make_wall_mat()
        glass_mat = make_glass_mat()
        roof_mat = make_roof_mat()
        mullion_mat = make_mullion_mat()
        parapet_mat = make_parapet_mat()
        grass_mat = make_grass_mat()
        asphalt_mat = make_asphalt_mat()
        sidewalk_mat = make_sidewalk_mat()
        plinth_mat = make_plinth_mat()
        canopy_mat = make_canopy_mat()
        foliage_mat = make_foliage_mat()
        trunk_mat = make_trunk_mat()
        curb_mat = make_curb_mat()
        line_mat = make_line_mat()

        # ── Building body (solid box) ─────────────────
        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, TOTAL_H / 2))
        body = bpy.context.active_object
        body.name = "{btype}"
        body.scale = (HX, HY, TOTAL_H / 2)
        body.data.materials.append(wall_mat)

        # ── Glass window bands ────────────────────────
        GLASS_THICK = 0.03
        PROTRUDE = GLASS_THICK
        for fi in range(FLOORS):
            wz = fi * FH + WIN_SILL + WIN_H / 2
            win_lx = LENGTH * WWR / 2
            win_ly = WIDTH * WWR / 2
            if win_lx < 0.1 or WIN_H < 0.1:
                continue
            for sfx, gx, gy, gsx, gsy in [
                ("N", 0, HY + PROTRUDE, win_lx, GLASS_THICK),
                ("S", 0, -HY - PROTRUDE, win_lx, GLASS_THICK),
                ("E", HX + PROTRUDE, 0, GLASS_THICK, win_ly),
                ("W", -HX - PROTRUDE, 0, GLASS_THICK, win_ly),
            ]:
                bpy.ops.mesh.primitive_cube_add(size=2, location=(gx, gy, wz))
                win = bpy.context.active_object
                win.name = f"Win_F{{fi+1}}_{{sfx}}"
                win.scale = (gsx, gsy, WIN_H / 2)
                win.data.materials.append(glass_mat)

        # ── Mullion grid ──────────────────────────────
        FRAME = 0.04
        for fi in range(FLOORS):
            wz = fi * FH + WIN_SILL + WIN_H / 2
            for sfx, fx, fy, is_ns in [
                ("N", 0, HY, True), ("S", 0, -HY, True),
                ("E", HX, 0, False), ("W", -HX, 0, False),
            ]:
                band = (LENGTH if is_ns else WIDTH) * WWR
                if band < 0.2:
                    continue
                bpy.ops.mesh.primitive_cube_add(size=2, location=(fx, fy, wz))
                hm = bpy.context.active_object
                hm.name = f"HM_F{{fi+1}}_{{sfx}}"
                if is_ns:
                    hm.scale = (band / 2, FRAME, FRAME)
                else:
                    hm.scale = (FRAME, band / 2, FRAME)
                hm.data.materials.append(mullion_mat)
                n_div = max(1, int(band / 3.0))
                for di in range(n_div + 1):
                    pos = -band / 2 + di * band / n_div
                    if is_ns:
                        vx, vy = fx + pos, fy
                    else:
                        vx, vy = fx, fy + pos
                    bpy.ops.mesh.primitive_cube_add(size=2, location=(vx, vy, wz))
                    vm = bpy.context.active_object
                    vm.name = f"VM_F{{fi+1}}_{{sfx}}_{{di}}"
                    vm.scale = (FRAME, FRAME, WIN_H / 2)
                    vm.data.materials.append(mullion_mat)

        # ── Floor reveal lines ────────────────────────
        reveal_mat = bpy.data.materials.new("Floor_Reveal")
        reveal_mat.use_nodes = True
        reveal_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.18, 0.18, 0.20, 1.0)
        for i in range(1, FLOORS):
            z = i * FH
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, z))
            r = bpy.context.active_object
            r.name = f"Reveal_{{i}}"
            r.scale = (HX + 0.05, HY + 0.05, 0.03)
            r.data.materials.append(reveal_mat)

        # ══════════════════════════════════════════════
        # Phase 3 — Roof: parapet + membrane + equipment
        # ══════════════════════════════════════════════
        PARAPET_H = 1.2
        PARAPET_T = 0.20

        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, TOTAL_H + 0.08))
        roof = bpy.context.active_object
        roof.name = "Roof_Slab"
        roof.scale = (HX + 0.3, HY + 0.3, 0.08)
        roof.data.materials.append(roof_mat)

        for tag, px, py, sx, sy in [
            ("N", 0, HY + 0.3, HX + 0.3, PARAPET_T / 2),
            ("S", 0, -HY - 0.3, HX + 0.3, PARAPET_T / 2),
            ("E", HX + 0.3, 0, PARAPET_T / 2, HY + 0.3),
            ("W", -HX - 0.3, 0, PARAPET_T / 2, HY + 0.3),
        ]:
            pz = TOTAL_H + 0.16 + PARAPET_H / 2
            bpy.ops.mesh.primitive_cube_add(size=2, location=(px, py, pz))
            pw = bpy.context.active_object
            pw.name = f"Parapet_{{tag}}"
            pw.scale = (sx, sy, PARAPET_H / 2)
            pw.data.materials.append(parapet_mat)

        has_mech = {has_mech}
        if has_mech:
            mech_mat = make_mech_mat()
            mech_x = HX * 0.3
            mech_y = HY * 0.3
            mech_z = TOTAL_H + 0.16 + 1.5
            bpy.ops.mesh.primitive_cube_add(size=2, location=(mech_x, mech_y, mech_z))
            ahu = bpy.context.active_object
            ahu.name = "Rooftop_AHU"
            ahu.scale = (HX * 0.18, HY * 0.15, 1.5)
            ahu.data.materials.append(mech_mat)
            bpy.ops.mesh.primitive_cylinder_add(
                radius=HX * 0.06, depth=2.0,
                location=(-mech_x, -mech_y, TOTAL_H + 0.16 + 1.0)
            )
            vent = bpy.context.active_object
            vent.name = "Rooftop_Vent"
            vent.data.materials.append(mech_mat)

        # ══════════════════════════════════════════════
        # Phase 4 — Building plinth (granite base)
        # ══════════════════════════════════════════════
        PLINTH_H = 0.8
        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, PLINTH_H / 2))
        plinth = bpy.context.active_object
        plinth.name = "Plinth"
        plinth.scale = (HX + 0.4, HY + 0.4, PLINTH_H / 2)
        plinth.data.materials.append(plinth_mat)

        # ══════════════════════════════════════════════
        # Phase 5 — Environment: grass, sidewalk, road, trees
        # ══════════════════════════════════════════════
        SIDE_W = 6.0
        ROAD_W = 10.0
        ROAD_Y = -HY - SIDE_W - ROAD_W / 2

        gnd_span = max(LENGTH, WIDTH) * 3.5
        bpy.ops.mesh.primitive_plane_add(size=gnd_span, location=(0, 0, -0.02))
        gnd = bpy.context.active_object
        gnd.name = "Grass_Ground"
        gnd.data.materials.append(grass_mat)

        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.005))
        sw = bpy.context.active_object
        sw.name = "Sidewalk"
        sw.scale = (HX + SIDE_W, HY + SIDE_W, 1)
        sw.data.materials.append(sidewalk_mat)

        road_len = max(LENGTH, WIDTH) * 3.0
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, ROAD_Y, 0.005))
        road = bpy.context.active_object
        road.name = "Road"
        road.scale = (road_len / 2, ROAD_W / 2, 1)
        road.data.materials.append(asphalt_mat)

        for li in [-1, 1]:
            bpy.ops.mesh.primitive_plane_add(
                size=1,
                location=(0, ROAD_Y + li * ROAD_W * 0.35, 0.008)
            )
            ln = bpy.context.active_object
            ln.name = f"RoadLine_{{'L' if li < 0 else 'R'}}"
            ln.scale = (road_len / 2, 0.08, 1)
            ln.data.materials.append(line_mat)

        bpy.ops.mesh.primitive_cube_add(
            size=2,
            location=(0, -HY - SIDE_W, 0.08)
        )
        curb = bpy.context.active_object
        curb.name = "Curb"
        curb.scale = (road_len / 2, 0.15, 0.08)
        curb.data.materials.append(curb_mat)

        tree_spacing = max(12.0, LENGTH / 5)
        n_trees_side = max(2, int(LENGTH / tree_spacing))
        tree_positions = []
        for ti in range(n_trees_side):
            tx = -LENGTH * 0.4 + ti * (LENGTH * 0.8 / max(n_trees_side - 1, 1))
            tree_positions.append((tx, -HY - SIDE_W - ROAD_W - 6))
            tree_positions.append((tx, HY + SIDE_W + 5))
        tree_positions.append((HX + SIDE_W + 5, 0))
        tree_positions.append((-HX - SIDE_W - 5, 0))

        tree_h = min(TOTAL_H * 0.35, 10.0)
        tree_h = max(tree_h, 4.0)
        canopy_r = tree_h * 0.45

        for idx, (tx, ty) in enumerate(tree_positions):
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.20, depth=tree_h * 0.6,
                location=(tx, ty, tree_h * 0.3)
            )
            tr = bpy.context.active_object
            tr.name = f"Trunk_{{idx}}"
            tr.data.materials.append(trunk_mat)
            bpy.ops.mesh.primitive_ico_sphere_add(
                radius=canopy_r, subdivisions=2,
                location=(tx, ty, tree_h * 0.7)
            )
            fo = bpy.context.active_object
            fo.name = f"Foliage_{{idx}}"
            fo.scale = (1.0, 1.0, 0.75)
            fo.data.materials.append(foliage_mat)

        # ══════════════════════════════════════════════
        # Phase 6 — Entrance canopy
        # ══════════════════════════════════════════════
        canopy_w = min(LENGTH * 0.3, 12.0)
        canopy_d = min(WIDTH * 0.15, 5.0)
        canopy_z = FH * 0.85
        bpy.ops.mesh.primitive_cube_add(
            size=2,
            location=(0, -HY - canopy_d, canopy_z)
        )
        canopy = bpy.context.active_object
        canopy.name = "Entrance_Canopy"
        canopy.scale = (canopy_w / 2, canopy_d, 0.06)
        canopy.data.materials.append(canopy_mat)

        for side in [-1, 1]:
            col_x = side * canopy_w * 0.4
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.08, depth=canopy_z,
                location=(col_x, -HY - canopy_d * 1.5, canopy_z / 2)
            )
            col = bpy.context.active_object
            col.name = f"Canopy_Col_{{'L' if side < 0 else 'R'}}"
            col.data.materials.append(canopy_mat)

        # ══════════════════════════════════════════════
        # Phase 7 — Nishita sky + golden hour lighting
        # ══════════════════════════════════════════════
        world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
        bpy.context.scene.world = world
        world.use_nodes = True
        wn = world.node_tree.nodes
        wl = world.node_tree.links
        wn.clear()
        sky = wn.new('ShaderNodeTexSky')
        sky.sky_type = 'NISHITA'
        sky.sun_elevation = math.radians(25)
        sky.sun_rotation = math.radians(220)
        sky.altitude = 0
        sky.air_density = 1.0
        sky.dust_density = 0.8
        sky.ozone_density = 1.2
        bg = wn.new('ShaderNodeBackground')
        bg.inputs['Strength'].default_value = 1.2
        wo = wn.new('ShaderNodeOutputWorld')
        wl.new(sky.outputs['Color'], bg.inputs['Color'])
        wl.new(bg.outputs['Background'], wo.inputs['Surface'])

        bpy.ops.object.light_add(type='SUN', location=(20, -20, 50))
        sun = bpy.context.active_object
        sun.name = "Key_Sun"
        sun.data.energy = 5.0
        sun.data.color = (1.0, 0.95, 0.85)
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(220))

        bpy.ops.object.light_add(type='AREA', location=(-LENGTH * 0.9, WIDTH * 0.7, TOTAL_H * 0.6))
        fill = bpy.context.active_object
        fill.name = "Fill_Light"
        fill.data.energy = 400
        fill.data.color = (0.85, 0.90, 1.0)
        fill.data.size = max(LENGTH, WIDTH) * 0.5

        bpy.ops.object.light_add(type='AREA', location=(LENGTH * 0.4, -WIDTH * 0.6, TOTAL_H * 0.1))
        rim = bpy.context.active_object
        rim.name = "Rim_Light"
        rim.data.energy = 200
        rim.data.color = (1.0, 0.92, 0.80)
        rim.data.size = max(LENGTH, WIDTH) * 0.3

        # ── Camera ────────────────────────────────────
        cam_dist = max(LENGTH, WIDTH) * 1.4
        cam_z = max(TOTAL_H * 0.55, 8.0)
        bpy.ops.object.camera_add(
            location=(cam_dist * 0.80, -cam_dist * 0.70, cam_z)
        )
        cam = bpy.context.active_object
        cam.name = "BuildingCam"
        look_at = Vector((0, 0, TOTAL_H * 0.35))
        direction = look_at - cam.location
        rot = direction.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot.to_euler()
        cam.data.lens = 32
        cam.data.clip_end = 5000
        bpy.context.scene.camera = cam

        # ── Render settings ───────────────────────────
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = 128
        bpy.context.scene.render.resolution_x = 1920
        bpy.context.scene.render.resolution_y = 1080
        try:
            bpy.context.scene.view_settings.look = 'AgX - Medium High Contrast'
        except Exception:
            pass

        obj_count = len(bpy.data.objects)
        print(
            f"{{'{btype}'}} generated: "
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
        if p["building_type"] in ("large_office", "hospital") and p["per_floor_area"] > 1000:
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
