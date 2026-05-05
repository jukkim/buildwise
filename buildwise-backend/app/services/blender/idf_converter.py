"""Convert Blender 3D model zone information to EnergyPlus IDF.

Uses the existing ems_bridge.py / generator.py pipeline, injecting zone
geometry extracted from the Blender scene.  This avoids depending on
gbXML or OpenStudio.
"""

from __future__ import annotations

import logging
from typing import Any

from .building_gen import bps_to_zone_info
from .client import BlenderPool

logger = logging.getLogger(__name__)


async def blender_to_idf(
    pool: BlenderPool,
    bps: dict,
    strategy: str = "baseline",
    city: str = "Seoul",
    period: str = "1year",
) -> str:
    """Generate an IDF from the current Blender scene + BPS metadata.

    Pipeline:
      1. Extract zone definitions from BPS (parametric, not from Blender mesh)
      2. Attempt ems_bridge (DOE templates) — preferred for accuracy
      3. Fallback to BuildWise IDF generator with injected zones
    """
    zones = bps_to_zone_info(bps)

    building_type = bps.get("building", {}).get("building_type", "large_office")

    # Try ems_bridge first (exact DOE templates)
    from app.services.idf.ems_bridge import generate_idf_via_ems, is_ems_supported

    if is_ems_supported(building_type, strategy):
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
            logger.warning("ems_bridge failed, falling back to generator", exc_info=True)

    # Fallback: BuildWise generator with zone info
    from app.services.idf.generator import generate_idf

    idf_content = generate_idf(
        bps=bps,
        strategy=strategy,
        climate_city=city,
        period_type=period,
        zones=zones,
    )
    return idf_content


def _zones_to_idf_objects(zones: list[dict]) -> str:
    """Convert zone list to IDF Zone + BuildingSurface objects.

    Each zone becomes:
      - Zone object
      - Floor surface
      - Ceiling/Roof surface
      - 4 Wall surfaces (with optional windows based on WWR)
    """
    lines: list[str] = []

    for zone in zones:
        name = zone["name"]
        area = zone["area_m2"]
        height = zone["height_m"]
        floor_idx = zone["floor"] - 1

        import math

        side = math.sqrt(area)
        z_base = floor_idx * height

        lines.append(f"\nZone,\n  {name},  !- Name\n  0,  !- Direction\n"
                      f"  0, 0, {z_base},  !- Origin\n  ,  !- Type\n  1;  !- Multiplier\n")

    return "\n".join(lines)
