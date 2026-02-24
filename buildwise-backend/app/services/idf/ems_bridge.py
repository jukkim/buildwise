"""Bridge module to delegate IDF generation to ems_simulation.

For building types supported by ems_simulation (DOE Reference Buildings),
this module delegates IDF generation to ems_simulation's IDFGenerator
for exact result matching.

Architecture:
- ems_simulation uses DOE Reference Building templates + eppy mutations
- BuildWise's BPS geometry is ignored (ems_simulation uses its own templates)
- Strategy mapping is 1:1 (baseline, m0-m8)
- Climate city names match directly
- Period types match ems_simulation's simulation_periods.yaml keys

Returns:
- IDF content as string
- Auxiliary files (CSV schedules for Schedule:File references)
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ems_simulation project root (sibling project under 8.simulation/)
# Layout (local dev):
#   8.simulation/blender/buildwise-backend/app/services/idf/ems_bridge.py  (this file)
#   8.simulation/ems_simulation/                                            (target)
# In Docker: EMS_SIMULATION_ROOT env var points to /opt/ems_simulation
_THIS_FILE = Path(__file__).resolve()
try:
    _EMS_SIM_DEFAULT = _THIS_FILE.parents[5] / "ems_simulation"
except IndexError:
    # Docker path is shallower (/app/app/services/idf/ems_bridge.py)
    _EMS_SIM_DEFAULT = Path("/opt/ems_simulation")

EMS_SIM_ROOT = Path(os.environ.get("EMS_SIMULATION_ROOT", str(_EMS_SIM_DEFAULT)))

# Building types that ems_simulation supports
SUPPORTED_BUILDINGS = frozenset(
    {
        "large_office",
        "medium_office",
        "small_office",
        "hospital",
        "primary_school",
        "standalone_retail",
    }
)

# Period mapping: BuildWise period_type → ems_simulation period key
# See ems_simulation/config/simulation_periods.yaml
PERIOD_MAP = {
    "1year": "1year",
    "1month_summer": "1month_summer",
    "1month_winter": "1month_winter",
    "1month_shoulder": "1month_shoulder",
    "10day_summer": "10day_summer",
    "10day_winter": "10day_winter",
    "summer_season": "summer_season",
    "winter_season": "winter_season",
}

_ems_available: bool | None = None


def is_ems_available() -> bool:
    """Check if ems_simulation project is accessible."""
    global _ems_available
    if _ems_available is not None:
        return _ems_available

    scripts_dir = EMS_SIM_ROOT / "scripts"
    gen_file = scripts_dir / "generate_idf.py"
    _ems_available = scripts_dir.is_dir() and gen_file.is_file()
    if _ems_available:
        logger.info("ems_simulation found at %s", EMS_SIM_ROOT)
    else:
        logger.warning("ems_simulation not found at %s — using BuildWise generator", EMS_SIM_ROOT)
    return _ems_available


def is_ems_supported(building_type: str) -> bool:
    """Check if ems_simulation supports this building type."""
    return building_type in SUPPORTED_BUILDINGS and is_ems_available()


_eppy_idd_set = False

# Lock for os.chdir() — process-wide CWD is not thread-safe
_chdir_lock = threading.Lock()

# Temp directory for IDD symlink (avoid polluting mounted /app volume)
_IDD_COMPAT_DIR = Path("/tmp/ems_compat")


def _setup_idd_compat() -> None:
    """Create IDD compatibility symlink for Linux/Docker.

    ems_simulation's generate_idf.py hardcodes C:/EnergyPlusV24-1-0/Energy+.idd
    and checks Path(...).exists() before calling eppy's IDF.setiddname().
    On Linux, this Windows-style path is treated as relative to CWD.

    Solution: create symlink at /tmp/ems_compat/C:/EnergyPlusV24-1-0/Energy+.idd
    and chdir to /tmp/ems_compat/ before calling IDFGenerator so the relative
    path resolves correctly. This avoids polluting the mounted /app volume.
    """
    global _eppy_idd_set
    if _eppy_idd_set:
        return

    if sys.platform == "win32":
        _eppy_idd_set = True
        return

    ep_dir = os.environ.get("EP_DIR", "/usr/local/EnergyPlus-24-1-0")
    real_idd = Path(ep_dir) / "Energy+.idd"
    if not real_idd.is_file():
        logger.warning("EnergyPlus IDD not found: %s", real_idd)
        return

    win_compat = _IDD_COMPAT_DIR / "C:" / "EnergyPlusV24-1-0" / "Energy+.idd"
    if not win_compat.exists():
        try:
            win_compat.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(real_idd), str(win_compat))
            logger.info("Created IDD symlink: %s -> %s", win_compat, real_idd)
        except OSError as exc:
            logger.warning("Failed to create IDD symlink: %s", exc)

    _eppy_idd_set = True


def generate_idf_via_ems(
    strategy: str,
    climate_city: str,
    building_type: str = "large_office",
    period_type: str = "1year",
    bps: dict | None = None,
) -> tuple[str, dict[str, bytes]]:
    """Generate IDF using ems_simulation's pipeline.

    Args:
        strategy: EMS strategy ('baseline', 'm0'-'m8').
        climate_city: Korean city name ('Seoul', 'Busan', etc.).
        building_type: DOE Reference Building type.
        period_type: Simulation period key.
        bps: Optional BPS dict for user setting overrides.

    Returns:
        Tuple of (idf_content_string, auxiliary_files_dict).
        auxiliary_files_dict maps filename → file bytes (CSV schedules).

    Raises:
        FileNotFoundError: If ems_simulation is not found.
        RuntimeError: If IDF generation fails.
    """
    scripts_dir = EMS_SIM_ROOT / "scripts"
    if not scripts_dir.is_dir():
        raise FileNotFoundError(f"ems_simulation scripts not found: {scripts_dir}")

    # Add ems_simulation/scripts to Python path for imports
    scripts_str = str(scripts_dir)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)

    # Map period
    period = PERIOD_MAP.get(period_type, "1year")

    logger.info(
        "Generating IDF via ems_simulation: building=%s strategy=%s climate=%s period=%s",
        building_type,
        strategy,
        climate_city,
        period,
    )

    # Create IDD compatibility symlink for Docker/Linux.
    # ems_simulation hardcodes "C:/EnergyPlusV24-1-0/Energy+.idd" (Windows path).
    # On Linux, this is a relative path — symlink makes it resolvable.
    _setup_idd_compat()

    # Import and instantiate IDFGenerator from ems_simulation
    from generate_idf import IDFGenerator  # noqa: E402 (dynamic import)

    generator = IDFGenerator(
        building=building_type,
        variant="default",
        climate=climate_city,
        period=period,
        ems=strategy,
    )

    # On Linux/Docker, redirect output_dir to /tmp to avoid PermissionError
    # from shutil.copy2() on Windows bind-mounted volumes (metadata preservation fails).
    if sys.platform != "win32":
        import tempfile

        tmp_out = Path(tempfile.mkdtemp(prefix="ems_idf_"))
        generator.output_dir = tmp_out

    # Change CWD to compat dir so "C:/EnergyPlusV24-1-0/Energy+.idd" resolves
    # via symlink at /tmp/ems_compat/C:/EnergyPlusV24-1-0/Energy+.idd
    # Lock protects against concurrent os.chdir() in threaded workers.
    with _chdir_lock:
        prev_cwd = os.getcwd()
        if sys.platform != "win32" and _IDD_COMPAT_DIR.is_dir():
            os.chdir(str(_IDD_COMPAT_DIR))

        try:
            idf_path = generator.generate()
        finally:
            os.chdir(prev_cwd)

    # Read IDF content
    idf_content = idf_path.read_text(encoding="utf-8")

    # Collect auxiliary files (CSV schedules for Schedule:File references)
    # Recursively find CSVs, preserving subdirectory structure (e.g. pmv_schedules/)
    output_dir = generator.output_dir
    aux_files: dict[str, bytes] = {}
    for csv_file in output_dir.rglob("*.csv"):
        # Skip EnergyPlus output CSVs (eplusout.csv, eplustbl.csv, etc.)
        if csv_file.name.startswith("eplus"):
            continue
        # Use relative path from output_dir as key (preserves subdirs)
        rel_path = csv_file.relative_to(output_dir)
        aux_files[str(rel_path)] = csv_file.read_bytes()
        logger.debug("Collected auxiliary file: %s (%d bytes)", rel_path, len(aux_files[str(rel_path)]))

    logger.info(
        "ems_simulation IDF generated: %d lines, %d auxiliary files",
        idf_content.count("\n"),
        len(aux_files),
    )

    # Apply user BPS overrides (setpoints, COP, efficiency)
    if bps:
        from .idf_patcher import apply_user_overrides

        idf_content, aux_files = apply_user_overrides(
            idf_content,
            aux_files,
            bps,
            building_type,
        )

    return idf_content, aux_files
