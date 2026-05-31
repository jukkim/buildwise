"""Test BMesh generation for all 6 DOE building types against live Blender."""

import sys

sys.path.insert(0, ".")

import json
import select
import socket
import time

from app.services.blender.building_gen import bps_to_bmesh_script

BUILDINGS = [
    {"building_type": "small_office", "floors": 1, "floor_area_m2": 511},
    {"building_type": "medium_office", "floors": 3, "floor_area_m2": 4982},
    {"building_type": "large_office", "floors": 12, "floor_area_m2": 46320},
    {"building_type": "standalone_retail", "floors": 1, "floor_area_m2": 2294},
    {"building_type": "primary_school", "floors": 1, "floor_area_m2": 6871},
    {"building_type": "hospital", "floors": 5, "floor_area_m2": 22422},
]


def send_code(code, timeout=60):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("localhost", 9876))
    msg = json.dumps({"type": "execute_code", "params": {"code": code}}) + "\n"
    s.sendall(msg.encode("utf-8"))
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = select.select([s], [], [], 1.0)
        if ready[0]:
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
            try:
                resp = json.loads(buf.decode().strip())
                s.close()
                return resp
            except json.JSONDecodeError:
                continue
    s.close()
    if buf:
        return json.loads(buf.decode().strip())
    raise TimeoutError("No response")


def get_scene_stats():
    code = """import bpy
obj_count = len(bpy.data.objects)
mat_count = len(bpy.data.materials)
mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
main = [o for o in mesh_objs if not o.name.startswith(('Win_', 'Floor', 'Roof', 'Ground'))]
wins = [o for o in mesh_objs if o.name.startswith('Win_')]
main_name = main[0].name if main else 'N/A'
main_dims = main[0].dimensions if main else None
dims_str = f'{main_dims.x:.1f}x{main_dims.y:.1f}x{main_dims.z:.1f}' if main_dims else 'N/A'
print(f'{obj_count}|{mat_count}|{len(wins)}|{main_name}|{dims_str}')
"""
    resp = send_code(code, timeout=10)
    return resp.get("result", {}).get("result", "").strip() if resp.get("status") == "success" else ""


print(
    f"{'Type':<20} {'F':>2} {'Area':>7} {'Obj':>4} {'Mat':>4} {'Win':>4} {'Main':>20} {'Dims':>25} {'Time':>6} Status"
)
print("-" * 110)

passed = 0
failed = 0

for b in BUILDINGS:
    bps = {
        "building": {
            "building_type": b["building_type"],
            "floors": b["floors"],
            "floor_area_m2": b["floor_area_m2"],
        },
        "envelope": {"wwr": 0.4},
    }

    try:
        script = bps_to_bmesh_script(bps)
        t0 = time.time()
        resp = send_code(script, timeout=120)
        dt = time.time() - t0

        if resp.get("status") == "error":
            status = f"FAIL: {resp.get('message', 'unknown')[:40]}"
            failed += 1
            print(
                f"{b['building_type']:<20} {b['floors']:>2} {b['floor_area_m2']:>7.0f}"
                f" {'':>4} {'':>4} {'':>4} {'':>20} {'':>25} {dt:>5.1f}s {status}"
            )
        else:
            stats = get_scene_stats()
            parts = stats.split("|") if stats else []
            if len(parts) >= 5:
                objs, mats, wins, name, dims = parts
                status = "PASS"
                passed += 1
            else:
                objs = mats = wins = name = dims = "?"
                status = "WARN"
                failed += 1
            print(
                f"{b['building_type']:<20} {b['floors']:>2} {b['floor_area_m2']:>7.0f}"
                f" {objs:>4} {mats:>4} {wins:>4} {name:>20} {dims:>25}"
                f" {dt:>5.1f}s {status}"
            )

    except Exception as e:
        failed += 1
        print(
            f"{b['building_type']:<20} {b['floors']:>2} {b['floor_area_m2']:>7.0f}"
            f" {'':>4} {'':>4} {'':>4} {'':>20} {'':>25} {'':>6} FAIL: {e}"
        )

print("-" * 110)
print(f"Total: {passed} PASS, {failed} FAIL out of {len(BUILDINGS)}")
