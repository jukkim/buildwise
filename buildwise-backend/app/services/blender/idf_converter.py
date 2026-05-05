"""Convert Blender 3D model zone information to EnergyPlus IDF.

Uses the existing ems_bridge.py pipeline (DOE reference building templates).
The Blender 3D geometry is for visualization only — actual IDF generation
relies on pre-validated DOE templates via ems_bridge, not on the zone
geometry extracted here.
"""

from __future__ import annotations

import logging
import math

from .building_gen import bps_to_zone_info
from .client import BlenderPool

logger = logging.getLogger(__name__)


async def blender_to_idf(
    pool: BlenderPool,
    bps: dict,
    strategy: str = "baseline",
    city: str = "Seoul",
    period: str = "1year",
) -> str | None:
    """Generate an IDF from BPS via ems_bridge (DOE templates).

    Returns IDF content string on success, None if ems_bridge is
    unavailable or the building type is unsupported.
    """
    building_type = bps.get("building", {}).get("building_type", "large_office")

    from app.services.idf.ems_bridge import generate_idf_via_ems, is_ems_supported

    if not is_ems_supported(building_type):
        logger.info("ems_bridge does not support %s — IDF not generated", building_type)
        return None

    try:
        idf_content, aux_files = generate_idf_via_ems(
            building_type=building_type,
            strategy=strategy,
            climate_city=city,
            period_type=period,
        )
        logger.info("IDF generated via ems_bridge for %s/%s", building_type, strategy)
        return idf_content
    except Exception:
        logger.warning("ems_bridge IDF generation failed", exc_info=True)
        return None


def _zones_to_idf_objects(zones: list[dict]) -> str:
    """Convert zone list to IDF Zone objects (name + origin only).

    This produces Zone declarations for validation/testing purposes.
    Full IDF generation (with surfaces, constructions, HVAC) is handled
    by ems_bridge using DOE reference templates.
    """
    lines: list[str] = []

    for zone in zones:
        name = zone["name"]
        height = zone["height_m"]
        floor_idx = zone["floor"] - 1
        z_base = floor_idx * height

        lines.append(f"\nZone,\n  {name},  !- Name\n  0,  !- Direction\n"
                      f"  0, 0, {z_base},  !- Origin\n  ,  !- Type\n  1;  !- Multiplier\n")

    return "\n".join(lines)
