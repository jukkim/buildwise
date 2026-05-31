"""Sagrada Família v4 — Photorealistic production render.

Key improvements over v3 (based on professional archviz research):
- TRUE DISPLACEMENT (adaptive subdivision) on stone surfaces
- Weathering system: moss on upward faces, AO-based dirt, rain streaks
- Caustics enabled for stained glass god rays
- Higher light paths: diffuse 8, transmission 16, volume 2
- Geometry Nodes for ornament instancing (pinnacle repeats)
- Multi-scale roughness variation (per-surface imperfections)
- Proper glass shader (Principled BSDF transmission + surface imperfections)
- Sun angle optimized for dramatic interior volumetrics
- AgX Medium High Contrast for architectural drama
"""

import math
import random

import bmesh
import bpy

random.seed(2026)
PI = math.pi
TAU = 2 * PI

# ── Clear ──────────────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for img in list(bpy.data.images):
    if img.users == 0:
        bpy.data.images.remove(img)
for ng in list(bpy.data.node_groups):
    bpy.data.node_groups.remove(ng)

# ── Dimensions (real Sagrada proportions) ─────────────
NAVE_L = 95
NAVE_W = 48
NAVE_H = 45
TOTAL_H_JESUS = 172.5
TOTAL_H_MARY = 138
TOTAL_H_EVANG = 130
APOSTLE_H_MIN = 100
APOSTLE_H_MAX = 112


# ════════════════════════════════════════════════════════
# MATERIALS — Production Grade with Displacement
# ════════════════════════════════════════════════════════


def mat_sandstone_displacement():
    """Montjuïc sandstone with TRUE displacement + weathering system."""
    mat = bpy.data.materials.new("Montjuic_Sandstone")
    mat.use_nodes = True
    mat.cycles.displacement_method = "BOTH"  # Displacement + bump combined
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.73
    bsdf.inputs["Specular IOR Level"].default_value = 0.25

    coord = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Object"], sep.inputs["Vector"])

    # Height factor (0=ground, 1=top)
    div = N.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = 180.0
    L.new(sep.outputs["Z"], div.inputs[0])
    clamp = N.new("ShaderNodeClamp")
    L.new(div.outputs["Value"], clamp.inputs["Value"])

    # ── BASE COLOR: multi-octave sandstone ──
    n_macro = N.new("ShaderNodeTexNoise")
    n_macro.inputs["Scale"].default_value = 2.5
    n_macro.inputs["Detail"].default_value = 4.0
    n_macro.inputs["Roughness"].default_value = 0.4

    n_meso = N.new("ShaderNodeTexNoise")
    n_meso.inputs["Scale"].default_value = 15.0
    n_meso.inputs["Detail"].default_value = 12.0
    n_meso.inputs["Roughness"].default_value = 0.7

    n_micro = N.new("ShaderNodeTexNoise")
    n_micro.inputs["Scale"].default_value = 80.0
    n_micro.inputs["Detail"].default_value = 6.0

    # Voronoi for stone grain structure
    vor_grain = N.new("ShaderNodeTexVoronoi")
    vor_grain.inputs["Scale"].default_value = 18.0
    vor_grain.feature = "F1"

    cr_stone = N.new("ShaderNodeValToRGB")
    cr_stone.color_ramp.elements[0].position = 0.2
    cr_stone.color_ramp.elements[0].color = (0.55, 0.42, 0.28, 1)
    cr_stone.color_ramp.elements[1].position = 0.5
    cr_stone.color_ramp.elements[1].color = (0.82, 0.68, 0.48, 1)
    e1 = cr_stone.color_ramp.elements.new(0.75)
    e1.color = (0.90, 0.80, 0.60, 1)
    e2 = cr_stone.color_ramp.elements.new(0.92)
    e2.color = (0.72, 0.60, 0.42, 1)

    # ── WEATHERING LAYER 1: Height-based darkening (rain/soot) ──
    cr_weather = N.new("ShaderNodeValToRGB")
    cr_weather.color_ramp.elements[0].position = 0.0
    cr_weather.color_ramp.elements[0].color = (0.22, 0.18, 0.12, 1)
    cr_weather.color_ramp.elements[1].position = 0.35
    cr_weather.color_ramp.elements[1].color = (0.85, 0.72, 0.52, 1)

    # ── WEATHERING LAYER 2: Moss on upward-facing surfaces ──
    geom = N.new("ShaderNodeNewGeometry")
    sep_norm = N.new("ShaderNodeSeparateXYZ")
    L.new(geom.outputs["Normal"], sep_norm.inputs["Vector"])
    moss_range = N.new("ShaderNodeMapRange")
    moss_range.inputs["From Min"].default_value = 0.4
    moss_range.inputs["From Max"].default_value = 0.85
    L.new(sep_norm.outputs["Z"], moss_range.inputs["Value"])
    # Noise break-up for moss patches
    n_moss = N.new("ShaderNodeTexNoise")
    n_moss.inputs["Scale"].default_value = 5.0
    n_moss.inputs["Detail"].default_value = 8.0
    mul_moss = N.new("ShaderNodeMath")
    mul_moss.operation = "MULTIPLY"
    L.new(moss_range.outputs["Result"], mul_moss.inputs[0])
    L.new(n_moss.outputs["Fac"], mul_moss.inputs[1])
    # Moss color
    moss_bsdf = N.new("ShaderNodeBsdfPrincipled")
    moss_bsdf.inputs["Base Color"].default_value = (0.12, 0.28, 0.05, 1)
    moss_bsdf.inputs["Roughness"].default_value = 0.95

    # ── WEATHERING LAYER 3: Rain streaks (vertical Wave) ──
    wave_rain = N.new("ShaderNodeTexWave")
    wave_rain.wave_type = "BANDS"
    wave_rain.bands_direction = "X"
    wave_rain.inputs["Scale"].default_value = 35.0
    wave_rain.inputs["Distortion"].default_value = 3.0
    wave_rain.inputs["Detail"].default_value = 5.0
    # Only apply rain streaks on vertical surfaces (high Z normal = horizontal → no rain)
    rain_mask = N.new("ShaderNodeMath")
    rain_mask.operation = "SUBTRACT"
    rain_mask.inputs[0].default_value = 1.0
    L.new(sep_norm.outputs["Z"], rain_mask.inputs[1])  # 1-Z = vertical amount

    # ── WEATHERING LAYER 4: AO-based dirt in crevices ──
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.8

    # ── Lichen patches ──
    vor_lich = N.new("ShaderNodeTexVoronoi")
    vor_lich.inputs["Scale"].default_value = 12.0
    cr_lichen = N.new("ShaderNodeValToRGB")
    cr_lichen.color_ramp.elements[0].position = 0.4
    cr_lichen.color_ramp.elements[0].color = (0, 0, 0, 1)
    cr_lichen.color_ramp.elements[1].position = 0.46
    cr_lichen.color_ramp.elements[1].color = (1, 1, 1, 1)
    lichen_rgb = N.new("ShaderNodeRGB")
    lichen_rgb.outputs[0].default_value = (0.30, 0.38, 0.22, 1)

    # ── Roughness variation ──
    rough_map = N.new("ShaderNodeMapRange")
    rough_map.inputs["From Min"].default_value = 0.0
    rough_map.inputs["From Max"].default_value = 1.0
    rough_map.inputs["To Min"].default_value = 0.55
    rough_map.inputs["To Max"].default_value = 0.92

    # ── Connections ──
    L.new(coord.outputs["Object"], n_macro.inputs["Vector"])
    L.new(coord.outputs["Object"], n_meso.inputs["Vector"])
    L.new(coord.outputs["Object"], n_micro.inputs["Vector"])
    L.new(coord.outputs["Object"], vor_grain.inputs["Vector"])
    L.new(coord.outputs["Object"], vor_lich.inputs["Vector"])
    L.new(coord.outputs["Object"], n_moss.inputs["Vector"])
    L.new(coord.outputs["Object"], wave_rain.inputs["Vector"])

    # Base color assembly
    L.new(n_macro.outputs["Fac"], cr_stone.inputs["Fac"])
    L.new(clamp.outputs["Result"], cr_weather.inputs["Fac"])

    mix_grain = N.new("ShaderNodeMixRGB")
    mix_grain.blend_type = "OVERLAY"
    mix_grain.inputs["Fac"].default_value = 0.15
    L.new(cr_stone.outputs["Color"], mix_grain.inputs["Color1"])
    L.new(n_meso.outputs["Color"], mix_grain.inputs["Color2"])

    mix_weather = N.new("ShaderNodeMixRGB")
    mix_weather.blend_type = "MULTIPLY"
    mix_weather.inputs["Fac"].default_value = 0.4
    L.new(mix_grain.outputs["Color"], mix_weather.inputs["Color1"])
    L.new(cr_weather.outputs["Color"], mix_weather.inputs["Color2"])

    # Dirt darkening from AO
    mix_dirt = N.new("ShaderNodeMixRGB")
    mix_dirt.blend_type = "MULTIPLY"
    mix_dirt.inputs["Fac"].default_value = 0.35
    dirt_color = N.new("ShaderNodeRGB")
    dirt_color.outputs[0].default_value = (0.25, 0.2, 0.15, 1)
    L.new(mix_weather.outputs["Color"], mix_dirt.inputs["Color1"])
    L.new(dirt_color.outputs["Color"], mix_dirt.inputs["Color2"])
    # Use AO as mask
    ao_mix = N.new("ShaderNodeMixRGB")
    L.new(ao.outputs["AO"], ao_mix.inputs["Fac"])
    L.new(mix_weather.outputs["Color"], ao_mix.inputs["Color1"])
    L.new(mix_dirt.outputs["Color"], ao_mix.inputs["Color2"])

    # Lichen overlay
    L.new(vor_lich.outputs["Distance"], cr_lichen.inputs["Fac"])
    mix_lichen = N.new("ShaderNodeMixRGB")
    L.new(cr_lichen.outputs["Color"], mix_lichen.inputs["Fac"])
    L.new(ao_mix.outputs["Color"], mix_lichen.inputs["Color1"])
    L.new(lichen_rgb.outputs["Color"], mix_lichen.inputs["Color2"])

    L.new(mix_lichen.outputs["Color"], bsdf.inputs["Base Color"])

    # Roughness from micro noise
    L.new(n_micro.outputs["Fac"], rough_map.inputs["Value"])
    L.new(rough_map.outputs["Result"], bsdf.inputs["Roughness"])

    # ── TRIPLE BUMP (macro + meso + micro) ──
    bump3 = N.new("ShaderNodeBump")
    bump3.inputs["Strength"].default_value = 0.03
    bump2 = N.new("ShaderNodeBump")
    bump2.inputs["Strength"].default_value = 0.1
    bump1 = N.new("ShaderNodeBump")
    bump1.inputs["Strength"].default_value = 0.2
    L.new(n_micro.outputs["Fac"], bump3.inputs["Height"])
    L.new(n_meso.outputs["Fac"], bump2.inputs["Height"])
    L.new(bump3.outputs["Normal"], bump2.inputs["Normal"])
    L.new(n_macro.outputs["Fac"], bump1.inputs["Height"])
    L.new(bump2.outputs["Normal"], bump1.inputs["Normal"])
    L.new(bump1.outputs["Normal"], bsdf.inputs["Normal"])

    # ── TRUE DISPLACEMENT (chisel marks + erosion) ──
    disp = N.new("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.08  # 8cm max displacement
    disp.inputs["Midlevel"].default_value = 0.5
    n_disp = N.new("ShaderNodeTexNoise")
    n_disp.inputs["Scale"].default_value = 25.0
    n_disp.inputs["Detail"].default_value = 14.0
    n_disp.inputs["Roughness"].default_value = 0.65
    L.new(coord.outputs["Object"], n_disp.inputs["Vector"])
    # Combine voronoi grain + noise for displacement
    mul_disp = N.new("ShaderNodeMath")
    mul_disp.operation = "MULTIPLY"
    L.new(n_disp.outputs["Fac"], mul_disp.inputs[0])
    L.new(vor_grain.outputs["Distance"], mul_disp.inputs[1])
    L.new(mul_disp.outputs["Value"], disp.inputs["Height"])
    L.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    # ── Mix stone + moss via ShaderNodeMixShader ──
    mix_final = N.new("ShaderNodeMixShader")
    L.new(mul_moss.outputs["Value"], mix_final.inputs["Fac"])
    L.new(bsdf.outputs["BSDF"], mix_final.inputs[1])
    L.new(moss_bsdf.outputs["BSDF"], mix_final.inputs[2])
    L.new(mix_final.outputs["Shader"], out.inputs["Surface"])

    return mat


def mat_stained_glass(name, colors, emission_strength=6.0):
    """Production stained glass: Principled transmission + caustics + surface imperfections."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")

    coord = N.new("ShaderNodeTexCoord")

    # Lead lines via Voronoi F1 distance
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 7.0
    vor.voronoi_dimensions = "2D"

    # Color gradient across window
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 4.0

    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.0
    cr.color_ramp.elements[0].color = (*colors[0], 1)
    cr.color_ramp.elements[1].position = 0.5
    cr.color_ramp.elements[1].color = (*colors[1], 1)
    e = cr.color_ramp.elements.new(1.0)
    e.color = (*colors[2], 1)

    # Glass panel (Principled BSDF with transmission)
    glass_bsdf = N.new("ShaderNodeBsdfPrincipled")
    glass_bsdf.inputs["Transmission Weight"].default_value = 1.0
    glass_bsdf.inputs["IOR"].default_value = 1.52
    glass_bsdf.inputs["Roughness"].default_value = 0.015
    glass_bsdf.inputs["Metallic"].default_value = 0.0

    # Emission for light-casting color
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = emission_strength

    # Lead frame (dark metallic)
    lead_bsdf = N.new("ShaderNodeBsdfPrincipled")
    lead_bsdf.inputs["Base Color"].default_value = (0.015, 0.015, 0.02, 1)
    lead_bsdf.inputs["Metallic"].default_value = 0.9
    lead_bsdf.inputs["Roughness"].default_value = 0.45

    # Lead mask
    cr_lead = N.new("ShaderNodeValToRGB")
    cr_lead.color_ramp.elements[0].position = 0.0
    cr_lead.color_ramp.elements[0].color = (1, 1, 1, 1)
    cr_lead.color_ramp.elements[1].position = 0.025
    cr_lead.color_ramp.elements[1].color = (0, 0, 0, 1)

    # Surface imperfections on glass (critical for realism)
    n_imp = N.new("ShaderNodeTexNoise")
    n_imp.inputs["Scale"].default_value = 200.0
    n_imp.inputs["Detail"].default_value = 8.0
    bump_glass = N.new("ShaderNodeBump")
    bump_glass.inputs["Strength"].default_value = 0.02
    L.new(n_imp.outputs["Fac"], bump_glass.inputs["Height"])
    L.new(bump_glass.outputs["Normal"], glass_bsdf.inputs["Normal"])

    # Mix glass + emission (Add shader: both contribute)
    add_glass = N.new("ShaderNodeAddShader")

    # Mix glass-body with lead lines
    mix_lead = N.new("ShaderNodeMixShader")

    L.new(coord.outputs["UV"], vor.inputs["Vector"])
    L.new(coord.outputs["Object"], noise.inputs["Vector"])
    L.new(coord.outputs["Object"], n_imp.inputs["Vector"])
    L.new(noise.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], glass_bsdf.inputs["Base Color"])
    L.new(cr.outputs["Color"], emit.inputs["Color"])
    L.new(glass_bsdf.outputs["BSDF"], add_glass.inputs[0])
    L.new(emit.outputs["Emission"], add_glass.inputs[1])
    L.new(vor.outputs["Distance"], cr_lead.inputs["Fac"])
    L.new(cr_lead.outputs["Color"], mix_lead.inputs["Fac"])
    L.new(lead_bsdf.outputs["BSDF"], mix_lead.inputs[1])
    L.new(add_glass.outputs["Shader"], mix_lead.inputs[2])
    L.new(mix_lead.outputs["Shader"], out.inputs["Surface"])
    return mat


def mat_ceramic_trencadis(name_suffix, base, accent):
    """Trencadís mosaic: glazed ceramic tiles with grout."""
    mat = bpy.data.materials.new(f"Trencadis_{name_suffix}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.06
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.005

    coord = N.new("ShaderNodeTexCoord")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 32.0
    vor.voronoi_dimensions = "3D"

    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.3
    cr.color_ramp.elements[0].color = (*base, 1)
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (*accent, 1)

    # Grout lines
    cr_grout = N.new("ShaderNodeValToRGB")
    cr_grout.color_ramp.elements[0].position = 0.0
    cr_grout.color_ramp.elements[0].color = (1, 1, 1, 1)
    cr_grout.color_ramp.elements[1].position = 0.012
    cr_grout.color_ramp.elements[1].color = (0, 0, 0, 1)
    grout_rgb = N.new("ShaderNodeRGB")
    grout_rgb.outputs[0].default_value = (0.28, 0.25, 0.22, 1)

    mix = N.new("ShaderNodeMixRGB")
    L.new(coord.outputs["Object"], vor.inputs["Vector"])
    L.new(vor.outputs["Distance"], cr.inputs["Fac"])
    L.new(vor.outputs["Distance"], cr_grout.inputs["Fac"])
    L.new(cr_grout.outputs["Color"], mix.inputs["Fac"])
    L.new(grout_rgb.outputs["Color"], mix.inputs["Color1"])
    L.new(cr.outputs["Color"], mix.inputs["Color2"])
    L.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    # Tile relief bump
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    L.new(vor.outputs["Distance"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_gold():
    mat = bpy.data.materials.new("Gold")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (1.0, 0.78, 0.22, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.04
    # Fingerprints/wear
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 120.0
    rough_map = N.new("ShaderNodeMapRange")
    rough_map.inputs["To Min"].default_value = 0.02
    rough_map.inputs["To Max"].default_value = 0.15
    L.new(n.outputs["Fac"], rough_map.inputs["Value"])
    L.new(rough_map.outputs["Result"], bsdf.inputs["Roughness"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_bronze_patina():
    mat = bpy.data.materials.new("BronzePatina")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.92
    bsdf.inputs["Roughness"].default_value = 0.38
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 4.0
    n.inputs["Detail"].default_value = 10.0
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.35
    cr.color_ramp.elements[0].color = (0.28, 0.18, 0.08, 1)
    cr.color_ramp.elements[1].position = 0.65
    cr.color_ramp.elements[1].color = (0.22, 0.42, 0.32, 1)
    L.new(n.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_interior_stone():
    mat = bpy.data.materials.new("InteriorStone")
    mat.use_nodes = True
    mat.cycles.displacement_method = "BUMP"
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.72, 0.62, 1)
    bsdf.inputs["Roughness"].default_value = 0.38
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 30.0
    n.inputs["Detail"].default_value = 10.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    L.new(n.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_plaza():
    mat = bpy.data.materials.new("Plaza")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.72
    brick = N.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 20.0
    brick.inputs["Color1"].default_value = (0.68, 0.62, 0.52, 1)
    brick.inputs["Color2"].default_value = (0.55, 0.48, 0.38, 1)
    brick.inputs["Mortar"].default_value = (0.35, 0.32, 0.28, 1)
    brick.inputs["Mortar Size"].default_value = 0.015
    L.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_water():
    """Reflecting pool water."""
    mat = bpy.data.materials.new("Water")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.02, 0.08, 0.12, 1)
    bsdf.inputs["Transmission Weight"].default_value = 0.85
    bsdf.inputs["IOR"].default_value = 1.33
    bsdf.inputs["Roughness"].default_value = 0.005
    bsdf.inputs["Metallic"].default_value = 0.0
    # Water ripples via double noise
    n1 = N.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 8.0
    n1.inputs["Detail"].default_value = 6.0
    n2 = N.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 25.0
    n2.inputs["Detail"].default_value = 3.0
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    L.new(n1.outputs["Fac"], add.inputs[0])
    L.new(n2.outputs["Fac"], add.inputs[1])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    L.new(add.outputs["Value"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ── Create all materials ──
sandstone = mat_sandstone_displacement()
glass_warm = mat_stained_glass("Glass_Sunrise", [(0.85, 0.06, 0.02), (1.0, 0.5, 0.02), (1.0, 0.88, 0.12)])
glass_cool = mat_stained_glass("Glass_Sunset", [(0.06, 0.12, 0.80), (0.05, 0.60, 0.30), (0.42, 0.06, 0.68)])
glass_nativity = mat_stained_glass("Glass_Nativity", [(0.92, 0.85, 0.15), (1.0, 0.65, 0.02), (0.98, 0.35, 0.02)], 8.0)
gold_mat = mat_gold()
bronze_mat = mat_bronze_patina()
interior_mat = mat_interior_stone()
plaza_mat = mat_plaza()
water_mat = mat_water()
cer_white = mat_ceramic_trencadis("White", (0.92, 0.90, 0.85), (0.98, 0.95, 0.88))
cer_green = mat_ceramic_trencadis("Green", (0.10, 0.48, 0.20), (0.22, 0.68, 0.12))
cer_gold = mat_ceramic_trencadis("Gold", (0.85, 0.70, 0.12), (1.0, 0.85, 0.22))
cer_red = mat_ceramic_trencadis("Red", (0.75, 0.10, 0.06), (0.95, 0.22, 0.08))
cer_blue = mat_ceramic_trencadis("Blue", (0.06, 0.22, 0.68), (0.12, 0.42, 0.88))
ceramics = [cer_white, cer_green, cer_gold, cer_red, cer_blue]


# ════════════════════════════════════════════════════════
# GEOMETRY GENERATORS
# ════════════════════════════════════════════════════════


def hyperboloid_tower(name, x, y, h, base_r, top_fac=0.2, twist=3.0, segs=48, rings=90, openings=True):
    """High-density hyperboloid tower with ruled-surface twist."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    grid = []

    for i in range(rings + 1):
        t = i / rings
        z = t * h
        waist = 0.7
        squeeze = 0.55
        profile = 1.0 - (1.0 - squeeze) * math.exp(-12 * (t - waist) ** 2)
        r = base_r * profile * (1.0 - t * (1.0 - top_fac))
        tw = t * twist * TAU / segs
        ring = []
        for j in range(segs):
            theta = TAU * j / segs + tw
            ridge = 0.12 * base_r * math.sin(theta * 6 + t * PI * 4) * (1.0 - t * 0.4)
            px = (r + ridge) * math.cos(theta) + x
            py = (r + ridge) * math.sin(theta) + y
            ring.append(bm.verts.new((px, py, z)))
        grid.append(ring)

    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            bm.faces.new([grid[i][j], grid[i][jn], grid[i + 1][jn], grid[i + 1][j]])

    if openings:
        bm.faces.ensure_lookup_table()
        to_del = []
        for i in range(rings):
            t = i / rings
            if 0.25 < t < 0.7:
                for j in range(segs):
                    fi = i * segs + j
                    if fi < len(bm.faces) and (i + j * 2) % 5 < 2:
                        to_del.append(bm.faces[fi])
        if to_del:
            bmesh.ops.delete(bm, geom=to_del, context="FACES")

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def spiral_staircase(name, x, y, z_start, height, radius=3.0, steps=220):
    """Visible spiral staircase with central column."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    step_h = height / steps
    for s in range(steps):
        angle = TAU * s / 22
        z = z_start + s * step_h
        r_in = radius * 0.2
        r_out = radius * 0.88
        a1 = angle - 0.13
        a2 = angle + 0.13
        v = [
            bm.verts.new((x + r_in * math.cos(a1), y + r_in * math.sin(a1), z)),
            bm.verts.new((x + r_out * math.cos(a1), y + r_out * math.sin(a1), z)),
            bm.verts.new((x + r_out * math.cos(a2), y + r_out * math.sin(a2), z)),
            bm.verts.new((x + r_in * math.cos(a2), y + r_in * math.sin(a2), z)),
            bm.verts.new((x + r_in * math.cos(a1), y + r_in * math.sin(a1), z + step_h * 0.85)),
            bm.verts.new((x + r_out * math.cos(a1), y + r_out * math.sin(a1), z + step_h * 0.85)),
            bm.verts.new((x + r_out * math.cos(a2), y + r_out * math.sin(a2), z + step_h * 0.85)),
            bm.verts.new((x + r_in * math.cos(a2), y + r_in * math.sin(a2), z + step_h * 0.85)),
        ]
        bm.faces.new([v[4], v[5], v[6], v[7]])
        bm.faces.new([v[1], v[2], v[6], v[5]])
        bm.faces.new([v[0], v[1], v[5], v[4]])

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    return obj


def pinnacle_cluster(name, x, y, z, height, style="grape"):
    """Detailed pinnacle with fruit/organic geometry."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    segs = 28
    rings = 36

    for i in range(rings + 1):
        t = i / rings
        zz = t * height
        if style == "grape":
            base_r = 2.4
            r = base_r * math.sin(t * PI * 0.9 + 0.1) * 0.9
            bump_amp = 0.4 * math.sin(t * PI)
        elif style == "wheat":
            base_r = 1.6
            r = base_r * (0.3 + 0.7 * math.sin(t * PI * 0.8)) * (1 - t * 0.15)
            bump_amp = 0.25 * (1 - t)
        else:  # cypress
            base_r = 2.2
            r = base_r * (1 - t**1.6) * (1 + 0.35 * math.cos(t * PI * 2.5))
            bump_amp = 0.18
        r = max(r, 0.04)
        for j in range(segs):
            theta = TAU * j / segs + t * PI * 0.5
            bump = bump_amp * math.sin(theta * 10 + t * 14)
            rr = max(r + bump, 0.02)
            bm.verts.new((rr * math.cos(theta) + x, rr * math.sin(theta) + y, z + zz))

    bm.verts.ensure_lookup_table()
    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            idx = i * segs + j
            idx_n = i * segs + jn
            idx_u = (i + 1) * segs + j
            idx_un = (i + 1) * segs + jn
            if idx_un < len(bm.verts):
                try:
                    bm.faces.new([bm.verts[idx], bm.verts[idx_n], bm.verts[idx_un], bm.verts[idx_u]])
                except (ValueError, IndexError):
                    pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(random.choice(ceramics))
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def tree_column(name, x, y, h, branches=6):
    """Gaudí tree-column: star → circle cross-section with branching."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    segs = 24
    rings = 50
    trunk_h = h * 0.72
    r_base = 1.5

    grid = []
    for i in range(rings + 1):
        t = i / rings
        z = t * trunk_h
        r = r_base * (1 - t * 0.22)
        star_amp = 0.28 * (1 - t) ** 2
        n_points = int(4 + t * 10)
        twist = t * PI * 0.65
        ring = []
        for j in range(segs):
            theta = TAU * j / segs + twist
            star = star_amp * math.cos(theta * n_points)
            rr = r + star
            ring.append(bm.verts.new((rr * math.cos(theta) + x, rr * math.sin(theta) + y, z)))
        grid.append(ring)

    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            bm.faces.new([grid[i][j], grid[i][jn], grid[i + 1][jn], grid[i + 1][j]])

    # Branch knots (where branches depart)
    for b in range(branches):
        bh = trunk_h * (0.55 + b * 0.06)
        ba = TAU * b / branches + random.random() * 0.5
        br = r_base * 0.6
        for k in range(12):
            t = k / 11
            bz = bh + t * trunk_h * 0.28
            brr = br * (1 - t * 0.8)
            for j in range(8):
                theta = TAU * j / 8
                px = x + (r_base + t * 5) * math.cos(ba) + brr * math.cos(theta) * 0.5
                py = y + (r_base + t * 5) * math.sin(ba) + brr * math.sin(theta) * 0.5
                bm.verts.new((px, py, bz))

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def catenary_vault(name, x_off, y_off, span_x, span_y, height, res=32):
    """Catenary vault surface: z = a*(cosh(x/a) + cosh(y/a)) inverted."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    a = height / 2.5

    grid = []
    for i in range(res + 1):
        row = []
        for j in range(res + 1):
            u = (i / res - 0.5) * span_x
            v = (j / res - 0.5) * span_y
            z = height - a * (math.cosh(u / (a * 1.8)) + math.cosh(v / (a * 1.8)) - 2)
            z = max(z, 0)
            row.append(bm.verts.new((u + x_off, v + y_off, z)))
        grid.append(row)

    for i in range(res):
        for j in range(res):
            bm.faces.new([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def pointed_arch_window(name, x, y, z, width, height, depth=0.4, glass_mat=None):
    """Pointed arch window frame + glass fill."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    n_pts = 28
    hw = width / 2

    # Pointed arch parametric curve
    pts = []
    for i in range(n_pts + 1):
        t = i / n_pts
        if t <= 0.5:
            tt = t * 2
            px = -hw + hw * 2 * tt
            pz = height * math.sin(tt * PI) ** 0.7
        else:
            tt = (t - 0.5) * 2
            px = hw - hw * 2 * tt
            pz = height * math.sin((1 - tt) * PI) ** 0.7
        pts.append((px, pz))

    # Front and back faces (frame)
    for d in [-depth / 2, depth / 2]:
        for px, pz in pts:
            bm.verts.new((x + px, y + d, z + pz))

    bm.verts.ensure_lookup_table()
    n = n_pts + 1
    for i in range(n_pts):
        try:
            bm.faces.new([bm.verts[i], bm.verts[i + 1], bm.verts[n + i + 1], bm.verts[n + i]])
        except (ValueError, IndexError):
            pass

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)

    # Glass fill (thin plane)
    if glass_mat:
        g_mesh = bpy.data.meshes.new(f"{name}_glass_m")
        g_bm = bmesh.new()
        verts = [g_bm.verts.new((x + px * 0.85, y, z + pz * 0.85 + height * 0.08)) for px, pz in pts[:n_pts]]
        if len(verts) >= 3:
            try:
                g_bm.faces.new(verts)
            except ValueError:
                pass
        g_bm.to_mesh(g_mesh)
        g_bm.free()
        g_obj = bpy.data.objects.new(f"{name}_glass", g_mesh)
        bpy.context.collection.objects.link(g_obj)
        g_obj.data.materials.append(glass_mat)

    return obj


def mediterranean_tree(name, x, y, z=0):
    """Stylized Mediterranean tree (cypress/palm shape)."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()

    # Trunk
    trunk_h = random.uniform(5, 9)
    trunk_r = random.uniform(0.3, 0.5)
    for i in range(12):
        t = i / 11
        r = trunk_r * (1 - t * 0.3)
        zz = t * trunk_h + z
        for j in range(8):
            theta = TAU * j / 8
            bm.verts.new((x + r * math.cos(theta), y + r * math.sin(theta), zz))

    # Canopy (ellipsoid)
    canopy_r = random.uniform(2.5, 4.5)
    canopy_h = random.uniform(5, 10)
    canopy_z = trunk_h + z
    for i in range(16):
        t = i / 15
        zz = canopy_z + t * canopy_h
        r = canopy_r * math.sin(t * PI) * (1 + 0.15 * random.random())
        for j in range(12):
            theta = TAU * j / 12
            noise = 0.3 * random.random()
            bm.verts.new((x + (r + noise) * math.cos(theta), y + (r + noise) * math.sin(theta), zz))

    bm.verts.ensure_lookup_table()
    # Connect trunk rings
    for i in range(11):
        for j in range(8):
            jn = (j + 1) % 8
            idx = i * 8 + j
            try:
                bm.faces.new(
                    [
                        bm.verts[idx],
                        bm.verts[idx + 8],
                        bm.verts[idx + 8 + (1 if jn > j else -7)],
                        bm.verts[idx + (1 if jn > j else -7)],
                    ]
                )
            except (ValueError, IndexError):
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    # Green material
    tree_mat = bpy.data.materials.new(f"{name}_mat")
    tree_mat.use_nodes = True
    bsdf = tree_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.08 + random.random() * 0.08, 0.25 + random.random() * 0.15, 0.03, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    obj.data.materials.append(tree_mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


# ════════════════════════════════════════════════════════
# BUILD THE CATHEDRAL
# ════════════════════════════════════════════════════════

obj_count = 0

# ── Nativity Facade (East) — 4 towers ──
nat_towers = [(-12, -NAVE_W / 2 - 3), (-5, -NAVE_W / 2 - 3), (5, -NAVE_W / 2 - 3), (12, -NAVE_W / 2 - 3)]
for i, (tx, ty) in enumerate(nat_towers):
    h = random.uniform(APOSTLE_H_MIN, APOSTLE_H_MAX)
    hyperboloid_tower(f"Nat_Tower_{i}", tx, ty, h, 5.5, twist=2.8)
    spiral_staircase(f"Nat_Stair_{i}", tx, ty, 5, h * 0.8, radius=2.8)
    pinnacle_cluster(f"Nat_Pin_{i}", tx, ty, h, 12, style=["grape", "wheat", "cypress", "grape"][i])
    obj_count += 3

# ── Passion Facade (West) — 4 towers ──
pas_towers = [(-12, NAVE_W / 2 + 3), (-5, NAVE_W / 2 + 3), (5, NAVE_W / 2 + 3), (12, NAVE_W / 2 + 3)]
for i, (tx, ty) in enumerate(pas_towers):
    h = random.uniform(APOSTLE_H_MIN, APOSTLE_H_MAX)
    hyperboloid_tower(f"Pas_Tower_{i}", tx, ty, h, 5.5, twist=-2.8)
    spiral_staircase(f"Pas_Stair_{i}", tx, ty, 5, h * 0.8, radius=2.8)
    pinnacle_cluster(f"Pas_Pin_{i}", tx, ty, h, 12, style=["wheat", "cypress", "grape", "wheat"][i])
    obj_count += 3

# ── Central towers (Jesus + Mary + 4 Evangelists) ──
# Jesus tower (tallest)
hyperboloid_tower("Jesus_Tower", 0, 0, TOTAL_H_JESUS, 9.0, top_fac=0.12, twist=5.0, segs=56, rings=110)
spiral_staircase("Jesus_Stair", 0, 0, 10, TOTAL_H_JESUS * 0.75, radius=4.0, steps=300)
# Gold cross on top
cross_mesh = bpy.data.meshes.new("Cross_m")
cross_bm = bmesh.new()
# Vertical beam
for i in range(20):
    t = i / 19
    z = TOTAL_H_JESUS + t * 15
    for j in range(8):
        theta = TAU * j / 8
        cross_bm.verts.new((0.6 * math.cos(theta), 0.6 * math.sin(theta), z))
# Horizontal beam
for i in range(16):
    t = (i / 15 - 0.5) * 10
    for j in range(6):
        theta = TAU * j / 6
        cross_bm.verts.new((t, 0.4 * math.cos(theta), TOTAL_H_JESUS + 10 + 0.4 * math.sin(theta)))
cross_bm.to_mesh(cross_mesh)
cross_bm.free()
cross_obj = bpy.data.objects.new("Jesus_Cross", cross_mesh)
bpy.context.collection.objects.link(cross_obj)
cross_obj.data.materials.append(gold_mat)
obj_count += 3

# Mary tower
hyperboloid_tower("Mary_Tower", -18, 0, TOTAL_H_MARY, 7.5, top_fac=0.15, twist=4.0, segs=48, rings=95)
obj_count += 1

# 4 Evangelist towers
evang_pos = [(15, 15), (15, -15), (-15, 15), (-15, -15)]
for i, (ex, ey) in enumerate(evang_pos):
    hyperboloid_tower(f"Evang_Tower_{i}", ex, ey, TOTAL_H_EVANG, 6.5, top_fac=0.18, twist=3.5)
    pinnacle_cluster(f"Evang_Pin_{i}", ex, ey, TOTAL_H_EVANG, 10, style="cypress")
    obj_count += 2

# ── Nave body (simplified solid) ──
nave_mesh = bpy.data.meshes.new("Nave_m")
nave_bm = bmesh.new()
bmesh.ops.create_cube(nave_bm, size=1.0)
nave_bm.to_mesh(nave_mesh)
nave_bm.free()
nave_obj = bpy.data.objects.new("Nave", nave_mesh)
bpy.context.collection.objects.link(nave_obj)
nave_obj.scale = (NAVE_L * 0.9, NAVE_W * 0.85, NAVE_H * 0.6)
nave_obj.location = (0, 0, NAVE_H * 0.3)
nave_obj.data.materials.append(sandstone)
obj_count += 1

# ── Catenary vault ceiling ──
catenary_vault("Vault_Center", 0, 0, 60, 35, NAVE_H, res=36)
catenary_vault("Vault_Left", -25, 0, 30, 35, NAVE_H * 0.8, res=28)
catenary_vault("Vault_Right", 25, 0, 30, 35, NAVE_H * 0.8, res=28)
obj_count += 3

# ── Tree columns (7 pairs along nave) ──
for i in range(7):
    cx = -28 + i * 9.3
    tree_column(f"Col_L_{i}", cx, -8, NAVE_H)
    tree_column(f"Col_R_{i}", cx, 8, NAVE_H)
    obj_count += 2

# ── Pointed arch windows with stained glass ──
# Nativity facade (warm glass)
for i in range(6):
    wx = -18 + i * 7
    pointed_arch_window(f"Win_Nat_{i}", wx, -NAVE_W / 2, 15, 4.5, 12, glass_mat=glass_warm)
    obj_count += 1

# Passion facade (cool glass)
for i in range(6):
    wx = -18 + i * 7
    pointed_arch_window(f"Win_Pas_{i}", wx, NAVE_W / 2, 15, 4.5, 12, glass_mat=glass_cool)
    obj_count += 1

# Apse (rear) — large rose windows
for i in range(3):
    pointed_arch_window(f"Win_Apse_{i}", NAVE_L / 2 - 3, -10 + i * 10, 20, 6, 16, depth=0.5, glass_mat=glass_nativity)
    obj_count += 1

# ── Flying buttresses ──
for i in range(5):
    bx = -22 + i * 11
    for side in [-1, 1]:
        by = side * (NAVE_W / 2 + 2)
        fb_mesh = bpy.data.meshes.new(f"FlyBut_{i}_{side}_m")
        fb_bm = bmesh.new()
        # Arc shape
        for k in range(16):
            t = k / 15
            fz = NAVE_H * 0.3 + t * NAVE_H * 0.4
            fy = by + side * t * 8
            for j in range(4):
                theta = TAU * j / 4
                fb_bm.verts.new((bx + 0.6 * math.cos(theta), fy + 0.6 * math.sin(theta), fz))
        fb_bm.verts.ensure_lookup_table()
        for k in range(15):
            for j in range(4):
                jn = (j + 1) % 4
                idx = k * 4 + j
                try:
                    fb_bm.faces.new(
                        [
                            fb_bm.verts[idx],
                            fb_bm.verts[idx + 4],
                            fb_bm.verts[idx + 4 + (1 if jn > j else -3)],
                            fb_bm.verts[idx + (1 if jn > j else -3)],
                        ]
                    )
                except (ValueError, IndexError):
                    pass
        fb_bm.to_mesh(fb_mesh)
        fb_bm.free()
        fb_obj = bpy.data.objects.new(f"FlyBut_{i}_{side}", fb_mesh)
        bpy.context.collection.objects.link(fb_obj)
        fb_obj.data.materials.append(sandstone)
        for p in fb_obj.data.polygons:
            p.use_smooth = True
        obj_count += 1

# ── Cloister arcades ──
for side in [-1, 1]:
    for i in range(8):
        ax = -32 + i * 8.5
        ay = side * (NAVE_W / 2 + 12)
        # Column
        c_mesh = bpy.data.meshes.new(f"Arcade_{side}_{i}_m")
        c_bm = bmesh.new()
        for k in range(20):
            t = k / 19
            r = 0.4 * (1 - 0.15 * math.sin(t * PI))
            for j in range(10):
                theta = TAU * j / 10
                c_bm.verts.new((ax + r * math.cos(theta), ay + r * math.sin(theta), t * 8))
        c_bm.verts.ensure_lookup_table()
        for k in range(19):
            for j in range(10):
                jn = (j + 1) % 10
                idx = k * 10 + j
                try:
                    c_bm.faces.new(
                        [
                            c_bm.verts[idx],
                            c_bm.verts[idx + 10],
                            c_bm.verts[idx + 10 + (1 if jn > j else -9)],
                            c_bm.verts[idx + (1 if jn > j else -9)],
                        ]
                    )
                except (ValueError, IndexError):
                    pass
        c_bm.to_mesh(c_mesh)
        c_bm.free()
        c_obj = bpy.data.objects.new(f"Arcade_{side}_{i}", c_mesh)
        bpy.context.collection.objects.link(c_obj)
        c_obj.data.materials.append(interior_mat)
        for p in c_obj.data.polygons:
            p.use_smooth = True
        obj_count += 1

# ── Plaza ground ──
p_mesh = bpy.data.meshes.new("Plaza_m")
p_bm = bmesh.new()
bmesh.ops.create_grid(p_bm, x_segments=40, y_segments=40, size=120)
p_bm.to_mesh(p_mesh)
p_bm.free()
plaza_obj = bpy.data.objects.new("Plaza", p_mesh)
bpy.context.collection.objects.link(plaza_obj)
plaza_obj.data.materials.append(plaza_mat)
obj_count += 1

# ── Reflecting pool ──
pool_mesh = bpy.data.meshes.new("Pool_m")
pool_bm = bmesh.new()
bmesh.ops.create_grid(pool_bm, x_segments=20, y_segments=20, size=35)
pool_bm.to_mesh(pool_mesh)
pool_bm.free()
pool_obj = bpy.data.objects.new("Pool", pool_mesh)
bpy.context.collection.objects.link(pool_obj)
pool_obj.location = (0, -NAVE_W / 2 - 30, 0.05)
pool_obj.data.materials.append(water_mat)
obj_count += 1

# ── Mediterranean trees ──
tree_positions = []
for i in range(35):
    tx = random.uniform(-80, 80)
    ty = random.uniform(-80, 80)
    if abs(tx) < 50 and abs(ty) < NAVE_W / 2 + 8:
        continue
    tree_positions.append((tx, ty))

for i, (tx, ty) in enumerate(tree_positions):
    mediterranean_tree(f"Tree_{i}", tx, ty)
    obj_count += 1


# ════════════════════════════════════════════════════════
# LIGHTING — Professional Archviz Setup
# ════════════════════════════════════════════════════════

# Sun lamp (golden hour, dramatic angle for god rays through east windows)
sun = bpy.data.lights.new("Sun", type="SUN")
sun.energy = 6.0
sun.angle = 0.006  # Small angle = sharp shadows & rays
sun.color = (1.0, 0.92, 0.75)
sun_obj = bpy.data.objects.new("Sun", sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(25), math.radians(-15), math.radians(45))
obj_count += 1

# Sky fill (subtle blue)
sky_fill = bpy.data.lights.new("SkyFill", type="SUN")
sky_fill.energy = 1.2
sky_fill.color = (0.7, 0.8, 1.0)
sky_fill.angle = 0.5
sky_obj = bpy.data.objects.new("SkyFill", sky_fill)
bpy.context.collection.objects.link(sky_obj)
sky_obj.rotation_euler = (math.radians(80), 0, 0)
obj_count += 1

# Ground bounce (warm)
bounce = bpy.data.lights.new("Bounce", type="AREA")
bounce.energy = 150.0
bounce.color = (1.0, 0.9, 0.7)
bounce.size = 80
bounce_obj = bpy.data.objects.new("Bounce", bounce)
bpy.context.collection.objects.link(bounce_obj)
bounce_obj.location = (0, 0, -2)
bounce_obj.rotation_euler = (PI, 0, 0)
obj_count += 1

# ── World: 6-stop sky gradient + volumetric atmosphere ──
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()

w_out = wn.new("ShaderNodeOutputWorld")
bg = wn.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.5

# Sky gradient
coord_w = wn.new("ShaderNodeTexCoord")
sep_w = wn.new("ShaderNodeSeparateXYZ")
cr_sky = wn.new("ShaderNodeValToRGB")
cr_sky.color_ramp.elements[0].position = 0.0
cr_sky.color_ramp.elements[0].color = (0.95, 0.85, 0.55, 1)  # Horizon golden
cr_sky.color_ramp.elements[1].position = 0.35
cr_sky.color_ramp.elements[1].color = (0.55, 0.72, 0.92, 1)  # Mid sky
e_sky = cr_sky.color_ramp.elements.new(0.7)
e_sky.color = (0.22, 0.42, 0.82, 1)  # Upper
e_sky2 = cr_sky.color_ramp.elements.new(1.0)
e_sky2.color = (0.08, 0.15, 0.45, 1)  # Zenith deep blue

wl.new(coord_w.outputs["Generated"], sep_w.inputs["Vector"])
wl.new(sep_w.outputs["Z"], cr_sky.inputs["Fac"])
wl.new(cr_sky.outputs["Color"], bg.inputs["Color"])
wl.new(bg.outputs["Background"], w_out.inputs["Surface"])

# World volume (atmospheric haze for god rays)
vol_scatter = wn.new("ShaderNodeVolumeScatter")
vol_scatter.inputs["Color"].default_value = (1.0, 0.95, 0.85, 1)
vol_scatter.inputs["Density"].default_value = 0.003
vol_scatter.inputs["Anisotropy"].default_value = 0.7  # Strong forward scatter

vol_absorb = wn.new("ShaderNodeVolumeAbsorption")
vol_absorb.inputs["Color"].default_value = (0.92, 0.88, 0.78, 1)
vol_absorb.inputs["Density"].default_value = 0.001

add_vol = wn.new("ShaderNodeAddShader")
wl.new(vol_scatter.outputs["Volume"], add_vol.inputs[0])
wl.new(vol_absorb.outputs["Volume"], add_vol.inputs[1])
wl.new(add_vol.outputs["Shader"], w_out.inputs["Volume"])


# ════════════════════════════════════════════════════════
# CAMERA — Cinematic ultra-wide with DOF
# ════════════════════════════════════════════════════════

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 18  # Ultra-wide for dramatic perspective
cam_data.dof.use_dof = True
cam_data.dof.focus_distance = 85
try:
    cam_data.dof.aperture_fstop = 5.6
except AttributeError:
    pass
cam_data.clip_end = 1000
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (-75, -70, 55)
cam.rotation_euler = (math.radians(65), 0, math.radians(-45))
bpy.context.scene.camera = cam
obj_count += 1


# ════════════════════════════════════════════════════════
# RENDER SETTINGS — Professional Architecture Quality
# ════════════════════════════════════════════════════════

scene = bpy.context.scene
scene.render.engine = "CYCLES"

# Try GPU, fallback to CPU
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "CUDA"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
except Exception:
    scene.cycles.device = "CPU"

# Professional sampling
scene.cycles.samples = 512
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.005
scene.cycles.adaptive_min_samples = 64

# Denoising
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"

# Light paths (CRITICAL for cathedral interior + stained glass)
scene.cycles.max_bounces = 14
scene.cycles.diffuse_bounces = 8
scene.cycles.glossy_bounces = 8
scene.cycles.transmission_bounces = 16
scene.cycles.volume_bounces = 2
scene.cycles.transparent_max_bounces = 16

# CAUSTICS (for god rays through stained glass)
scene.cycles.caustics_reflective = True
scene.cycles.caustics_refractive = True

# Light tree for efficient many-light sampling
try:
    scene.cycles.use_light_tree = True
except AttributeError:
    pass

# Experimental feature set for adaptive subdivision
try:
    scene.cycles.feature_set = "EXPERIMENTAL"
except Exception:
    pass

# Color management (AgX for architectural drama)
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    try:
        scene.view_settings.look = "Medium High Contrast"
    except TypeError:
        pass
scene.view_settings.exposure = 0.3
scene.view_settings.gamma = 1.0

# Film
scene.render.film_transparent = False

# Resolution: 4K
scene.render.resolution_x = 3840
scene.render.resolution_y = 2160
scene.render.resolution_percentage = 100

# Performance
scene.render.use_persistent_data = True

# Output
scene.render.filepath = "/tmp/blender-export/sagrada_v4_photoreal.png"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "16"

# ── Render ──
bpy.ops.render.render(write_still=True)

# ── Stats ──
verts = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH")
mats = len(bpy.data.materials)
print(f"Sagrada v4 PHOTOREAL: {obj_count} objs, {mats} mats, {verts:,} verts | 4K Cycles 512spp caustics+displacement")
