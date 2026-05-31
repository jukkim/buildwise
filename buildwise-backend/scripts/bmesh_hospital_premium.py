"""BMesh Hospital 5F — Premium version with PBR materials + landscaping.

Enhanced with:
- Realistic glass (blue-tint reflection, Fresnel)
- Concrete panel facade with reveal lines
- Metal frame mullions around windows
- Ground with grass texture, parking lot, access road
- Trees (low-poly stylized), hedges, lamp posts
- HDRI-style sky gradient
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

random.seed(42)

# ── Clear scene ──────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)

# ── Building parameters ──────────────────────────────
FLOORS = 5
FLOOR_HEIGHT = 3.96
TOTAL_AREA = 22422.0
ASPECT = 1.8
PER_FLOOR = TOTAL_AREA / FLOORS
WIDTH = math.sqrt(PER_FLOOR / ASPECT)
LENGTH = PER_FLOOR / WIDTH
WWR = 0.4
WIN_HEIGHT = FLOOR_HEIGHT * WWR
WIN_SILL = (FLOOR_HEIGHT - WIN_HEIGHT) / 2
TOTAL_H = FLOORS * FLOOR_HEIGHT
HX = LENGTH / 2
HY = WIDTH / 2


# ════════════════════════════════════════════════════════
# MATERIALS
# ════════════════════════════════════════════════════════


def make_concrete_facade():
    mat = bpy.data.materials.new("Facade_Concrete")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.92, 0.91, 0.88, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.65
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    # Subtle noise for concrete texture
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 80.0
    noise.inputs["Detail"].default_value = 12.0
    noise.inputs["Roughness"].default_value = 0.6
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    cr = nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.4
    cr.color_ramp.elements[0].color = (0.88, 0.87, 0.85, 1)
    cr.color_ramp.elements[1].position = 0.6
    cr.color_ramp.elements[1].color = (0.95, 0.94, 0.92, 1)
    links.new(noise.outputs["Fac"], cr.inputs["Fac"])
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_glass():
    mat = bpy.data.materials.new("Curtainwall_Glass")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.15, 0.30, 0.45, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.85
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 0.85
    bsdf.inputs["IOR"].default_value = 1.52
    # Fresnel-driven reflectivity
    fresnel = nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.52
    mix = nodes.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = (0.15, 0.30, 0.45, 1.0)
    mix.inputs[2].default_value = (0.7, 0.82, 0.92, 1.0)
    links.new(fresnel.outputs["Fac"], mix.inputs["Fac"])
    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_mullion_metal():
    mat = bpy.data.materials.new("Mullion_Metal")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.12, 0.13, 0.14, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.95
    bsdf.inputs["Roughness"].default_value = 0.25
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_roof():
    mat = bpy.data.materials.new("Roof_Membrane")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.35, 0.37, 0.40, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_ground_grass():
    mat = bpy.data.materials.new("Ground_Grass")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.95
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 25.0
    noise.inputs["Detail"].default_value = 6.0
    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 40.0
    cr = nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.3
    cr.color_ramp.elements[0].color = (0.12, 0.28, 0.08, 1)
    cr.color_ramp.elements[1].position = 0.7
    cr.color_ramp.elements[1].color = (0.22, 0.42, 0.12, 1)
    mix = nodes.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = (0.15, 0.32, 0.08, 1)
    mix.inputs[2].default_value = (0.25, 0.45, 0.15, 1)
    links.new(noise.outputs["Fac"], cr.inputs["Fac"])
    links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    links.new(vor.outputs["Distance"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_asphalt():
    mat = bpy.data.materials.new("Asphalt")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 100.0
    noise.inputs["Detail"].default_value = 10.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_sidewalk():
    mat = bpy.data.materials.new("Sidewalk")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.65, 0.63, 0.60, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    # Brick pattern
    brick = nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 8.0
    brick.inputs["Color1"].default_value = (0.60, 0.58, 0.55, 1)
    brick.inputs["Color2"].default_value = (0.70, 0.68, 0.65, 1)
    brick.inputs["Mortar"].default_value = (0.5, 0.48, 0.45, 1)
    brick.inputs["Mortar Size"].default_value = 0.02
    links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.1
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_tree_trunk():
    mat = bpy.data.materials.new("Tree_Trunk")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.25, 0.15, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_tree_leaves():
    mat = bpy.data.materials.new("Tree_Leaves")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.15, 0.40, 0.10, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    # Subsurface for leaf translucency
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.2
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_parking_line():
    mat = bpy.data.materials.new("Parking_Line")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_lamp_metal():
    mat = bpy.data.materials.new("Lamp_Metal")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.15, 0.15, 0.16, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.3
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# Create all materials
facade_mat = make_concrete_facade()
glass_mat = make_glass()
mullion_mat = make_mullion_metal()
roof_mat = make_roof()
grass_mat = make_ground_grass()
asphalt_mat = make_asphalt()
sidewalk_mat = make_sidewalk()
trunk_mat = make_tree_trunk()
leaves_mat = make_tree_leaves()
parking_line_mat = make_parking_line()
lamp_mat = make_lamp_metal()


# ════════════════════════════════════════════════════════
# BUILDING STRUCTURE
# ════════════════════════════════════════════════════════

# Main body (BMesh)
mesh = bpy.data.meshes.new("Hospital_Mesh")
obj = bpy.data.objects.new("Hospital_5F", mesh)
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
    z = i * FLOOR_HEIGHT
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=(0, 0, z),
        plane_no=(0, 0, 1),
    )

bm.to_mesh(mesh)
bm.free()
obj.data.materials.append(facade_mat)

# ── Windows with mullion frames ─────────────────────────
WIN_THICK = 0.04
MULLION_W = 0.06

for i in range(FLOORS):
    z = i * FLOOR_HEIGHT + WIN_SILL + WIN_HEIGHT / 2
    segments_x = 8
    segments_y = 5
    seg_w_x = (LENGTH * 0.88) / segments_x
    seg_w_y = (WIDTH * 0.88) / segments_y

    for face_dir in ["N", "S", "E", "W"]:
        if face_dir in ("N", "S"):
            n_seg = segments_x
            seg_w = seg_w_x
            total_w = LENGTH * 0.88
        else:
            n_seg = segments_y
            seg_w = seg_w_y
            total_w = WIDTH * 0.88

        for s in range(n_seg):
            offset = -total_w / 2 + seg_w / 2 + s * seg_w

            if face_dir == "N":
                loc = (offset, HY + WIN_THICK / 2, z)
                scale = (seg_w / 2 - MULLION_W, WIN_THICK / 2, WIN_HEIGHT / 2)
            elif face_dir == "S":
                loc = (offset, -HY - WIN_THICK / 2, z)
                scale = (seg_w / 2 - MULLION_W, WIN_THICK / 2, WIN_HEIGHT / 2)
            elif face_dir == "E":
                loc = (HX + WIN_THICK / 2, offset, z)
                scale = (WIN_THICK / 2, seg_w / 2 - MULLION_W, WIN_HEIGHT / 2)
            else:
                loc = (-HX - WIN_THICK / 2, offset, z)
                scale = (WIN_THICK / 2, seg_w / 2 - MULLION_W, WIN_HEIGHT / 2)

            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
            win = bpy.context.active_object
            win.name = f"Glass_F{i + 1}_{face_dir}_{s}"
            win.scale = scale
            win.data.materials.append(glass_mat)

    # Horizontal mullions per floor
    for face_dir in ["N", "S", "E", "W"]:
        if face_dir == "N":
            loc = (0, HY + WIN_THICK, z - WIN_HEIGHT / 2)
            scale = (LENGTH * 0.44, MULLION_W, MULLION_W)
        elif face_dir == "S":
            loc = (0, -HY - WIN_THICK, z - WIN_HEIGHT / 2)
            scale = (LENGTH * 0.44, MULLION_W, MULLION_W)
        elif face_dir == "E":
            loc = (HX + WIN_THICK, 0, z - WIN_HEIGHT / 2)
            scale = (MULLION_W, WIDTH * 0.44, MULLION_W)
        else:
            loc = (-HX - WIN_THICK, 0, z - WIN_HEIGHT / 2)
            scale = (MULLION_W, WIDTH * 0.44, MULLION_W)

        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        mul = bpy.context.active_object
        mul.name = f"Mullion_H_F{i + 1}_{face_dir}"
        mul.scale = scale
        mul.data.materials.append(mullion_mat)

# Vertical mullions
for i in range(FLOORS):
    z_base = i * FLOOR_HEIGHT + WIN_SILL
    for face_dir in ["N", "S", "E", "W"]:
        if face_dir in ("N", "S"):
            n_seg = 9
            total_w = LENGTH * 0.88
        else:
            n_seg = 6
            total_w = WIDTH * 0.88

        for s in range(n_seg + 1):
            offset = -total_w / 2 + s * (total_w / n_seg) if n_seg > 0 else 0

            if face_dir == "N":
                loc = (offset, HY + WIN_THICK, z_base + WIN_HEIGHT / 2)
                scale = (MULLION_W, MULLION_W, WIN_HEIGHT / 2)
            elif face_dir == "S":
                loc = (offset, -HY - WIN_THICK, z_base + WIN_HEIGHT / 2)
                scale = (MULLION_W, MULLION_W, WIN_HEIGHT / 2)
            elif face_dir == "E":
                loc = (HX + WIN_THICK, offset, z_base + WIN_HEIGHT / 2)
                scale = (MULLION_W, MULLION_W, WIN_HEIGHT / 2)
            else:
                loc = (-HX - WIN_THICK, offset, z_base + WIN_HEIGHT / 2)
                scale = (MULLION_W, MULLION_W, WIN_HEIGHT / 2)

            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
            mul = bpy.context.active_object
            mul.name = f"Mullion_V_F{i + 1}_{face_dir}_{s}"
            mul.scale = scale
            mul.data.materials.append(mullion_mat)

# ── Roof ────────────────────────────────────────────────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, TOTAL_H + 0.2))
roof = bpy.context.active_object
roof.name = "Roof_Slab"
roof.scale = (HX + 0.8, HY + 0.8, 0.2)
roof.data.materials.append(roof_mat)

# Roof equipment (HVAC units)
for rx, ry in [(-15, 8), (15, -8), (0, 12), (-20, -10)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(rx, ry, TOTAL_H + 1.2))
    eq = bpy.context.active_object
    eq.name = "Rooftop_HVAC"
    eq.scale = (2.5, 1.5, 1.0)
    eq.data.materials.append(mullion_mat)

# ── Entrance canopy ────────────────────────────────────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -HY - 4, 4.0))
canopy = bpy.context.active_object
canopy.name = "Entrance_Canopy"
canopy.scale = (12, 4, 0.15)
canopy.data.materials.append(mullion_mat)

# Canopy columns
for cx in [-10, -5, 5, 10]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=4, location=(cx, -HY - 4, 2.0))
    col = bpy.context.active_object
    col.name = "Canopy_Column"
    col.data.materials.append(mullion_mat)


# ════════════════════════════════════════════════════════
# LANDSCAPE & ENVIRONMENT
# ════════════════════════════════════════════════════════

SITE_SIZE = max(LENGTH, WIDTH) * 2.5

# ── Ground (grass) ──────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=SITE_SIZE, location=(0, 0, -0.02))
ground = bpy.context.active_object
ground.name = "Ground_Grass"
ground.data.materials.append(grass_mat)

# ── Parking lot (south side) ────────────────────────────
park_w = LENGTH * 0.8
park_d = 20
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -HY - 15 - park_d / 2, 0.01))
parking = bpy.context.active_object
parking.name = "Parking_Lot"
parking.scale = (park_w / 2, park_d / 2, 0.02)
parking.data.materials.append(asphalt_mat)

# Parking lines
for p in range(int(park_w / 3)):
    px = -park_w / 2 + 1.5 + p * 3
    bpy.ops.mesh.primitive_cube_add(size=1, location=(px, -HY - 15 - park_d / 2, 0.03))
    line = bpy.context.active_object
    line.name = f"ParkLine_{p}"
    line.scale = (0.05, park_d * 0.35, 0.01)
    line.data.materials.append(parking_line_mat)

# ── Access road ─────────────────────────────────────────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -HY - 8, 0.005))
road = bpy.context.active_object
road.name = "Access_Road"
road.scale = (SITE_SIZE / 2, 4, 0.01)
road.data.materials.append(asphalt_mat)

# ── Sidewalks ───────────────────────────────────────────
for sy, sw in [(-HY - 3.5, 2), (HY + 3, 2)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, sy, 0.02))
    sw_obj = bpy.context.active_object
    sw_obj.name = "Sidewalk"
    sw_obj.scale = (HX + 10, sw / 2, 0.03)
    sw_obj.data.materials.append(sidewalk_mat)


# ── Trees ───────────────────────────────────────────────
def create_tree(x, y, height=8, crown_r=3.5):
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=height * 0.5, location=(x, y, height * 0.25))
    trunk = bpy.context.active_object
    trunk.name = "Tree_Trunk"
    trunk.data.materials.append(trunk_mat)
    # Crown (icosphere)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=crown_r, subdivisions=2, location=(x, y, height * 0.65))
    crown = bpy.context.active_object
    crown.name = "Tree_Crown"
    crown.scale = (1.0, 1.0, 1.2)
    crown.data.materials.append(leaves_mat)


# Tree row along east side
for t in range(8):
    ty = -HY + 6 + t * (WIDTH - 12) / 7
    create_tree(HX + 8, ty, height=random.uniform(7, 10), crown_r=random.uniform(3, 4.5))

# Tree row along west side
for t in range(6):
    ty = -HY + 8 + t * (WIDTH - 16) / 5
    create_tree(-HX - 8, ty, height=random.uniform(6, 9), crown_r=random.uniform(2.5, 4))

# Trees in front (south, near parking)
for t in range(5):
    tx = -LENGTH * 0.3 + t * (LENGTH * 0.6) / 4
    create_tree(tx, -HY - 12, height=random.uniform(7, 9), crown_r=random.uniform(3, 4))


# ── Hedges (low box shrubs) ─────────────────────────────
def create_hedge(x, y, length, width=0.8, height=1.2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, height / 2))
    hedge = bpy.context.active_object
    hedge.name = "Hedge"
    hedge.scale = (length / 2, width / 2, height / 2)
    hedge.data.materials.append(leaves_mat)


# Hedge along building perimeter
create_hedge(0, HY + 1.5, LENGTH * 0.6)
create_hedge(0, -HY - 1.5, LENGTH * 0.4)
create_hedge(HX + 1.5, 0, WIDTH * 0.5)
# Rotate side hedge
bpy.context.active_object.rotation_euler[2] = math.radians(90)


# ── Lamp posts ──────────────────────────────────────────
def create_lamp(x, y, height=6):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=height, location=(x, y, height / 2))
    pole = bpy.context.active_object
    pole.name = "Lamp_Pole"
    pole.data.materials.append(lamp_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(x, y, height))
    bulb = bpy.context.active_object
    bulb.name = "Lamp_Bulb"
    bulb_mat = bpy.data.materials.new("Lamp_Emission")
    bulb_mat.use_nodes = True
    nodes = bulb_mat.node_tree.nodes
    links = bulb_mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (1.0, 0.92, 0.7, 1.0)
    emit.inputs["Strength"].default_value = 5.0
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    bulb.data.materials.append(bulb_mat)


# Lamp posts along road
for lx in range(-int(SITE_SIZE / 2) + 10, int(SITE_SIZE / 2), 25):
    create_lamp(lx, -HY - 11, height=6)


# ════════════════════════════════════════════════════════
# LIGHTING & SKY
# ════════════════════════════════════════════════════════

# Sun
bpy.ops.object.light_add(type="SUN", location=(30, -30, 60))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 4.0
sun.data.color = (1.0, 0.96, 0.9)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))

# Ambient fill
bpy.ops.object.light_add(type="AREA", location=(-40, 40, 45))
fill = bpy.context.active_object
fill.name = "Fill_Light"
fill.data.energy = 300
fill.data.size = 30
fill.data.color = (0.85, 0.92, 1.0)

# ── World (gradient sky) ────────────────────────────────
world = bpy.data.worlds.get("World")
if world is None:
    world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()
out = wnodes.new("ShaderNodeOutputWorld")
bg = wnodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.0
# Sky gradient: horizon warm, zenith cool blue
grad = wnodes.new("ShaderNodeTexGradient")
grad.gradient_type = "QUADRATIC_SPHERE"
mapping = wnodes.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
texcoord = wnodes.new("ShaderNodeTexCoord")
cr = wnodes.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.0
cr.color_ramp.elements[0].color = (0.12, 0.35, 0.65, 1)
cr.color_ramp.elements[1].position = 0.5
cr.color_ramp.elements[1].color = (0.55, 0.72, 0.92, 1)
elem = cr.color_ramp.elements.new(1.0)
elem.color = (0.85, 0.9, 0.95, 1)
wlinks.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
wlinks.new(mapping.outputs["Vector"], grad.inputs["Vector"])
wlinks.new(grad.outputs["Fac"], cr.inputs["Fac"])
wlinks.new(cr.outputs["Color"], bg.inputs["Color"])
wlinks.new(bg.outputs["Background"], out.inputs["Surface"])


# ════════════════════════════════════════════════════════
# CAMERA & RENDER
# ════════════════════════════════════════════════════════

cam_loc = Vector((LENGTH * 1.1, -WIDTH * 0.9, TOTAL_H * 0.7))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.name = "BuildingCam"
target = Vector((0, 0, TOTAL_H * 0.35))
direction = target - cam_loc
rot = direction.to_track_quat("-Z", "Y")
cam.rotation_euler = rot.to_euler()
cam.data.lens = 32
cam.data.clip_end = 500
bpy.context.scene.camera = cam

# Render settings
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 128
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.cycles.use_denoising = True

# ── Summary ──────────────────────────────────────────
obj_count = len(bpy.data.objects)
mat_count = len(bpy.data.materials)
result = f"Hospital 5F Premium: {obj_count} objects, {mat_count} materials, {FLOORS} floors, {LENGTH:.1f}x{WIDTH:.1f}m"
print(result)
