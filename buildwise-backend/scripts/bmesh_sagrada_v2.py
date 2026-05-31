"""Sagrada Família v2 — High-fidelity mathematical surfaces.

Gaudí's architecture is defined by:
- Hyperboloid towers with ruled-surface openings
- Catenary arches (inverted chain curves)
- Paraboloid vaults
- Helicoidal (twisted) surfaces on spires
- Venetian mosaic ceramic pinnacles

This version uses proper parametric equations, not primitive boxes.
"""

import math
import random
from functools import lru_cache

import bmesh
import bpy
from mathutils import Vector, Matrix, Euler

random.seed(42)

# ── Clear ──────────────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

# ── Constants ──────────────────────────────────────────
NAVE_L = 90
NAVE_W = 45
NAVE_H = 45
TOTAL_H_JESUS = 172.5
PI = math.pi
TAU = 2 * PI


# ════════════════════════════════════════════════════════
# ADVANCED MATERIALS
# ════════════════════════════════════════════════════════


def mat_aged_sandstone():
    """Multi-layer sandstone with weathering, lichen, water stains."""
    mat = bpy.data.materials.new("AgedSandstone")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()

    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.72

    # Coordinate
    coord = N.new("ShaderNodeTexCoord")
    map1 = N.new("ShaderNodeMapping")
    map1.inputs["Scale"].default_value = (1, 1, 1)

    # Base sandstone color (warm ochre layered)
    n1 = N.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 8.0
    n1.inputs["Detail"].default_value = 14.0
    n1.inputs["Roughness"].default_value = 0.7

    n2 = N.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 45.0
    n2.inputs["Detail"].default_value = 6.0

    # Age/weathering mask (darker at bottom, water streaks)
    n3 = N.new("ShaderNodeTexNoise")
    n3.inputs["Scale"].default_value = 3.0
    n3.inputs["Detail"].default_value = 4.0
    n3.inputs["Distortion"].default_value = 2.0

    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Object"], sep.inputs["Vector"])

    # Height gradient (bottom = darker/wetter)
    math_div = N.new("ShaderNodeMath")
    math_div.operation = "DIVIDE"
    math_div.inputs[1].default_value = TOTAL_H_JESUS
    L.new(sep.outputs["Z"], math_div.inputs[0])

    # Color ramp for base sandstone
    cr1 = N.new("ShaderNodeValToRGB")
    cr1.color_ramp.elements[0].position = 0.25
    cr1.color_ramp.elements[0].color = (0.62, 0.48, 0.32, 1)
    cr1.color_ramp.elements[1].position = 0.75
    cr1.color_ramp.elements[1].color = (0.88, 0.76, 0.55, 1)
    e = cr1.color_ramp.elements.new(0.5)
    e.color = (0.78, 0.64, 0.44, 1)

    # Weathering color ramp
    cr2 = N.new("ShaderNodeValToRGB")
    cr2.color_ramp.elements[0].position = 0.0
    cr2.color_ramp.elements[0].color = (0.35, 0.30, 0.22, 1)  # dark base
    cr2.color_ramp.elements[1].position = 0.6
    cr2.color_ramp.elements[1].color = (0.75, 0.65, 0.48, 1)  # clean upper

    # Mix base + weathering
    mix1 = N.new("ShaderNodeMixRGB")
    mix1.blend_type = "MULTIPLY"
    mix1.inputs["Fac"].default_value = 0.3

    # Lichen spots (green-gray patches)
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 15.0
    cr3 = N.new("ShaderNodeValToRGB")
    cr3.color_ramp.elements[0].position = 0.45
    cr3.color_ramp.elements[0].color = (0, 0, 0, 1)
    cr3.color_ramp.elements[1].position = 0.55
    cr3.color_ramp.elements[1].color = (1, 1, 1, 1)

    mix2 = N.new("ShaderNodeMixRGB")
    lichen_color = N.new("ShaderNodeRGB")
    lichen_color.outputs[0].default_value = (0.35, 0.40, 0.28, 1)

    # Connections
    L.new(coord.outputs["Object"], map1.inputs["Vector"])
    L.new(map1.outputs["Vector"], n1.inputs["Vector"])
    L.new(map1.outputs["Vector"], n2.inputs["Vector"])
    L.new(map1.outputs["Vector"], n3.inputs["Vector"])
    L.new(map1.outputs["Vector"], vor.inputs["Vector"])

    L.new(n1.outputs["Fac"], cr1.inputs["Fac"])
    L.new(math_div.outputs["Value"], cr2.inputs["Fac"])

    L.new(cr1.outputs["Color"], mix1.inputs["Color1"])
    L.new(cr2.outputs["Color"], mix1.inputs["Color2"])

    L.new(vor.outputs["Distance"], cr3.inputs["Fac"])
    L.new(cr3.outputs["Color"], mix2.inputs["Fac"])
    L.new(mix1.outputs["Color"], mix2.inputs["Color1"])
    L.new(lichen_color.outputs["Color"], mix2.inputs["Color2"])

    L.new(mix2.outputs["Color"], bsdf.inputs["Base Color"])

    # Multi-scale bump
    bump1 = N.new("ShaderNodeBump")
    bump1.inputs["Strength"].default_value = 0.12
    bump2 = N.new("ShaderNodeBump")
    bump2.inputs["Strength"].default_value = 0.05
    L.new(n1.outputs["Fac"], bump1.inputs["Height"])
    L.new(n2.outputs["Fac"], bump2.inputs["Height"])
    L.new(bump1.outputs["Normal"], bump2.inputs["Normal"])
    L.new(bump2.outputs["Normal"], bsdf.inputs["Normal"])

    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_glass_cathedral(hue_shift=0.0):
    """Stained glass with proper color-dependent transmission."""
    mat = bpy.data.materials.new(f"CathedralGlass_{hue_shift:.1f}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()

    out = N.new("ShaderNodeOutputMaterial")
    mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None

    # Glass shader
    glass = N.new("ShaderNodeBsdfGlass")
    glass.inputs["IOR"].default_value = 1.52
    glass.inputs["Roughness"].default_value = 0.01

    # Emission for glow-through effect
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 4.0

    # Voronoi pattern for lead lines
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 8.0
    vor.voronoi_dimensions = "2D"

    # Color pattern (stained glass segments)
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 2.0

    cr = N.new("ShaderNodeValToRGB")
    # Sagrada's east = warm (sunrise), west = cool (sunset)
    if hue_shift < 0.5:  # warm side
        cr.color_ramp.elements[0].color = (0.9, 0.2, 0.05, 1)
        cr.color_ramp.elements[1].color = (1.0, 0.8, 0.1, 1)
        e = cr.color_ramp.elements.new(0.5)
        e.color = (0.95, 0.5, 0.02, 1)
    else:  # cool side
        cr.color_ramp.elements[0].color = (0.05, 0.2, 0.8, 1)
        cr.color_ramp.elements[1].color = (0.3, 0.8, 0.4, 1)
        e = cr.color_ramp.elements.new(0.5)
        e.color = (0.1, 0.5, 0.9, 1)

    L.new(noise.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], glass.inputs["Color"])
    L.new(cr.outputs["Color"], emit.inputs["Color"])

    # Mix: glass body + emission (light passes through)
    mix1 = N.new("ShaderNodeMixShader")
    mix1.inputs["Fac"].default_value = 0.35
    L.new(glass.outputs["BSDF"], mix1.inputs[1])
    L.new(emit.outputs["Emission"], mix1.inputs[2])

    # Lead lines (dark borders from Voronoi)
    lead = N.new("ShaderNodeBsdfDiffuse")
    lead.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)

    cr2 = N.new("ShaderNodeValToRGB")
    cr2.color_ramp.elements[0].position = 0.0
    cr2.color_ramp.elements[0].color = (1, 1, 1, 1)  # glass
    cr2.color_ramp.elements[1].position = 0.05
    cr2.color_ramp.elements[1].color = (0, 0, 0, 1)  # lead line

    mix2 = N.new("ShaderNodeMixShader")
    L.new(vor.outputs["Distance"], cr2.inputs["Fac"])
    L.new(cr2.outputs["Color"], mix2.inputs["Fac"])
    L.new(mix1.outputs["Shader"], mix2.inputs[1])
    L.new(lead.outputs["BSDF"], mix2.inputs[2])

    L.new(mix2.outputs["Shader"], out.inputs["Surface"])
    return mat


def mat_venetian_ceramic(base_color, accent_color):
    """Trencadís mosaic (broken tile) material."""
    mat = bpy.data.materials.new(f"Ceramic_{base_color[0]:.1f}_{base_color[1]:.1f}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()

    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Metallic"].default_value = 0.05
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.02

    # Voronoi for broken-tile pattern
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 25.0
    vor.voronoi_dimensions = "3D"

    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.3
    cr.color_ramp.elements[0].color = (*base_color, 1)
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (*accent_color, 1)

    L.new(vor.outputs["Distance"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], bsdf.inputs["Base Color"])

    # Grout lines bump
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    L.new(vor.outputs["Distance"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_gold_ornate():
    """Polished gold with micro-scratches."""
    mat = bpy.data.materials.new("Gold_Ornate")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (1.0, 0.78, 0.22, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.08
    # Anisotropic for brushed look
    if "Anisotropic" in bsdf.inputs:
        bsdf.inputs["Anisotropic"].default_value = 0.3
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 200.0
    n.inputs["Detail"].default_value = 3.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.02
    L.new(n.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_dark_bronze():
    """Patinated bronze for doors and sculpture."""
    mat = bpy.data.materials.new("DarkBronze")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.45
    # Patina: mix bronze + verdigris
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 8.0
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.4
    cr.color_ramp.elements[0].color = (0.30, 0.20, 0.10, 1)  # bronze
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (0.25, 0.40, 0.30, 1)  # verdigris
    L.new(noise.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_plaza_stone():
    """Worn limestone plaza paving."""
    mat = bpy.data.materials.new("PlazaStone")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.75
    brick = N.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 12.0
    brick.inputs["Color1"].default_value = (0.72, 0.68, 0.60, 1)
    brick.inputs["Color2"].default_value = (0.62, 0.58, 0.50, 1)
    brick.inputs["Mortar"].default_value = (0.4, 0.38, 0.34, 1)
    brick.inputs["Mortar Size"].default_value = 0.02
    L.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.1
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# Build materials
sandstone = mat_aged_sandstone()
gold = mat_gold_ornate()
bronze = mat_dark_bronze()
plaza = mat_plaza_stone()
glass_warm = mat_glass_cathedral(0.2)
glass_cool = mat_glass_cathedral(0.8)
ceramic_white_gold = mat_venetian_ceramic((0.95, 0.92, 0.85), (0.9, 0.75, 0.2))
ceramic_green_gold = mat_venetian_ceramic((0.15, 0.55, 0.25), (0.85, 0.75, 0.15))
ceramic_red_gold = mat_venetian_ceramic((0.8, 0.15, 0.1), (0.95, 0.8, 0.2))
ceramic_blue_white = mat_venetian_ceramic((0.1, 0.3, 0.75), (0.9, 0.92, 0.95))
ceramics = [ceramic_white_gold, ceramic_green_gold, ceramic_red_gold, ceramic_blue_white]


# ════════════════════════════════════════════════════════
# PARAMETRIC GEOMETRY GENERATORS
# ════════════════════════════════════════════════════════


def make_hyperboloid_tower(
    name, x, y, height, base_r, top_r_factor=0.3, twist_turns=2.5, segments=32, rings=48, openings=True
):
    """Generate a tower with ruled hyperboloid surface and diamond openings.

    The real Sagrada towers have ruled-surface geometry where straight lines
    create a curved surface (hyperboloid of one sheet), plus diamond-shaped
    openings that let light through.
    """
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()

    verts_grid = []  # [ring][seg]

    for i in range(rings + 1):
        t = i / rings  # 0..1 bottom to top
        z = t * height

        # Hyperboloid radius profile: wide base, narrow waist, slight flare at top
        # r(t) = sqrt(a² + (b*t - c)²) * base_r
        waist_pos = 0.7  # waist at 70% height
        waist_factor = 0.6
        profile = 1.0 - (1.0 - waist_factor) * math.exp(-8 * (t - waist_pos) ** 2)
        r = base_r * profile * (1.0 - t * (1.0 - top_r_factor))

        # Twist angle increases with height (ruled surface)
        twist = t * twist_turns * TAU / segments

        ring_verts = []
        for j in range(segments):
            theta = TAU * j / segments + twist

            # Add ruled-surface undulation (straight lines creating curves)
            undulation = 0.15 * base_r * math.sin(theta * 4 + t * PI * 3) * (1 - t * 0.3)

            px = (r + undulation) * math.cos(theta) + x
            py = (r + undulation) * math.sin(theta) + y
            v = bm.verts.new((px, py, z))
            ring_verts.append(v)
        verts_grid.append(ring_verts)

    # Create faces
    for i in range(rings):
        for j in range(segments):
            j_next = (j + 1) % segments
            v0 = verts_grid[i][j]
            v1 = verts_grid[i][j_next]
            v2 = verts_grid[i + 1][j_next]
            v3 = verts_grid[i + 1][j]
            bm.faces.new([v0, v1, v2, v3])

    # Diamond openings: delete faces in a pattern
    if openings:
        bm.faces.ensure_lookup_table()
        faces_to_delete = []
        for i in range(rings):
            for j in range(segments):
                fi = i * segments + j
                if fi >= len(bm.faces):
                    continue
                # Diamond pattern: skip every other in a diagonal
                t = i / rings
                if 0.3 < t < 0.85:  # only in middle section
                    if (i + j) % 4 == 0 or (i + j) % 4 == 1:
                        if random.random() < 0.3:  # 30% of eligible faces
                            faces_to_delete.append(bm.faces[fi])

        bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    return obj


def make_pinnacle(name, x, y, z_base, height, style="mitre"):
    """Gaudí pinnacle: bishop's mitre, grape cluster, or wheat sheaf."""
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()

    segments = 20
    rings = 24

    for i in range(rings + 1):
        t = i / rings
        zz = t * height

        if style == "mitre":
            # Bishop's mitre: 4-pointed crown shape
            r_base = 1.8 * (1 - t * 0.3)
            for j in range(segments):
                theta = TAU * j / segments
                # 4 pointed lobes
                lobe = 0.4 * math.cos(theta * 4) * (1 - t) ** 2
                # Twist at top
                twist_angle = t * PI * 0.3
                r = r_base + lobe
                # Taper to point
                r *= 1 - t**1.5
                r = max(r, 0.1)
                px = r * math.cos(theta + twist_angle) + x
                py = r * math.sin(theta + twist_angle) + y
                bm.verts.new((px, py, z_base + zz))

        elif style == "grape":
            # Grape cluster: bulbous bottom, tapers up
            r_base = 2.0
            for j in range(segments):
                theta = TAU * j / segments
                # Bumpy surface (grapes)
                bump = 0.3 * math.sin(theta * 8 + t * 6) * math.sin(t * PI)
                r = r_base * math.sin(t * PI) * 0.8 + bump
                r = max(r, 0.05)
                px = r * math.cos(theta) + x
                py = r * math.sin(theta) + y
                bm.verts.new((px, py, z_base + zz))

    bm.verts.ensure_lookup_table()
    for i in range(rings):
        for j in range(segments):
            j_next = (j + 1) % segments
            v0 = i * segments + j
            v1 = i * segments + j_next
            v2 = (i + 1) * segments + j_next
            v3 = (i + 1) * segments + j
            try:
                bm.faces.new([bm.verts[v0], bm.verts[v1], bm.verts[v2], bm.verts[v3]])
            except (ValueError, IndexError):
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(random.choice(ceramics))
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def make_catenary_arch(name, x, y, z, span, height, thickness=0.8):
    """Catenary arch (inverted hanging chain curve): y = a*cosh(x/a).

    Gaudí used inverted catenary curves because they are pure compression
    structures — no bending moment, purely compressive forces.
    """
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()

    n_pts = 32
    a = height / (math.cosh(span / (2 * height)) - 1)  # solve for catenary parameter

    # Generate catenary profile points
    profile = []
    for i in range(n_pts + 1):
        t = i / n_pts  # 0..1
        px = (t - 0.5) * span
        # Inverted catenary: highest at center
        pz = height - a * (math.cosh(px / a) - 1)
        profile.append((px, pz))

    # Extrude along depth
    depths = [-thickness / 2, thickness / 2]
    for d_idx, depth in enumerate(depths):
        for px, pz in profile:
            bm.verts.new((x + px, y + depth, z + pz))

    bm.verts.ensure_lookup_table()
    n = n_pts + 1
    for i in range(n_pts):
        v0 = i
        v1 = i + 1
        v2 = n + i + 1
        v3 = n + i
        bm.faces.new([bm.verts[v0], bm.verts[v1], bm.verts[v2], bm.verts[v3]])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def make_tree_column(name, x, y, height, n_branches=6):
    """Gaudí's tree-columns: trunk splits into hyperbolic paraboloid branches.

    The columns in the nave are designed to distribute weight like tree trunks
    splitting into branches, with each branch angle calculated so that the
    forces flow naturally downward.
    """
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()

    # Trunk (double-twisted column)
    trunk_h = height * 0.65
    trunk_r = 1.2
    segments = 16
    rings = 20

    for i in range(rings + 1):
        t = i / rings
        z = t * trunk_h
        # Gaudí's columns are often star-shaped in cross-section
        # that transitions from square base to octagon to circle
        n_sides = int(4 + t * 12)  # 4 at base → 16 at top
        n_sides = min(n_sides, segments)
        r = trunk_r * (1 - t * 0.15)  # slight taper
        twist = t * PI * 0.5  # gentle twist

        for j in range(segments):
            theta = TAU * j / segments + twist
            # Star shape modulation (decreases with height)
            star = 0.15 * math.cos(theta * 8) * (1 - t)
            rr = r + star
            px = rr * math.cos(theta) + x
            py = rr * math.sin(theta) + y
            bm.verts.new((px, py, z))

    # Connect trunk faces
    bm.verts.ensure_lookup_table()
    for i in range(rings):
        for j in range(segments):
            j_next = (j + 1) % segments
            v0 = i * segments + j
            v1 = i * segments + j_next
            v2 = (i + 1) * segments + j_next
            v3 = (i + 1) * segments + j
            bm.faces.new([bm.verts[v0], bm.verts[v1], bm.verts[v2], bm.verts[v3]])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    # Tree column material: polished stone
    col_mat = bpy.data.materials.new(f"{name}_mat")
    col_mat.use_nodes = True
    bsdf = col_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.65, 0.58, 0.48, 1)
    bsdf.inputs["Roughness"].default_value = 0.35
    obj.data.materials.append(col_mat)

    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Branches (cones angled outward)
    branch_z = trunk_h * 0.85
    for b in range(n_branches):
        angle = TAU * b / n_branches + random.uniform(-0.1, 0.1)
        bx = x + 2.5 * math.cos(angle)
        by = y + 2.5 * math.sin(angle)
        bpy.ops.mesh.primitive_cone_add(
            radius1=0.6, radius2=0.15, depth=height * 0.35, location=(bx, by, branch_z + height * 0.15)
        )
        br = bpy.context.active_object
        br.name = f"{name}_branch_{b}"
        # Tilt outward
        br.rotation_euler = (0.4 * math.sin(angle), -0.4 * math.cos(angle), angle)
        br.data.materials.append(col_mat)

    return obj


# ════════════════════════════════════════════════════════
# CONSTRUCT THE BASILICA
# ════════════════════════════════════════════════════════

# ── Nave body ────────────────────────────────────���─────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, NAVE_H / 2))
nave = bpy.context.active_object
nave.name = "Nave"
nave.scale = (NAVE_L / 2, NAVE_W / 2, NAVE_H / 2)
nave.data.materials.append(sandstone)

# Apse (half-cylinder)
bpy.ops.mesh.primitive_cylinder_add(
    radius=NAVE_W / 2 + 2, depth=NAVE_H, location=(-NAVE_L / 2 + 5, 0, NAVE_H / 2), vertices=48
)
apse = bpy.context.active_object
apse.name = "Apse"
apse.scale = (0.4, 1, 1)
apse.data.materials.append(sandstone)

# Vault roof (parabolic approximation with elongated sphere)
bpy.ops.mesh.primitive_uv_sphere_add(radius=NAVE_W / 2, segments=48, ring_count=24, location=(0, 0, NAVE_H))
vault = bpy.context.active_object
vault.name = "ParabolicVault"
vault.scale = (NAVE_L / NAVE_W, 1, 0.4)
vault.data.materials.append(sandstone)


# ── Towers ─────────────────────────────────────────────

# Jesus tower (center, tallest)
make_hyperboloid_tower("Tower_Jesus", 0, 0, TOTAL_H_JESUS, 7.0, top_r_factor=0.15, twist_turns=3, segments=36, rings=60)
make_pinnacle("Pinnacle_Jesus", 0, 0, TOTAL_H_JESUS, 15, style="mitre")

# Cross on top
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H_JESUS + 15 + 4))
cx = bpy.context.active_object
cx.name = "Cross_V"
cx.scale = (0.4, 0.4, 4)
cx.data.materials.append(gold)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H_JESUS + 15 + 6))
ch = bpy.context.active_object
ch.name = "Cross_H"
ch.scale = (2.5, 0.4, 0.4)
ch.data.materials.append(gold)

# Mary tower
make_hyperboloid_tower("Tower_Mary", -32, 0, 138, 6.0, top_r_factor=0.2, twist_turns=2.5, segments=32, rings=50)
make_pinnacle("Pinnacle_Mary", -32, 0, 138, 12, style="grape")

# 4 Evangelist towers
evang_pos = [(15, 15), (15, -15), (-15, 15), (-15, -15)]
for i, (ex, ey) in enumerate(evang_pos):
    h = 130 + random.uniform(-3, 3)
    make_hyperboloid_tower(f"Tower_Evang_{i}", ex, ey, h, 5.5, top_r_factor=0.22, twist_turns=2, segments=28, rings=45)
    make_pinnacle(f"Pin_Evang_{i}", ex, ey, h, 10, style="mitre" if i % 2 == 0 else "grape")

# 8 Apostle towers (4 per facade)
# Nativity facade (+Y)
for i in range(4):
    ax = -10 + i * 8
    ay = NAVE_W / 2 + 5
    h = random.uniform(98, 110)
    make_hyperboloid_tower(
        f"Tower_Apost_N{i}", ax, ay, h, 4.8, top_r_factor=0.28, twist_turns=2.5, segments=24, rings=40
    )
    make_pinnacle(f"Pin_Apost_N{i}", ax, ay, h, 8, style="grape")

# Passion facade (-Y)
for i in range(4):
    ax = -10 + i * 8
    ay = -NAVE_W / 2 - 5
    h = random.uniform(98, 110)
    make_hyperboloid_tower(f"Tower_Apost_S{i}", ax, ay, h, 4.8, top_r_factor=0.28, twist_turns=2, segments=24, rings=40)
    make_pinnacle(f"Pin_Apost_S{i}", ax, ay, h, 8, style="mitre")


# ── Facades ────────────────────────────────────────────

# Nativity facade: organic, nature-inspired relief
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, NAVE_W / 2 + 2, NAVE_H * 0.5))
nat = bpy.context.active_object
nat.name = "Facade_Nativity"
nat.scale = (20, 2, NAVE_H * 0.5)
nat.data.materials.append(sandstone)

# Sculptural elements (organic blobs representing figures/foliage)
for _ in range(40):
    sx = random.uniform(-12, 18)
    sz = random.uniform(3, NAVE_H * 0.85)
    sr = random.uniform(0.5, 2.0)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=sr, subdivisions=2, location=(sx, NAVE_W / 2 + 4, sz))
    sc = bpy.context.active_object
    sc.name = "Sculpture_Nat"
    sc.scale = (random.uniform(0.6, 1.2), 0.3, random.uniform(0.8, 1.5))
    sc.data.materials.append(sandstone)

# Passion facade: angular, skeletal
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, -NAVE_W / 2 - 2, NAVE_H * 0.45))
pas = bpy.context.active_object
pas.name = "Facade_Passion"
pas.scale = (20, 2, NAVE_H * 0.45)
pas.data.materials.append(sandstone)

# Angular bone-columns (tilted, austere)
for i in range(6):
    cx = -8 + i * 5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, -NAVE_W / 2 - 5, NAVE_H * 0.3))
    bone = bpy.context.active_object
    bone.name = f"BoneColumn_{i}"
    bone.scale = (0.6, 0.6, NAVE_H * 0.3)
    bone.rotation_euler = (random.uniform(-0.08, 0.08), random.uniform(-0.15, 0.15), 0)
    bone.data.materials.append(bronze)

# Glory facade (main entrance, east +X)
bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 3, 0, NAVE_H * 0.5))
glory = bpy.context.active_object
glory.name = "Facade_Glory"
glory.scale = (3, NAVE_W * 0.45, NAVE_H * 0.5)
glory.data.materials.append(sandstone)


# ���─ Stained Glass ──────────────────────────────────────

# Nativity side (warm: red/orange/gold = sunrise)
for i in range(12):
    wx = -NAVE_L * 0.4 + i * (NAVE_L * 0.8) / 11
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, NAVE_W / 2 + 0.5, NAVE_H * 0.55))
    win = bpy.context.active_object
    win.name = f"Glass_Warm_{i}"
    win.scale = (2.2, 0.05, 7)
    win.data.materials.append(glass_warm)

# Passion side (cool: blue/green/purple = sunset)
for i in range(12):
    wx = -NAVE_L * 0.4 + i * (NAVE_L * 0.8) / 11
    bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, -NAVE_W / 2 - 0.5, NAVE_H * 0.55))
    win = bpy.context.active_object
    win.name = f"Glass_Cool_{i}"
    win.scale = (2.2, 0.05, 7)
    win.data.materials.append(glass_cool)

# Rose window (Glory facade)
bpy.ops.mesh.primitive_cylinder_add(radius=9, depth=0.3, vertices=64, location=(NAVE_L / 2 + 6.5, 0, NAVE_H * 0.7))
rose = bpy.context.active_object
rose.name = "RoseWindow"
rose.rotation_euler = (0, PI / 2, 0)
rose.data.materials.append(glass_warm)

# Rose window frame rings
for r_scale in [0.7, 0.45, 0.2]:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=9 * r_scale, minor_radius=0.25, location=(NAVE_L / 2 + 6.6, 0, NAVE_H * 0.7)
    )
    ring = bpy.context.active_object
    ring.name = "Rose_Frame"
    ring.rotation_euler = (0, PI / 2, 0)
    ring.data.materials.append(gold)


# ── Tree Columns (interior) ────────────────────────────

for row in range(5):
    for col in range(2):
        cx = -NAVE_L * 0.3 + row * (NAVE_L * 0.55) / 4
        cy = -8 + col * 16
        make_tree_column(f"TreeCol_{row}_{col}", cx, cy, NAVE_H * 0.85, n_branches=5)


# ── Catenary Arches ────────────────────────────────────

for i in range(6):
    ax = -NAVE_L * 0.35 + i * (NAVE_L * 0.6) / 5
    make_catenary_arch(f"Arch_{i}", ax, 0, 0, NAVE_W * 0.8, NAVE_H * 0.9, thickness=1.2)


# ── Flying Buttresses ──────────────────────────────────

for side in [1, -1]:
    for i in range(7):
        bx = -NAVE_L * 0.35 + i * (NAVE_L * 0.65) / 6
        by = side * (NAVE_W / 2 + 6)
        # Arch
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, NAVE_H * 0.6))
        fb = bpy.context.active_object
        fb.name = "FlyingButtress"
        fb.scale = (1.0, 6, 1.5)
        fb.rotation_euler = (side * 0.35, 0, 0)
        fb.data.materials.append(sandstone)
        # Pier
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, side * (NAVE_W / 2 + 11), NAVE_H * 0.35))
        pier = bpy.context.active_object
        pier.name = "Buttress_Pier"
        pier.scale = (1.0, 1.0, NAVE_H * 0.35)
        pier.data.materials.append(sandstone)
        # Pinnacle on pier
        bpy.ops.mesh.primitive_cone_add(
            radius1=1.2, radius2=0, depth=5, location=(bx, side * (NAVE_W / 2 + 11), NAVE_H * 0.7 + 2)
        )
        pin = bpy.context.active_object
        pin.name = "Buttress_Pin"
        pin.data.materials.append(sandstone)


# ════════════════════════════════════════════════════════
# ENVIRONMENT
# ════════════════════════════════════════════════════════

# Plaza
bpy.ops.mesh.primitive_plane_add(size=350, location=(0, 0, -0.1))
ground = bpy.context.active_object
ground.name = "Plaza"
ground.data.materials.append(plaza)

# Reflecting pool
water_mat = bpy.data.materials.new("Water")
water_mat.use_nodes = True
wn = water_mat.node_tree.nodes
wl = water_mat.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputMaterial")
bsdf = wn.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.02, 0.08, 0.18, 1)
bsdf.inputs["Roughness"].default_value = 0.005
bsdf.inputs["Metallic"].default_value = 0.0
if "Transmission Weight" in bsdf.inputs:
    bsdf.inputs["Transmission Weight"].default_value = 0.6
bsdf.inputs["IOR"].default_value = 1.33
wl.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 30, 0, -0.15))
pool = bpy.context.active_object
pool.name = "ReflectingPool"
pool.scale = (20, 12, 0.15)
pool.data.materials.append(water_mat)

# Trees (Mediterranean cypress + plane trees)
tree_mat = bpy.data.materials.new("MediterraneanTree")
tree_mat.use_nodes = True
tree_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.22, 0.05, 1)
tree_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8

bark_mat = bpy.data.materials.new("Bark")
bark_mat.use_nodes = True
bark_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.18, 0.12, 0.06, 1)
bark_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

for i in range(25):
    angle = random.uniform(0, TAU)
    dist = random.uniform(60, 140)
    tx = dist * math.cos(angle)
    ty = dist * math.sin(angle)
    h = random.uniform(10, 18)
    # Cypress (tall narrow)
    if random.random() < 0.4:
        bpy.ops.mesh.primitive_cone_add(radius1=1.5, radius2=0.3, depth=h, location=(tx, ty, h / 2))
    else:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=random.uniform(3, 5), subdivisions=2, location=(tx, ty, h * 0.6))
    tree = bpy.context.active_object
    tree.name = "Tree"
    tree.data.materials.append(tree_mat)
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=h * 0.4, location=(tx, ty, h * 0.2))
    tr = bpy.context.active_object
    tr.name = "Trunk"
    tr.data.materials.append(bark_mat)


# ════════════════════════════════════════════════════════
# LIGHTING & ATMOSPHERE
# ════════════════════════════════════════════════════════

# Golden hour sun (Barcelona afternoon)
bpy.ops.object.light_add(type="SUN", location=(80, -40, 100))
sun = bpy.context.active_object
sun.name = "GoldenSun"
sun.data.energy = 6.0
sun.data.color = (1.0, 0.88, 0.65)
sun.data.angle = math.radians(1.5)  # sharp shadows
sun.rotation_euler = (math.radians(58), math.radians(8), math.radians(240))

# Blue sky bounce
bpy.ops.object.light_add(type="AREA", location=(-80, 60, 90))
fill = bpy.context.active_object
fill.name = "SkyBounce"
fill.data.energy = 150
fill.data.size = 60
fill.data.color = (0.65, 0.78, 1.0)

# World: Barcelona golden hour sky
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputWorld")
bg = wn.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.5
coord = wn.new("ShaderNodeTexCoord")
mapping = wn.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (PI / 2, 0, 0)
grad = wn.new("ShaderNodeTexGradient")
grad.gradient_type = "QUADRATIC_SPHERE"
cr = wn.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.0
cr.color_ramp.elements[0].color = (0.05, 0.12, 0.35, 1)  # deep zenith
cr.color_ramp.elements[1].position = 0.35
cr.color_ramp.elements[1].color = (0.25, 0.45, 0.75, 1)  # blue
e1 = cr.color_ramp.elements.new(0.65)
e1.color = (0.65, 0.55, 0.40, 1)  # warm mid
e2 = cr.color_ramp.elements.new(0.85)
e2.color = (0.95, 0.65, 0.30, 1)  # orange horizon
e3 = cr.color_ramp.elements.new(0.95)
e3.color = (0.98, 0.80, 0.50, 1)  # golden glow
wl.new(coord.outputs["Generated"], mapping.inputs["Vector"])
wl.new(mapping.outputs["Vector"], grad.inputs["Vector"])
wl.new(grad.outputs["Fac"], cr.inputs["Fac"])
wl.new(cr.outputs["Color"], bg.inputs["Color"])
wl.new(bg.outputs["Background"], out.inputs["Surface"])


# ════════════════════════════════════════════════════════
# CAMERA
# ════════════════════════════════════════════════════════

# Dramatic low angle from plaza, looking up at towers
cam_loc = Vector((85, -55, 25))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.name = "SagradaCam_Main"
target = Vector((0, 0, TOTAL_H_JESUS * 0.45))
direction = target - cam_loc
rot = direction.to_track_quat("-Z", "Y")
cam.rotation_euler = rot.to_euler()
cam.data.lens = 20  # wide angle for dramatic perspective
cam.data.clip_end = 1000
bpy.context.scene.camera = cam

# Render settings
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.render.resolution_x = 2560
scene.render.resolution_y = 1440
scene.render.film_transparent = False
# Color management
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except (TypeError, RuntimeError):
    pass

# ── Result ─────────────────────────────────────────────
obj_count = len(bpy.data.objects)
mat_count = len(bpy.data.materials)
vert_count = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH")
result = f"Sagrada Familia v2: {obj_count} objects, {mat_count} materials, {vert_count:,} vertices"
print(result)
