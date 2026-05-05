"""Blender 3D generation orchestration service.

Coordinates the full pipeline:
  NL/BPS → Blender 3D → glTF export → IDF generation

Falls back to Phase 1 parametric box model if Blender is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings

from .building_gen import bps_to_blender_commands, bps_to_bmesh_script, bps_to_zone_info
from .client import BlenderConnectionError, BlenderError, BlenderPool, BlenderTimeoutError
from .exporter import export_gltf_url
from .idf_converter import blender_to_idf

logger = logging.getLogger(__name__)

_pool: BlenderPool | None = None


def _get_pool() -> BlenderPool:
    global _pool
    if _pool is None:
        hosts_str = getattr(settings, "blender_hosts", "localhost:9876")
        hosts = []
        for h in hosts_str.split(","):
            h = h.strip()
            if not h:
                continue
            parts = h.split(":")
            host = parts[0]
            try:
                port = int(parts[1]) if len(parts) > 1 else 9876
            except ValueError:
                logger.warning("Invalid port in blender_hosts: %s, using 9876", h)
                port = 9876
            hosts.append((host, port))
        _pool = BlenderPool(hosts=hosts, timeout=60.0)
    return _pool


@dataclass
class GenerationResult:
    model_url: str
    zones: list[dict]
    idf_content: str | None
    source: str  # "blender" or "fallback"


async def generate_3d_from_bps(
    bps: dict,
    building_id: str,
    strategy: str = "baseline",
    city: str = "Seoul",
) -> GenerationResult:
    """Generate a 3D model from BPS and return glTF URL + IDF.

    Tries Blender MCP first; falls back to parametric box on failure.
    """
    pool = _get_pool()

    try:
        script = bps_to_bmesh_script(bps)
        await pool.execute({"type": "execute_code", "params": {"code": script}})

        model_url = await export_gltf_url(pool, building_id)
        zones = bps_to_zone_info(bps)
        idf_content = await blender_to_idf(pool, bps, strategy, city)

        logger.info("Blender 3D generation succeeded for building %s", building_id)
        return GenerationResult(
            model_url=model_url,
            zones=zones,
            idf_content=idf_content,
            source="blender",
        )

    except (BlenderConnectionError, BlenderTimeoutError, BlenderError) as exc:
        logger.warning(
            "Blender unavailable (%s), falling back to parametric", exc
        )
        return _fallback_parametric(bps, building_id)


async def modify_3d_from_instruction(
    instruction: str,
    bps: dict,
    building_id: str,
) -> GenerationResult:
    """Modify an existing 3D model using a natural language instruction.

    Parses the instruction into BPS updates, then regenerates 3D.
    """
    from app.services.ai.nl_parser import parse_building_from_text

    result = await parse_building_from_text(instruction)
    updated_bps = {**bps, **result.bps}

    return await generate_3d_from_bps(updated_bps, building_id)


def _fallback_parametric(bps: dict, building_id: str) -> GenerationResult:
    """Phase 1 fallback: return zone info without Blender 3D."""
    zones = bps_to_zone_info(bps)
    return GenerationResult(
        model_url="",
        zones=zones,
        idf_content=None,
        source="fallback",
    )
