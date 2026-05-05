"""Blender 3D generation orchestration service.

Coordinates the full pipeline:
  NL/BPS → Blender 3D → glTF export → IDF generation

Falls back to Phase 1 parametric box model if Blender is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

from .building_gen import bps_to_blender_commands, bps_to_zone_info
from .client import BlenderConnectionError, BlenderPool, BlenderTimeoutError
from .exporter import export_gltf_url, get_scene_info
from .idf_converter import blender_to_idf

logger = logging.getLogger(__name__)

# Lazy singleton pool
_pool: BlenderPool | None = None


def _get_pool() -> BlenderPool:
    global _pool
    if _pool is None:
        hosts_str = getattr(settings, "blender_hosts", "localhost:9876")
        hosts = []
        for h in hosts_str.split(","):
            parts = h.strip().split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 9876
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
        # 1. Generate 3D in Blender
        commands = bps_to_blender_commands(bps)
        for cmd in commands:
            await pool.execute(cmd)

        # 2. Export glTF
        model_url = await export_gltf_url(pool, building_id)

        # 3. Extract zones
        zones = bps_to_zone_info(bps)

        # 4. Generate IDF
        idf_content = await blender_to_idf(pool, bps, strategy, city)

        logger.info("Blender 3D generation succeeded for building %s", building_id)
        return GenerationResult(
            model_url=model_url,
            zones=zones,
            idf_content=idf_content,
            source="blender",
        )

    except (BlenderConnectionError, BlenderTimeoutError) as exc:
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

    Uses Claude API to translate the instruction into Blender commands,
    then executes them via MCP.
    """
    pool = _get_pool()

    from app.services.ai.nl_parser import parse_building_description

    updated_bps = await parse_building_description(instruction, base_bps=bps)

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
