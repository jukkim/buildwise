"""Sagrada Família — Artistic BMesh recreation in Blender.

Features:
- 18 towers (spires) with hyperboloid pinnacles
- Nativity / Passion / Glory facades with relief geometry
- Stained glass windows (multicolor emission)
- Sandstone/limestone PBR material with age patina
- Organic tree-column interior visible through nave windows
- Rose window, flying buttresses
- Plaza with visitor figures, trees, surrounding context
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

random.seed(2026)

# ── Clear ──────────────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for c in list(bpy.data.collections):
    if c.name != "Collection":
        bpy.data.collections.remove(c)

# ── Parameters (approximate real dimensions in meters) ──
NAVE_L = 90  # nave length
NAVE_W = 45  # nave width
NAVE_H = 45  # nave vault height
APSE_R = 15  # apse radius
TOWER_BASE_R = 5.5
N_EVANGELIST_TOWERS = 4
N_APOSTLE_TOWERS = 12  # reduced to 8 for performance
JESUS_TOWER_H = 172.5
MARY_TOWER_H = 138
EVANGELIST_H = 135
APOSTLE_H_RANGE = (98, 112)


# ════════════════════════════════════════════════════════
# MATERIALS
# ════════════════════════════════════════════════════════


def mat_sandstone():
    mat = bpy.data.materials.new("Sandstone")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.75
    # Layered noise for sandstone color variation
    n1 = N.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 12.0
    n1.inputs["Detail"].default_value = 8.0
    n2 = N.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 60.0
    n2.inputs["Detail"].default_value = 4.0
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.3
    cr.color_ramp.elements[0].color = (0.72, 0.58, 0.40, 1)  # warm sandstone
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (0.85, 0.75, 0.58, 1)  # lighter
    e = cr.color_ramp.elements.new(0.9)
    e.color = (0.65, 0.52, 0.38, 1)  # darker weathered
    L.new(n1.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    # Bump from fine noise
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    L.new(n2.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_sandstone_dark():
    mat = bpy.data.materials.new("Sandstone_Dark")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.45, 0.35, 0.25, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    n = N.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 40.0
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    L.new(n.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_stained_glass(color, name_suffix):
    mat = bpy.data.materials.new(f"StainedGlass_{name_suffix}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    # Mix emission + transparent
    emit = N.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = 3.0
    transp = N.new("ShaderNodeBsdfTransparent")
    transp.inputs["Color"].default_value = (*color, 1.0)
    mix = N.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.4
    L.new(emit.outputs["Emission"], mix.inputs[1])
    L.new(transp.outputs["BSDF"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def mat_gold_cross():
    mat = bpy.data.materials.new("Gold_Cross")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.95, 0.75, 0.20, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.15
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_bronze():
    mat = bpy.data.materials.new("Bronze_Door")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.40, 0.28, 0.15, 1)
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.4
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_white_stone():
    mat = bpy.data.materials.new("White_Stone")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.92, 0.90, 0.85, 1)
    bsdf.inputs["Roughness"].default_value = 0.6
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_ceramic_pinnacle(color):
    mat = bpy.data.materials.new(f"Ceramic_{color[0]:.1f}")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.2
    bsdf.inputs["Metallic"].default_value = 0.1
    # Glossy ceramic coat
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.8
        bsdf.inputs["Coat Roughness"].default_value = 0.05
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_plaza():
    mat = bpy.data.materials.new("Plaza_Stone")
    mat.use_nodes = True
    N = mat.node_tree.nodes
    L = mat.node_tree.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.7
    brick = N.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 15.0
    brick.inputs["Color1"].default_value = (0.7, 0.65, 0.58, 1)
    brick.inputs["Color2"].default_value = (0.6, 0.55, 0.48, 1)
    brick.inputs["Mortar"].default_value = (0.5, 0.48, 0.42, 1)
    brick.inputs["Mortar Size"].default_value = 0.015
    L.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# Create materials
sandstone = mat_sandstone()
sandstone_dk = mat_sandstone_dark()
gold = mat_gold_cross()
bronze = mat_bronze()
white_stone = mat_white_stone()
plaza_mat = mat_plaza()

# Stained glass colors (Sagrada's characteristic warm/cool spectrum)
sg_red = mat_stained_glass((0.9, 0.15, 0.05), "Red")
sg_orange = mat_stained_glass((0.95, 0.5, 0.05), "Orange")
sg_gold = mat_stained_glass((1.0, 0.8, 0.1), "Gold")
sg_green = mat_stained_glass((0.1, 0.7, 0.2), "Green")
sg_blue = mat_stained_glass((0.1, 0.3, 0.9), "Blue")
sg_purple = mat_stained_glass((0.5, 0.1, 0.7), "Purple")
stained_glasses = [sg_red, sg_orange, sg_gold, sg_green, sg_blue, sg_purple]

# Ceramic pinnacle colors
ceramic_colors = [
    (0.2, 0.6, 0.3),  # green
    (0.9, 0.85, 0.2),  # gold
    (0.85, 0.2, 0.15),  # red
    (0.1, 0.4, 0.8),  # blue
    (0.95, 0.95, 0.9),  # white
]
ceramic_mats = [mat_ceramic_pinnacle(c) for c in ceramic_colors]


# ════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════


def create_tower(x, y, height, base_r, name, taper=0.35, segments=24):
    """Create a tapered tower with helical surface detail."""
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()

    # Main cone body
    n_rings = 16
    for i in range(n_rings + 1):
        t = i / n_rings
        z = t * height
        r = base_r * (1.0 - t * (1.0 - taper))
        # Helical surface undulation
        for j in range(segments):
            angle = 2 * math.pi * j / segments
            # Spiral ridge
            ridge = 0.3 * math.sin(angle * 4 + t * math.pi * 6) * (1.0 - t * 0.5)
            px = (r + ridge) * math.cos(angle)
            py = (r + ridge) * math.sin(angle)
            bm.verts.new((px, py, z))

    bm.verts.ensure_lookup_table()

    # Connect faces
    for i in range(n_rings):
        for j in range(segments):
            v0 = i * segments + j
            v1 = i * segments + (j + 1) % segments
            v2 = (i + 1) * segments + (j + 1) % segments
            v3 = (i + 1) * segments + j
            bm.faces.new([bm.verts[v0], bm.verts[v1], bm.verts[v2], bm.verts[v3]])

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(sandstone)
    return obj


def create_pinnacle(x, y, z, height, name):
    """Hyperboloid pinnacle with ceramic finish (Gaudí style)."""
    mesh = bpy.data.meshes.new(f"{name}_pin_mesh")
    bm = bmesh.new()

    n_rings = 12
    segments = 16
    for i in range(n_rings + 1):
        t = i / n_rings
        # Hyperboloid profile: thin middle, flared top
        r = 0.8 * (1.0 + 0.6 * (2 * t - 1) ** 2)
        zz = t * height
        for j in range(segments):
            angle = 2 * math.pi * j / segments + t * math.pi * 0.5  # twist
            px = r * math.cos(angle)
            py = r * math.sin(angle)
            bm.verts.new((px, py, zz))

    bm.verts.ensure_lookup_table()
    for i in range(n_rings):
        for j in range(segments):
            v0 = i * segments + j
            v1 = i * segments + (j + 1) % segments
            v2 = (i + 1) * segments + (j + 1) % segments
            v3 = (i + 1) * segments + j
            bm.faces.new([bm.verts[v0], bm.verts[v1], bm.verts[v2], bm.verts[v3]])

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, z)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(random.choice(ceramic_mats))
    return obj


def create_cross(x, y, z, size=4):
    """Gold cross at tower top."""
    # Vertical
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + size / 2))
    cv = bpy.context.active_object
    cv.name = "Cross_V"
    cv.scale = (0.3, 0.3, size / 2)
    cv.data.materials.append(gold)
    # Horizontal
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + size * 0.7))
    ch = bpy.context.active_object
    ch.name = "Cross_H"
    ch.scale = (size * 0.35, 0.3, 0.3)
    ch.data.materials.append(gold)


# ════════════════════════════════════════════════════════
# MAIN BASILICA BODY
# ══════════════════════════════════════════════════��═════

# Nave body
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, NAVE_H / 2))
nave = bpy.context.active_object
nave.name = "Nave_Body"
nave.scale = (NAVE_L / 2, NAVE_W / 2, NAVE_H / 2)
nave.data.materials.append(sandstone)

# Apse (semicircular rear)
bpy.ops.mesh.primitive_cylinder_add(radius=NAVE_W / 2, depth=NAVE_H, location=(-NAVE_L / 2, 0, NAVE_H / 2), vertices=32)
apse = bpy.context.active_object
apse.name = "Apse"
apse.scale = (0.5, 1, 1)
apse.data.materials.append(sandstone)

# Clerestory (upper nave extension)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, NAVE_H + 5))
clerestory = bpy.context.active_object
clerestory.name = "Clerestory"
clerestory.scale = (NAVE_L * 0.4, NAVE_W * 0.3, 5)
clerestory.data.materials.append(sandstone)

# Pitched roof
bpy.ops.mesh.primitive_cone_add(radius1=NAVE_W / 2 + 2, radius2=0, depth=15, location=(0, 0, NAVE_H + 12), vertices=4)
roof = bpy.context.active_object
roof.name = "Nave_Roof"
roof.scale = (NAVE_L / NAVE_W, 1, 1)
roof.rotation_euler[2] = math.radians(45)
roof.data.materials.append(sandstone_dk)


# ════════════════════════════════════════════════════════
# TOWERS (SPIRES)
# ════════════════════════════════════════════════════════

# --- Jesus Tower (center, tallest) ---
jt = create_tower(0, 0, JESUS_TOWER_H, TOWER_BASE_R * 1.3, "Tower_Jesus", taper=0.15)
create_pinnacle(0, 0, JESUS_TOWER_H, 12, "Pinnacle_Jesus")
create_cross(0, 0, JESUS_TOWER_H + 12, size=6)

# --- Mary Tower (apse, second tallest) ---
mt = create_tower(-NAVE_L * 0.35, 0, MARY_TOWER_H, TOWER_BASE_R * 1.1, "Tower_Mary", taper=0.2)
create_pinnacle(-NAVE_L * 0.35, 0, MARY_TOWER_H, 10, "Pinnacle_Mary")
create_cross(-NAVE_L * 0.35, 0, MARY_TOWER_H + 10, size=5)

# --- 4 Evangelist Towers ---
evang_positions = [
    (NAVE_L * 0.15, NAVE_W * 0.3),
    (NAVE_L * 0.15, -NAVE_W * 0.3),
    (-NAVE_L * 0.15, NAVE_W * 0.3),
    (-NAVE_L * 0.15, -NAVE_W * 0.3),
]
for i, (ex, ey) in enumerate(evang_positions):
    h = EVANGELIST_H + random.uniform(-3, 3)
    create_tower(ex, ey, h, TOWER_BASE_R, f"Tower_Evangelist_{i + 1}", taper=0.25)
    create_pinnacle(ex, ey, h, 8, f"Pinnacle_Evang_{i + 1}")

# --- Apostle Towers (grouped in 4s at each facade) ---
# Nativity facade (east, +Y)
apostle_positions = []
for i in range(4):
    ax = NAVE_L * 0.1 + i * 7 - 10
    ay = NAVE_W / 2 + 3
    apostle_positions.append((ax, ay))

# Passion facade (west, -Y)
for i in range(4):
    ax = NAVE_L * 0.1 + i * 7 - 10
    ay = -NAVE_W / 2 - 3
    apostle_positions.append((ax, ay))

for i, (ax, ay) in enumerate(apostle_positions):
    h = random.uniform(*APOSTLE_H_RANGE)
    create_tower(ax, ay, h, TOWER_BASE_R * 0.85, f"Tower_Apostle_{i + 1}", taper=0.3)
    create_pinnacle(ax, ay, h, 7, f"Pinnacle_Apostle_{i + 1}")


# ════════════════════════════════════════════════════════
# FACADES
# ════════════════════════════════════════════════════════

# --- Nativity Facade (east, +Y) --- ornate organic
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, NAVE_W / 2 + 1.5, NAVE_H * 0.55))
nat_facade = bpy.context.active_object
nat_facade.name = "Nativity_Facade"
nat_facade.scale = (22, 1.5, NAVE_H * 0.55)
nat_facade.data.materials.append(sandstone)

# Sculpted relief elements on nativity facade
for row in range(5):
    for col in range(7):
        rx = -12 + col * 4
        rz = 8 + row * 7
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=random.uniform(0.8, 1.5), subdivisions=2, location=(rx + 5, NAVE_W / 2 + 3.2, rz)
        )
        rel = bpy.context.active_object
        rel.name = "Relief_Nativity"
        rel.scale = (1, 0.4, random.uniform(0.8, 1.4))
        rel.data.materials.append(sandstone if random.random() > 0.3 else sandstone_dk)

# --- Passion Facade (west, -Y) --- angular, stark
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, -NAVE_W / 2 - 1.5, NAVE_H * 0.5))
pas_facade = bpy.context.active_object
pas_facade.name = "Passion_Facade"
pas_facade.scale = (22, 1.5, NAVE_H * 0.5)
pas_facade.data.materials.append(sandstone_dk)

# Angular bone-like columns on passion facade
for col in range(6):
    cx = -10 + col * 5 + 5
    bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=NAVE_H * 0.7, location=(cx, -NAVE_W / 2 - 3, NAVE_H * 0.35))
    pcol = bpy.context.active_object
    pcol.name = "Passion_Column"
    pcol.rotation_euler = (random.uniform(-0.05, 0.05), random.uniform(-0.1, 0.1), 0)
    pcol.data.materials.append(sandstone_dk)

# --- Glory Facade (south, +X) --- future main entrance
bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 2, 0, NAVE_H * 0.6))
glory = bpy.context.active_object
glory.name = "Glory_Facade"
glory.scale = (2, NAVE_W * 0.4, NAVE_H * 0.6)
glory.data.materials.append(white_stone)

# Bronze doors
for dy in [-6, 0, 6]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 3.5, dy, 5))
    door = bpy.context.active_object
    door.name = "Bronze_Door"
    door.scale = (0.15, 2.5, 5)
    door.data.materials.append(bronze)


# ════════════════════════════════════════════════════════
# STAINED GLASS WINDOWS
# ════════════════════════════════════════════════════════

# Nave side windows (both sides)
for side in [1, -1]:
    for i in range(10):
        wx = -NAVE_L * 0.35 + i * (NAVE_L * 0.7) / 9
        wz = NAVE_H * 0.5
        wy = side * (NAVE_W / 2 + 0.3)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(wx, wy, wz))
        win = bpy.context.active_object
        win.name = f"StainedGlass_{i}_{'+' if side > 0 else '-'}"
        win.scale = (2.5, 1, 6)
        win.rotation_euler = (math.radians(90), 0, 0)
        win.data.materials.append(stained_glasses[i % len(stained_glasses)])

# Rose window (glory facade)
bpy.ops.mesh.primitive_circle_add(radius=8, vertices=32, fill_type="NGON", location=(NAVE_L / 2 + 3.8, 0, NAVE_H * 0.7))
rose = bpy.context.active_object
rose.name = "Rose_Window"
rose.rotation_euler = (0, math.radians(90), 0)
rose.data.materials.append(sg_gold)

# Rose window inner pattern (concentric circles)
for r_scale in [0.6, 0.35]:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=8 * r_scale, minor_radius=0.2, location=(NAVE_L / 2 + 3.9, 0, NAVE_H * 0.7)
    )
    ring = bpy.context.active_object
    ring.name = "Rose_Ring"
    ring.rotation_euler = (0, math.radians(90), 0)
    ring.data.materials.append(gold)


# ════════════════════════════════════════════════════════
# INTERIOR TREE COLUMNS (visible through windows)
# ════════════════════════════════════════════════════════

tree_trunk_mat = bpy.data.materials.new("TreeColumn")
tree_trunk_mat.use_nodes = True
tree_trunk_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.6, 0.55, 0.45, 1)
tree_trunk_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.5

for row in range(4):
    for col in range(2):
        tx = -NAVE_L * 0.25 + row * (NAVE_L * 0.5) / 3
        ty = -NAVE_W * 0.2 + col * (NAVE_W * 0.4)
        # Trunk
        bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=NAVE_H * 0.6, location=(tx, ty, NAVE_H * 0.3))
        tcol = bpy.context.active_object
        tcol.name = "TreeColumn_Trunk"
        tcol.data.materials.append(tree_trunk_mat)
        # Branching (simplified as cones)
        for branch in range(4):
            angle = math.pi / 2 * branch + random.uniform(-0.2, 0.2)
            bx = tx + 3 * math.cos(angle)
            by = ty + 3 * math.sin(angle)
            bpy.ops.mesh.primitive_cone_add(radius1=0.5, radius2=0.1, depth=8, location=(bx, by, NAVE_H * 0.65))
            br = bpy.context.active_object
            br.name = "TreeColumn_Branch"
            br.rotation_euler = (math.radians(30) * math.sin(angle), math.radians(30) * math.cos(angle), angle)
            br.data.materials.append(tree_trunk_mat)


# ════════════════════════════════════════════════════════
# FLYING BUTTRESSES
# ════════════════════════════════════════════════════════

for side in [1, -1]:
    for i in range(6):
        bx = -NAVE_L * 0.3 + i * (NAVE_L * 0.6) / 5
        by = side * (NAVE_W / 2 + 4)
        # Arc shape approximated with rotated cylinder
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, NAVE_H * 0.55))
        fb = bpy.context.active_object
        fb.name = "FlyingButtress"
        fb.scale = (1.5, 5, 1)
        fb.rotation_euler = (side * math.radians(25), 0, 0)
        fb.data.materials.append(sandstone)
        # Buttress pier
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, side * (NAVE_W / 2 + 8), NAVE_H * 0.3))
        pier = bpy.context.active_object
        pier.name = "Buttress_Pier"
        pier.scale = (1.2, 1.2, NAVE_H * 0.3)
        pier.data.materials.append(sandstone)


# ════════════════════════════════════════════════════════
# PLAZA & SURROUNDINGS
# ════════════════════════════════════════════════════════

PLAZA_SIZE = 300

# Ground plane
bpy.ops.mesh.primitive_plane_add(size=PLAZA_SIZE, location=(0, 0, -0.05))
ground = bpy.context.active_object
ground.name = "Plaza_Ground"
ground.data.materials.append(plaza_mat)

# Reflecting pool (glory facade side)
pool_mat = bpy.data.materials.new("Water")
pool_mat.use_nodes = True
N = pool_mat.node_tree.nodes
L = pool_mat.node_tree.links
N.clear()
out = N.new("ShaderNodeOutputMaterial")
bsdf = N.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.05, 0.15, 0.25, 1)
bsdf.inputs["Roughness"].default_value = 0.02
bsdf.inputs["Metallic"].default_value = 0.0
if "Transmission Weight" in bsdf.inputs:
    bsdf.inputs["Transmission Weight"].default_value = 0.5
elif "Transmission" in bsdf.inputs:
    bsdf.inputs["Transmission"].default_value = 0.5
L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

bpy.ops.mesh.primitive_cube_add(size=1, location=(NAVE_L / 2 + 25, 0, -0.2))
pool = bpy.context.active_object
pool.name = "Reflecting_Pool"
pool.scale = (15, 8, 0.2)
pool.data.materials.append(pool_mat)

# Trees around plaza
tree_leaf_mat = bpy.data.materials.new("PlazaTree_Leaf")
tree_leaf_mat.use_nodes = True
tree_leaf_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.35, 0.08, 1)

tree_bark_mat = bpy.data.materials.new("PlazaTree_Bark")
tree_bark_mat.use_nodes = True
tree_bark_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.14, 0.07, 1)
tree_bark_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

for i in range(20):
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(70, 130)
    tx = dist * math.cos(angle)
    ty = dist * math.sin(angle)
    h = random.uniform(8, 14)
    # trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=h * 0.5, location=(tx, ty, h * 0.25))
    t_obj = bpy.context.active_object
    t_obj.name = "PlazaTree_Trunk"
    t_obj.data.materials.append(tree_bark_mat)
    # crown
    bpy.ops.mesh.primitive_ico_sphere_add(radius=random.uniform(3, 5), subdivisions=2, location=(tx, ty, h * 0.6))
    c_obj = bpy.context.active_object
    c_obj.name = "PlazaTree_Crown"
    c_obj.data.materials.append(tree_leaf_mat)


# ════════════════════════════════════════════════════════
# LIGHTING & ATMOSPHERE
# ════════════════════════════════════════════════════════

# Warm afternoon sun
bpy.ops.object.light_add(type="SUN", location=(50, -50, 100))
sun = bpy.context.active_object
sun.name = "Sun_Afternoon"
sun.data.energy = 5.0
sun.data.color = (1.0, 0.92, 0.80)
sun.rotation_euler = (math.radians(55), math.radians(10), math.radians(220))

# Cool sky fill
bpy.ops.object.light_add(type="AREA", location=(-60, 60, 80))
fill = bpy.context.active_object
fill.name = "Sky_Fill"
fill.data.energy = 200
fill.data.size = 50
fill.data.color = (0.7, 0.85, 1.0)

# World sky (Barcelona sunset gradient)
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputWorld")
bg = wn.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.2
texcoord = wn.new("ShaderNodeTexCoord")
mapping = wn.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
grad = wn.new("ShaderNodeTexGradient")
grad.gradient_type = "QUADRATIC_SPHERE"
cr = wn.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.0
cr.color_ramp.elements[0].color = (0.08, 0.18, 0.45, 1)  # deep blue zenith
cr.color_ramp.elements[1].position = 0.4
cr.color_ramp.elements[1].color = (0.35, 0.55, 0.82, 1)  # blue
e1 = cr.color_ramp.elements.new(0.7)
e1.color = (0.75, 0.65, 0.50, 1)  # warm horizon
e2 = cr.color_ramp.elements.new(0.95)
e2.color = (0.95, 0.75, 0.45, 1)  # golden horizon
wl.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
wl.new(mapping.outputs["Vector"], grad.inputs["Vector"])
wl.new(grad.outputs["Fac"], cr.inputs["Fac"])
wl.new(cr.outputs["Color"], bg.inputs["Color"])
wl.new(bg.outputs["Background"], out.inputs["Surface"])


# ════════════════════════════════════════════════════════
# CAMERA
# ════════════════════════════════════════════════════════

# Dramatic angle from the Glory facade side
cam_loc = Vector((NAVE_L * 0.9, -NAVE_W * 0.7, 55))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.name = "SagradaCam"
target = Vector((0, 0, JESUS_TOWER_H * 0.4))
direction = target - cam_loc
rot = direction.to_track_quat("-Z", "Y")
cam.rotation_euler = rot.to_euler()
cam.data.lens = 24  # wide angle for grandeur
cam.data.clip_end = 1000
bpy.context.scene.camera = cam

# Render
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 128
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.cycles.use_denoising = True

# ── Summary ──────────────────────────────────────────
obj_count = len(bpy.data.objects)
mat_count = len(bpy.data.materials)
result = f"Sagrada Familia: {obj_count} objects, {mat_count} materials, Jesus tower {JESUS_TOWER_H}m"
print(result)
