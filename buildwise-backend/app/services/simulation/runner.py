"""EnergyPlus simulation runner.

Executes EnergyPlus via subprocess (local) or Docker container (production).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid as uuid_mod
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Strict EPW filename pattern (alphanumeric, dots, hyphens, underscores)
_EPW_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+\.epw$")


def _validate_run_id(run_id: str) -> str:
    """Validate run_id is a proper UUID to prevent path traversal."""
    try:
        validated = uuid_mod.UUID(run_id)
        return str(validated)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid run_id format: {run_id}")


def _validate_epw_filename(epw_file: str) -> str:
    """Validate EPW filename contains no path separators."""
    # Strip any directory components
    clean = Path(epw_file).name
    if not _EPW_FILENAME_RE.match(clean):
        raise ValueError(f"Invalid EPW filename: {epw_file}")
    return clean


async def run_energyplus(
    idf_content: str,
    epw_file: str,
    run_id: str,
    auxiliary_files: dict[str, bytes] | None = None,
) -> dict:
    """Execute EnergyPlus with the given IDF and EPW.

    Args:
        idf_content: Complete IDF file string.
        epw_file: EPW filename (e.g. "KOR_Seoul.Ws.108.epw").
        run_id: Unique run identifier (must be valid UUID).
        auxiliary_files: Optional dict of {filename: bytes} for Schedule:File
            CSV references. Written alongside the IDF in the working directory.

    Returns:
        dict with keys: output_dir, exit_code, stdout, stderr

    Raises:
        ValueError: If run_id is not a valid UUID or epw_file is invalid.
        FileNotFoundError: If EPW file cannot be found.
        RuntimeError: If EnergyPlus fails or times out.
    """
    # Validate inputs to prevent path traversal
    safe_run_id = _validate_run_id(run_id)
    safe_epw = _validate_epw_filename(epw_file)

    # Create temp directory for this run
    base_dir = Path(tempfile.gettempdir()) / "buildwise" / "runs" / safe_run_id
    base_dir.mkdir(parents=True, exist_ok=True)

    # Verify base_dir is under expected parent
    expected_parent = Path(tempfile.gettempdir()) / "buildwise" / "runs"
    if not base_dir.resolve().is_relative_to(expected_parent.resolve()):
        raise ValueError(f"Run directory escaped sandbox: {base_dir}")

    idf_path = base_dir / "in.idf"
    idf_path.write_text(idf_content, encoding="utf-8")

    # Write auxiliary files (CSV schedules for Schedule:File references)
    # Files may include subdirectory paths (e.g. "pmv_schedules/file.csv")
    if auxiliary_files:
        for fname, fbytes in auxiliary_files.items():
            rel_path = Path(fname)
            # Reject absolute paths and parent traversal
            if rel_path.is_absolute() or ".." in rel_path.parts:
                logger.warning("Skipping suspicious auxiliary filename: %s", fname)
                continue
            # Only allow safe characters in each component
            safe_parts = []
            for part in rel_path.parts:
                clean = Path(part).name  # strip any hidden separators
                if clean != part:
                    logger.warning("Skipping auxiliary file with unsafe component: %s", fname)
                    break
                safe_parts.append(clean)
            else:
                aux_path = base_dir / Path(*safe_parts)
                aux_path.parent.mkdir(parents=True, exist_ok=True)
                aux_path.write_bytes(fbytes)
                logger.debug("Wrote auxiliary file: %s (%d bytes)", fname, len(fbytes))

    # Locate EPW file
    epw_search_paths = [
        Path(os.environ.get("BUILDWISE_EPW_DIR", "")) / safe_epw,
        Path(__file__).parent.parent.parent.parent / "config" / "weather" / safe_epw,
        Path("/app/weather") / safe_epw,  # Docker container path
    ]
    epw_path = None
    for p in epw_search_paths:
        if p.exists():
            epw_path = p
            break

    if epw_path is None:
        logger.error("EPW file not found: %s", safe_epw)
        raise FileNotFoundError(f"EPW file not found: {safe_epw}")

    # Run EnergyPlus
    ep_exe = os.environ.get("ENERGYPLUS_EXE", "energyplus")

    ep_dir = os.environ.get("EP_DIR", "/usr/local/EnergyPlus-24-1-0")
    idd_path = os.path.join(ep_dir, "Energy+.idd")

    cmd = [
        ep_exe,
        "--idd",
        idd_path,
        "--weather",
        str(epw_path),
        "--output-directory",
        str(base_dir),
        "--readvars",
        str(idf_path),
    ]

    logger.info("Running EnergyPlus: %s", " ".join(cmd))

    # Redirect stdout/stderr to files to avoid unbounded memory buffering
    stdout_log = base_dir / "stdout.log"
    stderr_log = base_dir / "stderr.log"

    try:
        with open(stdout_log, "w") as stdout_f, open(stderr_log, "w") as stderr_f:
            proc = subprocess.run(
                cmd,
                stdout=stdout_f,
                stderr=stderr_f,
                timeout=settings.energyplus_timeout_seconds,
                cwd=str(base_dir),
            )

        # Read last portion of logs for error reporting
        stdout_tail = ""
        stderr_tail = ""
        if stdout_log.exists():
            stdout_tail = stdout_log.read_text(encoding="utf-8", errors="replace")[-5000:]
        if stderr_log.exists():
            stderr_tail = stderr_log.read_text(encoding="utf-8", errors="replace")[-5000:]

        result = {
            "output_dir": str(base_dir),
            "exit_code": proc.returncode,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
        }

        if proc.returncode != 0:
            logger.error(
                "EnergyPlus failed (exit %d): %s",
                proc.returncode,
                stderr_tail[:500],
            )
            raise RuntimeError(f"EnergyPlus exit code {proc.returncode}")

        logger.info("EnergyPlus completed: %s", base_dir)
        return result

    except subprocess.TimeoutExpired:
        logger.error("EnergyPlus timed out after %ds", settings.energyplus_timeout_seconds)
        raise RuntimeError(f"EnergyPlus timed out after {settings.energyplus_timeout_seconds}s")


def cleanup_run_directory(run_id: str) -> None:
    """Remove temporary simulation files for a completed/failed run."""
    try:
        safe_run_id = _validate_run_id(run_id)
        base_dir = Path(tempfile.gettempdir()) / "buildwise" / "runs" / safe_run_id
        if base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)
            logger.debug("Cleaned up run directory: %s", base_dir)
    except ValueError:
        pass  # Invalid run_id, nothing to clean
