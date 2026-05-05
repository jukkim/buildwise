"""BMesh-based Hospital 5F building generation for Blender.

Single mesh with extruded floors, window cutouts, PBR materials, lighting.
Sent to Blender via execute_code over MCP TCP.
"""
import bpy
import bmesh
import math

# ── Clear scene ──────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
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
WIN_MARGIN = 0.3
WIN_SILL = (FLOOR_HEIGHT - WIN_HEIGHT) / 2

# ── Materials ────────────────────────────────────────
def make_concrete_mat():
    mat = bpy.data.materials.new("Hospital_Concrete")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.88, 0.88, 0.86, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.7
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 50.0
    noise.inputs['Detail'].default_value = 8.0
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    out.location = (400, 0)
    bsdf.location = (0, 0)
    noise.location = (-400, -200)
    bump.location = (-200, -200)
    return mat

def make_glass_mat():
    mat = bpy.data.materials.new("Hospital_Glass")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.6, 0.75, 0.85, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.05
    bsdf.inputs['Metallic'].default_value = 0.0
    # Blender 4.x: use Transmission Weight
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = 0.8
    elif 'Transmission' in bsdf.inputs:
        bsdf.inputs['Transmission'].default_value = 0.8
    bsdf.inputs['IOR'].default_value = 1.45
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    out.location = (400, 0)
    bsdf.location = (0, 0)
    return mat

def make_roof_mat():
    mat = bpy.data.materials.new("Hospital_Roof")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.4, 0.42, 0.45, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    out.location = (400, 0)
    bsdf.location = (0, 0)
    return mat

concrete_mat = make_concrete_mat()
glass_mat = make_glass_mat()
roof_mat = make_roof_mat()

# ── Build main structure (BMesh single mesh) ─────────
mesh = bpy.data.meshes.new("Hospital_Mesh")
obj = bpy.data.objects.new("Hospital_5F", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

bm = bmesh.new()

# Create base floor rectangle
hx = LENGTH / 2
hy = WIDTH / 2
total_h = FLOORS * FLOOR_HEIGHT

# Create a box for the entire building
bmesh.ops.create_cube(bm, size=1.0)
# Scale to building dimensions
for v in bm.verts:
    v.co.x *= LENGTH
    v.co.y *= WIDTH
    v.co.z *= total_h
    v.co.z += total_h / 2  # lift to ground

bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# Bisect at each floor level to create edge loops
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

# Assign concrete material
obj.data.materials.append(concrete_mat)

# ── Window planes (glass panels flush with walls) ────
def add_window_strip(name, cx, cy, cz, sx, sy, rot_z=0):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, cz))
    win = bpy.context.active_object
    win.name = name
    win.scale = (sx, sy, 1.0)
    if rot_z != 0:
        win.rotation_euler = (math.pi/2, 0, rot_z)
    else:
        win.rotation_euler = (math.pi/2, 0, 0)
    win.data.materials.append(glass_mat)
    return win

win_count = 0
for i in range(FLOORS):
    z = i * FLOOR_HEIGHT + WIN_SILL + WIN_HEIGHT / 2
    win_w = LENGTH * 0.9
    win_w_side = WIDTH * 0.9

    # North face (Y+)
    add_window_strip(
        f"Win_F{i+1}_N", 0, hy + 0.005, z,
        win_w / 2, WIN_HEIGHT / 2, 0
    )
    # South face (Y-)
    add_window_strip(
        f"Win_F{i+1}_S", 0, -hy - 0.005, z,
        win_w / 2, WIN_HEIGHT / 2, 0
    )
    # East face (X+)
    add_window_strip(
        f"Win_F{i+1}_E", hx + 0.005, 0, z,
        win_w_side / 2, WIN_HEIGHT / 2, math.pi / 2
    )
    # West face (X-)
    add_window_strip(
        f"Win_F{i+1}_W", -hx - 0.005, 0, z,
        win_w_side / 2, WIN_HEIGHT / 2, math.pi / 2
    )
    win_count += 4

# ── Roof slab ────────────────────────────────────────
bpy.ops.mesh.primitive_cube_add(
    size=1,
    location=(0, 0, total_h + 0.15)
)
roof = bpy.context.active_object
roof.name = "Roof_Slab"
roof.scale = (hx + 0.5, hy + 0.5, 0.15)
roof.data.materials.append(roof_mat)

# ── Floor line reveals (thin dark strips) ────────────
reveal_mat = bpy.data.materials.new("Floor_Reveal")
reveal_mat.use_nodes = True
reveal_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)

for i in range(1, FLOORS):
    z = i * FLOOR_HEIGHT
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
    reveal = bpy.context.active_object
    reveal.name = f"FloorReveal_{i}"
    reveal.scale = (hx + 0.05, hy + 0.05, 0.02)
    reveal.data.materials.append(reveal_mat)

# ── Ground plane ─────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=max(LENGTH, WIDTH) * 3, location=(0, 0, -0.01))
ground = bpy.context.active_object
ground.name = "Ground"
ground_mat = bpy.data.materials.new("Ground")
ground_mat.use_nodes = True
ground_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.35, 0.38, 0.32, 1.0)
ground_mat.node_tree.nodes["Principled BSDF"].inputs['Roughness'].default_value = 0.9
ground.data.materials.append(ground_mat)

# ── Lighting ─────────────────────────────────────────
# Sun light
bpy.ops.object.light_add(type='SUN', location=(20, -20, 50))
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))

# Area light (fill)
bpy.ops.object.light_add(type='AREA', location=(-30, 30, 40))
fill = bpy.context.active_object
fill.name = "Fill_Light"
fill.data.energy = 500
fill.data.size = 20

# ── World (sky) ──────────────────────────────────────
world = bpy.data.worlds.get("World")
if world is None:
    world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()
bg = wnodes.new('ShaderNodeBackground')
bg.inputs['Color'].default_value = (0.53, 0.68, 0.85, 1.0)
bg.inputs['Strength'].default_value = 0.8
out = wnodes.new('ShaderNodeOutputWorld')
wlinks.new(bg.outputs['Background'], out.inputs['Surface'])

# ── Camera ───────────────────────────────────────────
bpy.ops.object.camera_add(
    location=(LENGTH * 1.2, -WIDTH * 1.0, total_h * 0.8)
)
cam = bpy.context.active_object
cam.name = "BuildingCam"
# Point at building center
from mathutils import Vector
direction = Vector((0, 0, total_h * 0.4)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
cam.data.lens = 35
bpy.context.scene.camera = cam

# ── Render settings ──────────────────────────────────
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

# ── Summary ──────────────────────────────────────────
obj_count = len(bpy.data.objects)
print(f"Hospital 5F generated: {obj_count} objects, {FLOORS} floors, {LENGTH:.1f}x{WIDTH:.1f}m")
