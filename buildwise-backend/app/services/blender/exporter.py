"""Export Blender scenes to glTF and retrieve the result.

After a building is generated in Blender, this module requests a glTF
binary export and returns the file bytes (or uploads to GCS and returns
the URL).
"""

from __future__ import annotations

import base64
import logging
import re
import uuid
from pathlib import Path

from app.config import settings

from .client import BlenderPool

logger = logging.getLogger(__name__)

_EXPORT_DIR = Path("/tmp/blender-export")

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _sanitize_id(value: str) -> str:
    """Ensure IDs used in Blender script paths contain only safe characters."""
    if not _SAFE_ID_RE.match(value):
        return uuid.uuid4().hex[:12]
    return value


async def export_gltf(pool: BlenderPool, scene_id: str | None = None) -> bytes:
    """Export current Blender scene to glTF binary (.glb)."""
    if scene_id is None:
        scene_id = uuid.uuid4().hex[:12]
    scene_id = _sanitize_id(scene_id)

    filename = f"{scene_id}.glb"
    export_path = f"/tmp/blender-export/{filename}"

    await pool.execute(
        {
            "type": "execute_script",
            "params": {
                "script": _EXPORT_GLB_SCRIPT.format(path=export_path),
            },
        }
    )

    local_path = _EXPORT_DIR / filename
    if local_path.exists():
        return local_path.read_bytes()

    result = await pool.execute(
        {
            "type": "execute_script",
            "params": {
                "script": _READ_FILE_B64_SCRIPT.format(path=export_path),
            },
        }
    )

    raw_b64 = result.get("result", "")
    if not raw_b64:
        logger.warning("Blender returned empty glTF export for %s", scene_id)
    return base64.b64decode(raw_b64)


async def export_gltf_url(pool: BlenderPool, building_id: str) -> str:
    """Export glTF and return a URL (GCS or local)."""
    safe_id = _sanitize_id(building_id)
    glb_bytes = await export_gltf(pool, scene_id=safe_id)

    if settings.debug:
        local_dir = Path("static/models")
        local_dir.mkdir(parents=True, exist_ok=True)
        out_path = local_dir / f"{safe_id}.glb"
        out_path.write_bytes(glb_bytes)
        return f"/static/models/{safe_id}.glb"

    from google.cloud.storage import Client as GCSClient

    client = GCSClient()
    bucket = client.bucket(settings.gcs_bucket_name)
    blob = bucket.blob(f"models/{safe_id}.glb")
    blob.upload_from_string(glb_bytes, content_type="model/gltf-binary")
    blob.make_public()
    return blob.public_url


async def get_scene_info(pool: BlenderPool) -> dict:
    """Query the current Blender scene for object/zone information."""
    result = await pool.execute({"type": "get_scene_info"})
    return result.get("result", {})


_EXPORT_GLB_SCRIPT = """\
import bpy
bpy.ops.export_scene.gltf(filepath='{path}', export_format='GLB')
"""

_READ_FILE_B64_SCRIPT = """\
import base64, json
with open('{path}', 'rb') as f:
    data = base64.b64encode(f.read()).decode()
print(json.dumps({{"status": "ok", "result": data}}))
"""
