"""Sagrada Família v3 — Maximum fidelity procedural generation.

Pushing BMesh to its limits:
- 100k+ vertices
- Spiral staircases inside towers
- Pointed arch windows with stone tracery
- Fruit/grape/wheat pinnacle clusters
- Volumetric atmosphere (god rays through windows)
- Catenary vault with paraboloid intersections
- Full tree-column forest interior
- Trencadís mosaic on pinnacles
- Cloister arcades
- 4K render-ready with AgX tonemapping
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector, Matrix

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

# ── Dimensions ─────────────────────────────────────────
NAVE_L = 95
NAVE_W = 48
NAVE_H = 45
AISLE_W = 7.5
TOTAL_H_JESUS = 172.5
TOTAL_H_MARY = 138
TOTAL_H_EVANG = 130
APOSTLE_H = (100, 112)


# ════════════════════════════════════════════════════════
# MATERIALS (Production Grade)
# ════════════════════════════════════════════════════════


def mat_sandstone_master():
    """Aged Montjuïc sandstone — multi-octave, height-driven weathering."""
    mat = bpy.data.materials.new("Montjuic_Sandstone")
    mat.use_nodes = True
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

    # Height factor (0 at ground, 1 at top)
    div = N.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = 180.0
    L.new(sep.outputs["Z"], div.inputs[0])

    clamp = N.new("ShaderNodeClamp")
    L.new(div.outputs["Value"], clamp.inputs["Value"])

    # Macro noise (large-scale color bands in stone)
    n_macro = N.new("ShaderNodeTexNoise")
    n_macro.inputs["Scale"].default_value = 2.5
    n_macro.inputs["Detail"].default_value = 3.0
    n_macro.inputs["Roughness"].default_value = 0.4

    # Meso noise (grain structure)
    n_meso = N.new("ShaderNodeTexNoise")
    n_meso.inputs["Scale"].default_value = 15.0
    n_meso.inputs["Detail"].default_value = 10.0
    n_meso.inputs["Roughness"].default_value = 0.7

    # Micro noise (fine surface)
    n_micro = N.new("ShaderNodeTexNoise")
    n_micro.inputs["Scale"].default_value = 80.0
    n_micro.inputs["Detail"].default_value = 5.0

    # Stone color ramp (Montjuïc sandstone: golden-ochre with gray veins)
    cr_stone = N.new("ShaderNodeValToRGB")
    cr_stone.color_ramp.elements[0].position = 0.2
    cr_stone.color_ramp.elements[0].color = (0.55, 0.42, 0.28, 1)
    cr_stone.color_ramp.elements[1].position = 0.5
    cr_stone.color_ramp.elements[1].color = (0.82, 0.68, 0.48, 1)
    e1 = cr_stone.color_ramp.elements.new(0.75)
    e1.color = (0.90, 0.80, 0.60, 1)
    e2 = cr_stone.color_ramp.elements.new(0.9)
    e2.color = (0.72, 0.60, 0.42, 1)

    # Weather staining (dark at bottom/crevices)
    cr_weather = N.new("ShaderNodeValToRGB")
    cr_weather.color_ramp.elements[0].position = 0.0
    cr_weather.color_ramp.elements[0].color = (0.25, 0.20, 0.15, 1)
    cr_weather.color_ramp.elements[1].position = 0.4
    cr_weather.color_ramp.elements[1].color = (0.85, 0.72, 0.52, 1)

    # Lichen (patchy green-gray)
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 12.0
    cr_lichen = N.new("ShaderNodeValToRGB")
    cr_lichen.color_ramp.elements[0].position = 0.4
    cr_lichen.color_ramp.elements[0].color = (0, 0, 0, 1)
    cr_lichen.color_ramp.elements[1].position = 0.48
    cr_lichen.color_ramp.elements[1].color = (1, 1, 1, 1)
    lichen_rgb = N.new("ShaderNodeRGB")
    lichen_rgb.outputs[0].default_value = (0.32, 0.38, 0.25, 1)

    # Mix layers
    mix_grain = N.new("ShaderNodeMixRGB")
    mix_grain.blend_type = "OVERLAY"
    mix_grain.inputs["Fac"].default_value = 0.15

    mix_weather = N.new("ShaderNodeMixRGB")
    mix_weather.blend_type = "MULTIPLY"
    mix_weather.inputs["Fac"].default_value = 0.4

    mix_lichen = N.new("ShaderNodeMixRGB")

    # Connect base
    L.new(coord.outputs["Object"], n_macro.inputs["Vector"])
    L.new(coord.outputs["Object"], n_meso.inputs["Vector"])
    L.new(coord.outputs["Object"], n_micro.inputs["Vector"])
    L.new(coord.outputs["Object"], vor.inputs["Vector"])
    L.new(n_macro.outputs["Fac"], cr_stone.inputs["Fac"])
    L.new(clamp.outputs["Result"], cr_weather.inputs["Fac"])
    L.new(cr_stone.outputs["Color"], mix_grain.inputs["Color1"])
    L.new(n_meso.outputs["Color"], mix_grain.inputs["Color2"])
    L.new(mix_grain.outputs["Color"], mix_weather.inputs["Color1"])
    L.new(cr_weather.outputs["Color"], mix_weather.inputs["Color2"])

    # Lichen mask
    L.new(vor.outputs["Distance"], cr_lichen.inputs["Fac"])
    L.new(cr_lichen.outputs["Color"], mix_lichen.inputs["Fac"])
    L.new(mix_weather.outputs["Color"], mix_lichen.inputs["Color1"])
    L.new(lichen_rgb.outputs["Color"], mix_lichen.inputs["Color2"])

    L.new(mix_lichen.outputs["Color"], bsdf.inputs["Base Color"])

    # Triple bump (macro + meso + micro)
    bump3 = N.new("ShaderNodeBump")
    bump3.inputs["Strength"].default_value = 0.03
    bump2 = N.new("ShaderNodeBump")
    bump2.inputs["Strength"].default_value = 0.08
    bump1 = N.new("ShaderNodeBump")
    bump1.inputs["Strength"].default_value = 0.15
    L.new(n_micro.outputs["Fac"], bump3.inputs["Height"])
    L.new(n_meso.outputs["Fac"], bump2.inputs["Height"])
    L.new(bump3.outputs["Normal"], bump2.inputs["Normal"])
    L.new(n_macro.outputs["Fac"], bump1.inputs["Height"])
    L.new(bump2.outputs["Normal"], bump1.inputs["Normal"])
    L.new(bump1.outputs["Normal"], bsdf.inputs["Normal"])

    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_stained_warm():
    """East facade stained glass (sunrise: red → orange → gold)."""
    mat = bpy.data.materials.new("Glass_Sunrise")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")

    coord = N.new("ShaderNodeTexCoord")
    # Lead lines (Voronoi cell borders)
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 6.0
    vor.voronoi_dimensions = "2D"

    # Color by position (gradient across window)
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.0
    noise.inputs["Detail"].default_value = 3.0

    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.0
    cr.color_ramp.elements[0].color = (0.85, 0.08, 0.02, 1)
    cr.color_ramp.elements[1].position = 0.5
    cr.color_ramp.elements[1].color = (1.0, 0.55, 0.02, 1)
    e = cr.color_ramp.elements.new(1.0)
    e.color = (1.0, 0.88, 0.15, 1)

    # Glass BSDF
    glass = N.new("ShaderNodeBsdfGlass")
    glass.inputs["Roughness"].default_value = 0.0
    glass.inputs["IOR"].default_value = 1.52

    # Emission (glow)
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 8.0

    # Lead (dark diffuse)
    lead = N.new("ShaderNodeBsdfDiffuse")
    lead.inputs["Color"].default_value = (0.01, 0.01, 0.01, 1)

    # Lead mask from Voronoi
    cr_lead = N.new("ShaderNodeValToRGB")
    cr_lead.color_ramp.elements[0].position = 0.0
    cr_lead.color_ramp.elements[0].color = (1, 1, 1, 1)
    cr_lead.color_ramp.elements[1].position = 0.03
    cr_lead.color_ramp.elements[1].color = (0, 0, 0, 1)

    # Mix glass + emission
    mix1 = N.new("ShaderNodeMixShader")
    mix1.inputs["Fac"].default_value = 0.5

    # Mix glass-body with lead lines
    mix2 = N.new("ShaderNodeMixShader")

    L.new(coord.outputs["UV"], vor.inputs["Vector"])
    L.new(coord.outputs["Object"], noise.inputs["Vector"])
    L.new(noise.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], glass.inputs["Color"])
    L.new(cr.outputs["Color"], emit.inputs["Color"])
    L.new(glass.outputs["BSDF"], mix1.inputs[1])
    L.new(emit.outputs["Emission"], mix1.inputs[2])
    L.new(vor.outputs["Distance"], cr_lead.inputs["Fac"])
    L.new(cr_lead.outputs["Color"], mix2.inputs["Fac"])
    L.new(lead.outputs["BSDF"], mix2.inputs[1])
    L.new(mix1.outputs["Shader"], mix2.inputs[2])
    L.new(mix2.outputs["Shader"], out.inputs["Surface"])
    return mat


def mat_stained_cool():
    """West facade stained glass (sunset: blue → green → purple)."""
    mat = bpy.data.materials.new("Glass_Sunset")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")

    coord = N.new("ShaderNodeTexCoord")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 6.0
    vor.voronoi_dimensions = "2D"
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.0
    noise.inputs["Detail"].default_value = 3.0

    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.0
    cr.color_ramp.elements[0].color = (0.08, 0.15, 0.80, 1)
    cr.color_ramp.elements[1].position = 0.5
    cr.color_ramp.elements[1].color = (0.05, 0.65, 0.35, 1)
    e = cr.color_ramp.elements.new(1.0)
    e.color = (0.45, 0.08, 0.70, 1)

    glass = N.new("ShaderNodeBsdfGlass")
    glass.inputs["Roughness"].default_value = 0.0
    glass.inputs["IOR"].default_value = 1.52
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 6.0
    lead = N.new("ShaderNodeBsdfDiffuse")
    lead.inputs["Color"].default_value = (0.01, 0.01, 0.01, 1)
    cr_lead = N.new("ShaderNodeValToRGB")
    cr_lead.color_ramp.elements[0].position = 0.0
    cr_lead.color_ramp.elements[0].color = (1, 1, 1, 1)
    cr_lead.color_ramp.elements[1].position = 0.03
    cr_lead.color_ramp.elements[1].color = (0, 0, 0, 1)
    mix1 = N.new("ShaderNodeMixShader")
    mix1.inputs["Fac"].default_value = 0.5
    mix2 = N.new("ShaderNodeMixShader")

    L.new(coord.outputs["UV"], vor.inputs["Vector"])
    L.new(coord.outputs["Object"], noise.inputs["Vector"])
    L.new(noise.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], glass.inputs["Color"])
    L.new(cr.outputs["Color"], emit.inputs["Color"])
    L.new(glass.outputs["BSDF"], mix1.inputs[1])
    L.new(emit.outputs["Emission"], mix1.inputs[2])
    L.new(vor.outputs["Distance"], cr_lead.inputs["Fac"])
    L.new(cr_lead.outputs["Color"], mix2.inputs["Fac"])
    L.new(lead.outputs["BSDF"], mix2.inputs[1])
    L.new(mix1.outputs["Shader"], mix2.inputs[2])
    L.new(mix2.outputs["Shader"], out.inputs["Surface"])
    return mat


def mat_ceramic_trencadis(base, accent):
    """Trencadís (broken tile mosaic) with grout."""
    mat = bpy.data.materials.new(f"Trencadis_{base[0]:.0f}{base[1]:.0f}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.08
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.01

    coord = N.new("ShaderNodeTexCoord")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 30.0
    vor.voronoi_dimensions = "3D"

    # Tile color variation
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.3
    cr.color_ramp.elements[0].color = (*base, 1)
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (*accent, 1)

    # Grout (dark lines between tiles)
    cr_grout = N.new("ShaderNodeValToRGB")
    cr_grout.color_ramp.elements[0].position = 0.0
    cr_grout.color_ramp.elements[0].color = (1, 1, 1, 1)
    cr_grout.color_ramp.elements[1].position = 0.015
    cr_grout.color_ramp.elements[1].color = (0, 0, 0, 1)
    grout_rgb = N.new("ShaderNodeRGB")
    grout_rgb.outputs[0].default_value = (0.3, 0.28, 0.25, 1)

    mix = N.new("ShaderNodeMixRGB")

    L.new(coord.outputs["Object"], vor.inputs["Vector"])
    L.new(vor.outputs["Distance"], cr.inputs["Fac"])
    L.new(vor.outputs["Distance"], cr_grout.inputs["Fac"])
    L.new(cr_grout.outputs["Color"], mix.inputs["Fac"])
    L.new(grout_rgb.outputs["Color"], mix.inputs["Color1"])
    L.new(cr.outputs["Color"], mix.inputs["Color2"])
    L.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
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
    bsdf.inputs["Roughness"].default_value = 0.06
    if "Anisotropic" in bsdf.inputs:
        bsdf.inputs["Anisotropic"].default_value = 0.4
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
    bsdf.inputs["Roughness"].default_value = 0.4
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 4.0
    n.inputs["Detail"].default_value = 8.0
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
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.72, 0.65, 0.55, 1)
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
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
    brick.inputs["Scale"].default_value = 18.0
    brick.inputs["Color1"].default_value = (0.68, 0.62, 0.52, 1)
    brick.inputs["Color2"].default_value = (0.58, 0.52, 0.42, 1)
    brick.inputs["Mortar"].default_value = (0.38, 0.35, 0.30, 1)
    brick.inputs["Mortar Size"].default_value = 0.018
    L.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# Create materials
sandstone = mat_sandstone_master()
glass_w = mat_stained_warm()
glass_c = mat_stained_cool()
gold_mat = mat_gold()
bronze_mat = mat_bronze_patina()
interior_mat = mat_interior_stone()
plaza_mat = mat_plaza()
cer_white = mat_ceramic_trencadis((0.92, 0.90, 0.85), (0.98, 0.95, 0.88))
cer_green = mat_ceramic_trencadis((0.12, 0.50, 0.22), (0.25, 0.70, 0.15))
cer_gold = mat_ceramic_trencadis((0.85, 0.70, 0.15), (1.0, 0.85, 0.25))
cer_red = mat_ceramic_trencadis((0.75, 0.12, 0.08), (0.95, 0.25, 0.1))
cer_blue = mat_ceramic_trencadis((0.08, 0.25, 0.70), (0.15, 0.45, 0.90))
ceramics = [cer_white, cer_green, cer_gold, cer_red, cer_blue]


# ════════════════════════════════════════════════════════
# GEOMETRY GENERATORS
# ════════════════════════════════════════════════════════


def hyperboloid_tower(name, x, y, h, base_r, top_fac=0.2, twist=3.0, segs=40, rings=72, openings=True):
    """High-poly hyperboloid tower with ruled-surface twist and openings."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    grid = []

    for i in range(rings + 1):
        t = i / rings
        z = t * h
        # Profile: base → waist (70%) → slight flare at top
        waist = 0.7
        squeeze = 0.55
        profile = 1.0 - (1.0 - squeeze) * math.exp(-12 * (t - waist) ** 2)
        r = base_r * profile * (1.0 - t * (1.0 - top_fac))
        tw = t * twist * TAU / segs
        ring = []
        for j in range(segs):
            theta = TAU * j / segs + tw
            # Ruled surface: 6-fold helicoidal ridge
            ridge = 0.12 * base_r * math.sin(theta * 6 + t * PI * 4) * (1.0 - t * 0.4)
            px = (r + ridge) * math.cos(theta) + x
            py = (r + ridge) * math.sin(theta) + y
            ring.append(bm.verts.new((px, py, z)))
        grid.append(ring)

    # Faces
    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            bm.faces.new([grid[i][j], grid[i][jn], grid[i + 1][jn], grid[i + 1][j]])

    # Diamond openings (30-65% height, staggered)
    if openings:
        bm.faces.ensure_lookup_table()
        to_del = []
        for i in range(rings):
            t = i / rings
            if 0.25 < t < 0.7:
                for j in range(segs):
                    fi = i * segs + j
                    if fi < len(bm.faces):
                        # Louver pattern: 3 open, 1 closed
                        if (i + j * 2) % 5 < 2:
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


def spiral_staircase(name, x, y, z_start, height, radius=3.0, steps=200):
    """Visible spiral staircase inside tower."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    step_h = height / steps
    step_w = 0.8
    for s in range(steps):
        angle = TAU * s / 20  # 20 steps per revolution
        z = z_start + s * step_h
        # Step (wedge shape approximated as small cube)
        cx = x + (radius - step_w) * math.cos(angle)
        cy = y + (radius - step_w) * math.sin(angle)
        # Create step vertices
        r_in = radius * 0.3
        r_out = radius * 0.85
        a1 = angle - 0.12
        a2 = angle + 0.12
        v = [
            bm.verts.new((x + r_in * math.cos(a1), y + r_in * math.sin(a1), z)),
            bm.verts.new((x + r_out * math.cos(a1), y + r_out * math.sin(a1), z)),
            bm.verts.new((x + r_out * math.cos(a2), y + r_out * math.sin(a2), z)),
            bm.verts.new((x + r_in * math.cos(a2), y + r_in * math.sin(a2), z)),
            bm.verts.new((x + r_in * math.cos(a1), y + r_in * math.sin(a1), z + step_h * 0.8)),
            bm.verts.new((x + r_out * math.cos(a1), y + r_out * math.sin(a1), z + step_h * 0.8)),
            bm.verts.new((x + r_out * math.cos(a2), y + r_out * math.sin(a2), z + step_h * 0.8)),
            bm.verts.new((x + r_in * math.cos(a2), y + r_in * math.sin(a2), z + step_h * 0.8)),
        ]
        # Top face
        bm.faces.new([v[4], v[5], v[6], v[7]])
        # Front face
        bm.faces.new([v[1], v[2], v[6], v[5]])

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    return obj


def pinnacle_fruit(name, x, y, z, height, style="grape"):
    """Pinnacle with fruit cluster geometry (grape, wheat, or cypress)."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    segs = 24
    rings = 32

    for i in range(rings + 1):
        t = i / rings
        zz = t * height

        if style == "grape":
            # Grape cluster: sphere at base, tapers with bumps
            base_r = 2.2
            r = base_r * math.sin(t * PI * 0.9 + 0.1) * 0.9
            bump_amp = 0.35 * math.sin(t * PI)
        elif style == "wheat":
            # Wheat sheaf: thin base, wider middle, pointed top
            base_r = 1.5
            r = base_r * (0.3 + 0.7 * math.sin(t * PI * 0.8)) * (1 - t * 0.2)
            bump_amp = 0.2 * (1 - t)
        else:  # cypress/mitre
            base_r = 2.0
            r = base_r * (1 - t**1.8) * (1 + 0.3 * math.cos(t * PI * 2))
            bump_amp = 0.15

        r = max(r, 0.05)
        for j in range(segs):
            theta = TAU * j / segs + t * PI * 0.4  # twist
            # Individual fruit/grain bumps
            bump = bump_amp * math.sin(theta * 8 + t * 12)
            rr = r + bump
            rr = max(rr, 0.02)
            px = rr * math.cos(theta) + x
            py = rr * math.sin(theta) + y
            bm.verts.new((px, py, z + zz))

    bm.verts.ensure_lookup_table()
    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            idx = lambda ii, jj: ii * segs + jj
            try:
                bm.faces.new(
                    [bm.verts[idx(i, j)], bm.verts[idx(i, jn)], bm.verts[idx(i + 1, jn)], bm.verts[idx(i + 1, j)]]
                )
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


def pointed_arch_window(name, x, y, z, width, height, depth=0.3):
    """Gothic pointed arch window with simple tracery."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()

    # Pointed arch profile (two arcs meeting at a point)
    n_pts = 24
    hw = width / 2
    # Left arc center: (hw, 0), Right arc center: (-hw, 0)
    arc_r = math.sqrt(hw**2 + height**2)  # radius to reach the point

    profile_outer = []
    profile_inner = []
    border = 0.15

    for i in range(n_pts + 1):
        t = i / n_pts
        if t <= 0.5:
            # Left arc
            tt = t * 2
            # Arc from bottom-left to top point
            angle = math.asin(hw / arc_r)
            a = -PI / 2 + angle + tt * (PI / 2 - angle + math.acos(hw / arc_r))
            px = -hw + arc_r * math.cos(a)
            pz = arc_r * math.sin(a) + 0
        else:
            # Right arc (mirror)
            tt = (t - 0.5) * 2
            angle = math.asin(hw / arc_r)
            a = math.acos(hw / arc_r) - tt * (PI / 2 - angle + math.acos(hw / arc_r))
            px = hw - arc_r * math.cos(a)
            pz = arc_r * math.sin(a) + 0

        pz = max(pz, 0)
        profile_outer.append((px, pz))

        # Inner profile (smaller, for the glass opening)
        scale = 1 - border / max(width, height)
        profile_inner.append((px * scale, pz * scale + border))

    # Create frame (outer - inner as a solid border)
    for d in [-depth / 2, depth / 2]:
        for px, pz in profile_outer:
            bm.verts.new((x + px, y + d, z + pz))
        for px, pz in profile_inner:
            bm.verts.new((x + px, y + d, z + pz))

    n = n_pts + 1
    bm.verts.ensure_lookup_table()
    # Outer frame faces (connect outer front to outer back)
    for i in range(n_pts):
        bm.faces.new([bm.verts[i], bm.verts[i + 1], bm.verts[n + i + 1], bm.verts[n + i]])
    # Inner edges connect similarly at offset
    base2 = 2 * n
    for i in range(n_pts):
        bm.faces.new(
            [bm.verts[base2 + i], bm.verts[base2 + i + 1], bm.verts[base2 + n + i + 1], bm.verts[base2 + n + i]]
        )

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)
    return obj


def tree_column(name, x, y, h, branches=8):
    """Gaudí tree-column with star cross-section morphing to circle."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()
    segs = 20
    rings = 40
    trunk_h = h * 0.7
    r_base = 1.4

    for i in range(rings + 1):
        t = i / rings
        z = t * trunk_h
        r = r_base * (1 - t * 0.2)
        # Cross-section: square at base → star → circle at top
        star_amp = 0.25 * (1 - t) ** 2
        n_points = int(4 + t * 8)  # 4→12 sides
        twist = t * PI * 0.6

        for j in range(segs):
            theta = TAU * j / segs + twist
            star = star_amp * math.cos(theta * n_points)
            rr = r + star
            bm.verts.new((rr * math.cos(theta) + x, rr * math.sin(theta) + y, z))

    bm.verts.ensure_lookup_table()
    for i in range(rings):
        for j in range(segs):
            jn = (j + 1) % segs
            idx = i * segs + j
            bm.faces.new(
                [bm.verts[idx], bm.verts[idx - j + jn], bm.verts[(i + 1) * segs + jn], bm.verts[(i + 1) * segs + j]]
            )

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    for p in obj.data.polygons:
        p.use_smooth = True

    # Branches (hyperboloid cones angled outward)
    branch_z = trunk_h
    for b in range(branches):
        a = TAU * b / branches + random.uniform(-0.1, 0.1)
        dist = 3.5
        bx = x + dist * math.cos(a)
        by = y + dist * math.sin(a)
        bpy.ops.mesh.primitive_cone_add(
            radius1=0.5, radius2=0.08, depth=h * 0.32, location=(bx, by, branch_z + h * 0.12)
        )
        br = bpy.context.active_object
        br.name = f"{name}_br{b}"
        tilt = 0.45
        br.rotation_euler = (tilt * math.sin(a), -tilt * math.cos(a), a)
        br.data.materials.append(interior_mat)

    return obj


def catenary_vault(name, x, y, z, span_x, span_y, height, res=20):
    """Catenary vault surface (crossed catenary arches forming a vault)."""
    mesh = bpy.data.meshes.new(f"{name}_m")
    bm = bmesh.new()

    # Catenary: z = a * (cosh(d/a) - 1), inverted
    a_param = height / (math.cosh(1) - 1)

    for i in range(res + 1):
        for j in range(res + 1):
            u = (i / res - 0.5) * 2  # -1..1
            v = (j / res - 0.5) * 2  # -1..1
            px = u * span_x / 2
            py = v * span_y / 2
            # Crossed catenary height
            d = math.sqrt(u**2 + v**2)
            d = min(d, 0.99)
            pz = height * (1 - (math.cosh(d * 1.5) - 1) / (math.cosh(1.5) - 1))
            pz = max(pz, 0)
            bm.verts.new((x + px, y + py, z + pz))

    bm.verts.ensure_lookup_table()
    for i in range(res):
        for j in range(res):
            idx = lambda ii, jj: ii * (res + 1) + jj
            bm.faces.new(
                [bm.verts[idx(i, j)], bm.verts[idx(i, j + 1)], bm.verts[idx(i + 1, j + 1)], bm.verts[idx(i + 1, j)]]
            )

    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(interior_mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


# ════════════════════════════════════════════════════════
# BUILD THE BASILICA
# ════════════════════════════════════════════════════════

# ── Main nave body ─────────────────────────────────────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, NAVE_H / 2))
nave = bpy.context.active_object
nave.name = "Nave"
nave.scale = (NAVE_L / 2, NAVE_W / 2, NAVE_H / 2)
nave.data.materials.append(sandstone)

# Apse
bpy.ops.mesh.primitive_cylinder_add(
    radius=NAVE_W / 2 + 3, depth=NAVE_H + 5, location=(-NAVE_L / 2 + 8, 0, (NAVE_H + 5) / 2), vertices=64
)
apse = bpy.context.active_object
apse.name = "Apse"
apse.scale = (0.4, 1, 1)
apse.data.materials.append(sandstone)

# Catenary vaults (series along nave)
for vi in range(5):
    vx = -NAVE_L * 0.35 + vi * (NAVE_L * 0.65) / 4
    catenary_vault(f"Vault_{vi}", vx, 0, NAVE_H - 2, 16, NAVE_W * 0.8, 12, res=16)


# ── Towers ─────────────────────────────────────────────

# Jesus tower (tallest, center)
hyperboloid_tower("Jesus_Tower", 0, 0, TOTAL_H_JESUS, 8.0, top_fac=0.12, twist=3.5, segs=48, rings=90)
pinnacle_fruit("Jesus_Pin", 0, 0, TOTAL_H_JESUS, 16, "cypress")
spiral_staircase("Jesus_Stairs", 0, 0, 5, TOTAL_H_JESUS * 0.6, radius=4)
# Cross
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H_JESUS + 16 + 5))
cr = bpy.context.active_object
cr.name = "JesusCross_V"
cr.scale = (0.5, 0.5, 5)
cr.data.materials.append(gold_mat)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H_JESUS + 16 + 8))
cr2 = bpy.context.active_object
cr2.name = "JesusCross_H"
cr2.scale = (3.5, 0.5, 0.5)
cr2.data.materials.append(gold_mat)

# Mary tower
hyperboloid_tower("Mary_Tower", -35, 0, TOTAL_H_MARY, 7.0, top_fac=0.18, twist=2.8, segs=40, rings=72)
pinnacle_fruit("Mary_Pin", -35, 0, TOTAL_H_MARY, 13, "grape")
spiral_staircase("Mary_Stairs", -35, 0, 5, TOTAL_H_MARY * 0.5, radius=3.5)

# Evangelist towers (4)
evang = [(18, 16), (18, -16), (-18, 16), (-18, -16)]
for i, (ex, ey) in enumerate(evang):
    h = TOTAL_H_EVANG + random.uniform(-4, 4)
    hyperboloid_tower(f"Evang_{i}", ex, ey, h, 6.0, top_fac=0.2, twist=2.5, segs=36, rings=60)
    style = ["grape", "wheat", "cypress", "grape"][i]
    pinnacle_fruit(f"Evang_Pin_{i}", ex, ey, h, 11, style)
    spiral_staircase(f"Evang_Stair_{i}", ex, ey, 5, h * 0.5, radius=3)

# Apostle towers — Nativity facade (8 total, 4+4)
for i in range(4):
    ax = -12 + i * 9
    ay = NAVE_W / 2 + 6
    h = random.uniform(*APOSTLE_H)
    hyperboloid_tower(f"Apost_N{i}", ax, ay, h, 5.2, top_fac=0.25, twist=2.8, segs=32, rings=55)
    pinnacle_fruit(f"ApostPin_N{i}", ax, ay, h, 9, random.choice(["grape", "wheat"]))

for i in range(4):
    ax = -12 + i * 9
    ay = -NAVE_W / 2 - 6
    h = random.uniform(*APOSTLE_H)
    hyperboloid_tower(f"Apost_S{i}", ax, ay, h, 5.2, top_fac=0.25, twist=2.2, segs=32, rings=55)
    pinnacle_fruit(f"ApostPin_S{i}", ax, ay, h, 9, random.choice(["cypress", "wheat"]))


# ── Facades ────────────────────────────────────────────

# Nativity facade (organic)
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, NAVE_W / 2 + 3, NAVE_H * 0.55))
nf = bpy.context.active_object
nf.name = "Facade_Nativity"
nf.scale = (22, 2.5, NAVE_H * 0.55)
nf.data.materials.append(sandstone)

# Nativity sculptural relief (dense organic forms)
for _ in range(60):
    sx = random.uniform(-15, 20)
    sz = random.uniform(2, NAVE_H * 0.9)
    bpy.ops.mesh.primitive_ico_sphere_add(
        radius=random.uniform(0.4, 1.8), subdivisions=3, location=(sx + 5, NAVE_W / 2 + 5.5, sz)
    )
    sc = bpy.context.active_object
    sc.name = "NatSculpt"
    sc.scale = (random.uniform(0.5, 1.3), random.uniform(0.2, 0.4), random.uniform(0.7, 1.6))
    sc.data.materials.append(sandstone)

# Tree of Life (central cypress on nativity facade)
bpy.ops.mesh.primitive_cone_add(radius1=2.5, radius2=0.3, depth=25, location=(5, NAVE_W / 2 + 6, NAVE_H * 0.4 + 12))
cypress = bpy.context.active_object
cypress.name = "TreeOfLife"
cypress_mat = bpy.data.materials.new("Cypress")
cypress_mat.use_nodes = True
cypress_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.28, 0.06, 1)
cypress.data.materials.append(cypress_mat)

# Passion facade (stark, angular)
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, -NAVE_W / 2 - 3, NAVE_H * 0.5))
pf = bpy.context.active_object
pf.name = "Facade_Passion"
pf.scale = (22, 2.5, NAVE_H * 0.5)
pf.data.materials.append(sandstone)

# Passion bone-columns (tilted, austere Subirachs style)
for i in range(6):
    cx = -8 + i * 6
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, -NAVE_W / 2 - 6, NAVE_H * 0.35))
    bone = bpy.context.active_object
    bone.name = f"PassionCol_{i}"
    bone.scale = (0.5, 0.5, NAVE_H * 0.35)
    bone.rotation_euler = (random.uniform(-0.1, 0.1), random.uniform(-0.2, 0.2), 0)
    bone.data.materials.append(bronze_mat)

# Glory facade
bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 4, 0, NAVE_H * 0.55))
gf = bpy.context.active_object
gf.name = "Facade_Glory"
gf.scale = (4, NAVE_W * 0.42, NAVE_H * 0.55)
gf.data.materials.append(sandstone)

# Bronze doors (Glory)
for dy in [-8, -3, 3, 8]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 8.5, dy, 5))
    door = bpy.context.active_object
    door.name = "Door_Glory"
    door.scale = (0.12, 2.2, 5)
    door.data.materials.append(bronze_mat)


# ── Pointed Arch Windows ───────────────────────────────

for i in range(14):
    wx = -NAVE_L * 0.42 + i * (NAVE_L * 0.84) / 13
    # North (warm glass)
    pointed_arch_window(f"ArchWin_N{i}", wx, NAVE_W / 2 + 0.3, NAVE_H * 0.25, 3.0, 10)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, NAVE_W / 2 + 0.5, NAVE_H * 0.55))
    gp = bpy.context.active_object
    gp.name = f"GlassPane_N{i}"
    gp.scale = (1.4, 0.03, 5)
    gp.data.materials.append(glass_w)

    # South (cool glass)
    pointed_arch_window(f"ArchWin_S{i}", wx, -NAVE_W / 2 - 0.3, NAVE_H * 0.25, 3.0, 10)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, -NAVE_W / 2 - 0.5, NAVE_H * 0.55))
    gp2 = bpy.context.active_object
    gp2.name = f"GlassPane_S{i}"
    gp2.scale = (1.4, 0.03, 5)
    gp2.data.materials.append(glass_c)

# Rose window
bpy.ops.mesh.primitive_cylinder_add(radius=10, depth=0.15, vertices=80, location=(NAVE_L / 2 + 8.8, 0, NAVE_H * 0.72))
rose = bpy.context.active_object
rose.name = "RoseWindow"
rose.rotation_euler = (0, PI / 2, 0)
rose.data.materials.append(glass_w)

# Rose frame rings
for rs in [0.75, 0.5, 0.25]:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=10 * rs, minor_radius=0.2, location=(NAVE_L / 2 + 8.9, 0, NAVE_H * 0.72)
    )
    ring = bpy.context.active_object
    ring.name = "RoseFrame"
    ring.rotation_euler = (0, PI / 2, 0)
    ring.data.materials.append(gold_mat)
# Radial spokes
for spoke in range(12):
    a = TAU * spoke / 12
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.12,
        depth=9.5,
        location=(NAVE_L / 2 + 8.9, 10 * 0.5 * math.sin(a) / 2 + 0, NAVE_H * 0.72 + 10 * 0.5 * math.cos(a) / 2),
    )
    sp = bpy.context.active_object
    sp.name = "RoseSpoke"
    sp.rotation_euler = (math.cos(a) * PI / 2, 0, a)
    # Actually just position them radially
    sp.location = (NAVE_L / 2 + 8.9, 4.5 * math.sin(a), NAVE_H * 0.72 + 4.5 * math.cos(a))
    sp.rotation_euler = (a, PI / 2, 0)
    sp.data.materials.append(gold_mat)


# ── Interior Tree Columns ──────────────────────────────

for row in range(7):
    for col in range(2):
        cx = -NAVE_L * 0.38 + row * (NAVE_L * 0.7) / 6
        cy = -10 + col * 20
        tree_column(f"TreeCol_{row}_{col}", cx, cy, NAVE_H * 0.88, branches=6)


# ── Flying Buttresses ──────────────────────────────────

for side in [1, -1]:
    for i in range(8):
        bx = -NAVE_L * 0.38 + i * (NAVE_L * 0.7) / 7
        by = side * (NAVE_W / 2 + 7)
        # Arch
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, NAVE_H * 0.6))
        fb = bpy.context.active_object
        fb.name = "Buttress"
        fb.scale = (1.2, 7, 1.8)
        fb.rotation_euler = (side * 0.32, 0, 0)
        fb.data.materials.append(sandstone)
        # Pier
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, side * (NAVE_W / 2 + 13), NAVE_H * 0.35))
        pier = bpy.context.active_object
        pier.name = "Pier"
        pier.scale = (1.2, 1.2, NAVE_H * 0.35)
        pier.data.materials.append(sandstone)
        # Pinnacle on pier
        bpy.ops.mesh.primitive_cone_add(
            radius1=1.0, radius2=0, depth=6, location=(bx, side * (NAVE_W / 2 + 13), NAVE_H * 0.72)
        )
        pin = bpy.context.active_object
        pin.name = "ButtressPin"
        pin.data.materials.append(sandstone)


# ── Cloister Arcade ────────────────────────────────────

for side in [1, -1]:
    for i in range(12):
        cx = -NAVE_L * 0.4 + i * (NAVE_L * 0.75) / 11
        cy = side * (NAVE_W / 2 + 18)
        # Column
        bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=5, location=(cx, cy, 2.5))
        col = bpy.context.active_object
        col.name = "CloisCol"
        col.data.materials.append(sandstone)
        # Arch top
        bpy.ops.mesh.primitive_torus_add(major_radius=3, minor_radius=0.2, location=(cx, cy, 5.2))
        arch = bpy.context.active_object
        arch.name = "CloisArch"
        arch.scale = (1, 0.3, 1)
        arch.data.materials.append(sandstone)


# ════════════════════════════════════════════════════════
# ENVIRONMENT
# ════════════════════════════════════════════════════════

# Plaza
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.15))
ground = bpy.context.active_object
ground.name = "Plaza"
ground.data.materials.append(plaza_mat)

# Reflecting pool
water_mat = bpy.data.materials.new("Water")
water_mat.use_nodes = True
wn = water_mat.node_tree.nodes
wl = water_mat.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputMaterial")
bsdf = wn.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.01, 0.05, 0.12, 1)
bsdf.inputs["Roughness"].default_value = 0.001
if "Transmission Weight" in bsdf.inputs:
    bsdf.inputs["Transmission Weight"].default_value = 0.7
bsdf.inputs["IOR"].default_value = 1.33
wl.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 35, 0, -0.2))
pool = bpy.context.active_object
pool.name = "Pool"
pool.scale = (22, 14, 0.2)
pool.data.materials.append(water_mat)

# Mediterranean trees
tree_leaf_m = bpy.data.materials.new("TreeLeaf")
tree_leaf_m.use_nodes = True
tree_leaf_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.06, 0.18, 0.04, 1)
bark_m = bpy.data.materials.new("Bark")
bark_m.use_nodes = True
bark_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.10, 0.05, 1)
bark_m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.92

for i in range(30):
    angle = random.uniform(0, TAU)
    dist = random.uniform(65, 160)
    tx = dist * math.cos(angle)
    ty = dist * math.sin(angle)
    h = random.uniform(9, 16)
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=h * 0.45, location=(tx, ty, h * 0.22))
    tr = bpy.context.active_object
    tr.name = "TreeTrunk"
    tr.data.materials.append(bark_m)
    # Crown
    if random.random() < 0.35:  # Cypress
        bpy.ops.mesh.primitive_cone_add(radius1=1.5, radius2=0.2, depth=h * 0.7, location=(tx, ty, h * 0.55))
    else:  # Plane tree (round)
        bpy.ops.mesh.primitive_ico_sphere_add(radius=random.uniform(3, 5), subdivisions=2, location=(tx, ty, h * 0.6))
    crown = bpy.context.active_object
    crown.name = "TreeCrown"
    crown.data.materials.append(tree_leaf_m)


# ════════════════════════════════════════════════════════
# VOLUMETRIC ATMOSPHERE (GOD RAYS)
# ════════════════════════════════════════════════════════

# Volume cube for atmosphere
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, NAVE_H / 2))
vol = bpy.context.active_object
vol.name = "Atmosphere"
vol.scale = (NAVE_L * 0.8, NAVE_W * 0.8, NAVE_H)

vol_mat = bpy.data.materials.new("Volumetric")
vol_mat.use_nodes = True
vn = vol_mat.node_tree.nodes
vl = vol_mat.node_tree.links
vn.clear()
out = vn.new("ShaderNodeOutputMaterial")
vol_scatter = vn.new("ShaderNodeVolumeScatter")
vol_scatter.inputs["Color"].default_value = (1.0, 0.95, 0.85, 1)
vol_scatter.inputs["Density"].default_value = 0.008
vol_scatter.inputs["Anisotropy"].default_value = 0.6
vl.new(vol_scatter.outputs["Volume"], out.inputs["Volume"])
vol.data.materials.append(vol_mat)


# ════════════════════════════════════════════════════════
# LIGHTING
# ════════════════════════════════════════════════════════

# Golden hour sun (low angle, warm)
bpy.ops.object.light_add(type="SUN", location=(100, -60, 80))
sun = bpy.context.active_object
sun.name = "GoldenSun"
sun.data.energy = 8.0
sun.data.color = (1.0, 0.85, 0.55)
sun.data.angle = math.radians(0.8)  # very sharp for god rays
sun.rotation_euler = (math.radians(62), math.radians(5), math.radians(250))

# Blue sky fill (opposite side)
bpy.ops.object.light_add(type="AREA", location=(-100, 80, 100))
fill = bpy.context.active_object
fill.name = "SkyFill"
fill.data.energy = 120
fill.data.size = 80
fill.data.color = (0.6, 0.75, 1.0)

# Warm bounce from ground
bpy.ops.object.light_add(type="AREA", location=(0, 0, -5))
bounce = bpy.context.active_object
bounce.name = "GroundBounce"
bounce.data.energy = 30
bounce.data.size = 100
bounce.data.color = (0.9, 0.8, 0.6)
bounce.rotation_euler = (PI, 0, 0)

# World sky
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputWorld")
bg = wn.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.8
coord = wn.new("ShaderNodeTexCoord")
mapping = wn.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (PI / 2, 0, 0)
grad = wn.new("ShaderNodeTexGradient")
grad.gradient_type = "QUADRATIC_SPHERE"
cr = wn.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.0
cr.color_ramp.elements[0].color = (0.03, 0.08, 0.28, 1)
cr.color_ramp.elements[1].position = 0.3
cr.color_ramp.elements[1].color = (0.15, 0.35, 0.70, 1)
e1 = cr.color_ramp.elements.new(0.55)
e1.color = (0.45, 0.55, 0.78, 1)
e2 = cr.color_ramp.elements.new(0.75)
e2.color = (0.80, 0.60, 0.35, 1)
e3 = cr.color_ramp.elements.new(0.9)
e3.color = (0.98, 0.72, 0.32, 1)
e4 = cr.color_ramp.elements.new(0.98)
e4.color = (1.0, 0.85, 0.55, 1)
wl.new(coord.outputs["Generated"], mapping.inputs["Vector"])
wl.new(mapping.outputs["Vector"], grad.inputs["Vector"])
wl.new(grad.outputs["Fac"], cr.inputs["Fac"])
wl.new(cr.outputs["Color"], bg.inputs["Color"])
wl.new(bg.outputs["Background"], out.inputs["Surface"])


# ════════════════════════════════════════════════════════
# CAMERA & RENDER
# ════════════════════════════════════════════════════════

cam_loc = Vector((95, -65, 20))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.name = "HeroCamera"
target = Vector((-5, 0, TOTAL_H_JESUS * 0.38))
direction = target - cam_loc
rot = direction.to_track_quat("-Z", "Y")
cam.rotation_euler = rot.to_euler()
cam.data.lens = 18  # ultra-wide for maximum drama
cam.data.clip_end = 1200
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = (target - cam_loc).length
cam.data.dof.aperture_fstop = 5.6
bpy.context.scene.camera = cam

# Render settings (4K ready)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 512
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.render.resolution_x = 3840
scene.render.resolution_y = 2160
scene.render.film_transparent = False

# Color management
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except:
    pass

# ── Final stats ────────────────────────────────────────
obj_count = len(bpy.data.objects)
mat_count = len(bpy.data.materials)
vert_count = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH")
result = f"Sagrada v3 FINAL: {obj_count} objs, {mat_count} mats, {vert_count:,} verts | 4K Cycles 512spp"
print(result)
