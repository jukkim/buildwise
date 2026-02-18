"""EnergyPlus simulation runner.

Executes EnergyPlus via subprocess (local) or Docker container (production).
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


async def run_energyplus(
    idf_content: str,
    epw_file: str,
    run_id: str,
) -> dict:
    """Execute EnergyPlus with the given IDF and EPW.

    Args:
        idf_content: Complete IDF file string.
        epw_file: EPW filename (e.g. "KOR_Seoul.Ws.108.epw").
        run_id: Unique run identifier for output directory.

    Returns:
        dict with keys: output_dir, exit_code, stdout, stderr
    """
    # Create temp directory for this run
    base_dir = Path(tempfile.gettempdir()) / "buildwise" / "runs" / run_id
    base_dir.mkdir(parents=True, exist_ok=True)

    idf_path = base_dir / "in.idf"
    idf_path.write_text(idf_content, encoding="utf-8")

    # Locate EPW file
    epw_search_paths = [
        Path(os.environ.get("BUILDWISE_EPW_DIR", "")) / epw_file,
        Path(__file__).parent.parent.parent.parent / "config" / "weather" / epw_file,
        Path("/app/weather") / epw_file,  # Docker container path
    ]
    epw_path = None
    for p in epw_search_paths:
        if p.exists():
            epw_path = p
            break

    if epw_path is None:
        logger.error("EPW file not found: %s", epw_file)
        raise FileNotFoundError(f"EPW file not found: {epw_file}")

    # Run EnergyPlus
    ep_exe = os.environ.get("ENERGYPLUS_EXE", "energyplus")

    cmd = [
        ep_exe,
        "--idd", "/usr/local/EnergyPlus-24-1-0/Energy+.idd",
        "--weather", str(epw_path),
        "--output-directory", str(base_dir),
        "--readvars",
        str(idf_path),
    ]

    logger.info("Running EnergyPlus: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.energyplus_timeout_seconds,
            cwd=str(base_dir),
        )

        result = {
            "output_dir": str(base_dir),
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-5000:] if proc.stdout else "",
            "stderr": proc.stderr[-5000:] if proc.stderr else "",
        }

        if proc.returncode != 0:
            logger.error(
                "EnergyPlus failed (exit %d): %s",
                proc.returncode,
                proc.stderr[:500],
            )
            raise RuntimeError(f"EnergyPlus exit code {proc.returncode}: {proc.stderr[:500]}")

        logger.info("EnergyPlus completed: %s", base_dir)
        return result

    except subprocess.TimeoutExpired:
        logger.error("EnergyPlus timed out after %ds", settings.energyplus_timeout_seconds)
        raise RuntimeError(f"EnergyPlus timed out after {settings.energyplus_timeout_seconds}s")
