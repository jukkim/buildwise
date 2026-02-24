#!/usr/bin/env python3
"""Full-stack E2E test: API → Celery → EnergyPlus → Results.

Tests the complete BuildWise pipeline through HTTP API:
1. Login as demo user
2. Create project + building
3. Start simulation (baseline + m4)
4. Poll until complete
5. Verify results (EUI, savings, monthly profile)

Prerequisites:
  docker compose up -d  (db, redis, backend, worker)
  docker compose exec backend python scripts/seed.py  (or alembic + seed)

Usage:
  python -m tests.docker_e2e_test [--base-url http://localhost:8001]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8001"
DEMO_EMAIL = "demo@buildwise.ai"
POLL_INTERVAL = 10  # seconds
POLL_TIMEOUT = 600  # 10 minutes max

EXPECTED_BASELINE_EUI = 119.75  # large_office Seoul
EXPECTED_M4_EUI = 113.17
EUI_TOLERANCE_PCT = 2.0  # ±2% for full-stack (slightly wider than unit test)

PASS = 0
FAIL = 0


def check(condition: bool, msg: str):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def api(method: str, path: str, body: dict | None = None, user_id: str = "", base_url: str = DEFAULT_BASE_URL) -> dict:
    """Make HTTP request to BuildWise API."""
    url = f"{base_url}/api/v1{path}"
    headers = {"Content-Type": "application/json"}
    if user_id:
        headers["X-User-Id"] = user_id

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"{method} {path} → {e.code}: {error_body}") from e


# ---------------------------------------------------------------------------
# Test Steps
# ---------------------------------------------------------------------------


def step_health(base_url: str):
    """Step 0: Verify backend is healthy."""
    print("\n" + "=" * 60)
    print("Step 0: Health check")
    print("=" * 60)

    try:
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        check(data.get("status") == "ok", f"Backend healthy: {data}")
    except Exception as e:
        check(False, f"Backend not reachable: {e}")
        print("\n  Start services: docker compose up -d")
        sys.exit(1)


def step_login(base_url: str) -> str:
    """Step 1: Login as demo user."""
    print("\n" + "=" * 60)
    print("Step 1: Login")
    print("=" * 60)

    data = api("POST", "/auth/login", {"email": DEMO_EMAIL}, base_url=base_url)
    user_id = data.get("id", "")
    check(bool(user_id), f"Logged in as {data.get('email', '?')} (id={user_id})")
    return user_id


def step_create_project(user_id: str, base_url: str) -> str:
    """Step 2: Create test project."""
    print("\n" + "=" * 60)
    print("Step 2: Create project")
    print("=" * 60)

    data = api(
        "POST",
        "/projects",
        {
            "name": "E2E Test Project",
            "description": "Automated integration test",
        },
        user_id=user_id,
        base_url=base_url,
    )
    project_id = data["id"]
    check(bool(project_id), f"Project created: {project_id}")
    return project_id


def step_create_building(user_id: str, project_id: str, base_url: str) -> str:
    """Step 3: Create large_office building with default BPS."""
    print("\n" + "=" * 60)
    print("Step 3: Create building")
    print("=" * 60)

    bps = {
        "location": {"city": "Seoul"},
        "geometry": {
            "building_type": "large_office",
            "num_floors_above": 12,
            "total_floor_area_m2": 46320,
            "floor_to_floor_height_m": 3.96,
            "aspect_ratio": 1.5,
            "wwr": 0.38,
        },
        "envelope": {
            "wall_type": "curtain_wall",
            "window_type": "double_low_e",
            "window_shgc": 0.25,
        },
        "hvac": {
            "system_type": "vav_chiller_boiler",
            "autosize": True,
            "chillers": {"count": 3, "cop": 6.1},
            "boilers": {"count": 2, "efficiency": 0.80},
        },
        "internal_loads": {
            "people_density": 0.0565,
            "lighting_power_density": 10.76,
            "equipment_power_density": 10.76,
        },
        "schedules": {"occupancy_type": "office_standard"},
        "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
        "simulation": {"period": "1year"},
    }

    data = api(
        "POST",
        f"/projects/{project_id}/buildings",
        {
            "name": "E2E Large Office",
            "bps": bps,
        },
        user_id=user_id,
        base_url=base_url,
    )
    building_id = data["id"]
    check(bool(building_id), f"Building created: {building_id}")
    check(data.get("building_type") == "large_office", f"Type: {data.get('building_type')}")
    return building_id


def step_start_simulation(user_id: str, building_id: str, base_url: str) -> str:
    """Step 4: Start simulation with baseline + m4."""
    print("\n" + "=" * 60)
    print("Step 4: Start simulation")
    print("=" * 60)

    data = api(
        "POST",
        "/simulations",
        {
            "building_id": building_id,
            "climate_city": "Seoul",
            "period_type": "1year",
            "strategies": ["baseline", "m4"],
        },
        user_id=user_id,
        base_url=base_url,
    )

    config_id = data["config_id"]
    total = data.get("total_strategies", 0)
    check(bool(config_id), f"Simulation started: config={config_id}")
    check(total == 2, f"Strategies: {total} (baseline + m4)")
    return config_id


def step_poll_progress(user_id: str, config_id: str, base_url: str) -> dict:
    """Step 5: Poll until all runs complete."""
    print("\n" + "=" * 60)
    print("Step 5: Poll progress")
    print("=" * 60)

    start = time.time()
    last_status = ""

    while time.time() - start < POLL_TIMEOUT:
        data = api("GET", f"/simulations/{config_id}/progress", user_id=user_id, base_url=base_url)

        completed = data.get("completed", 0)
        running = data.get("running", 0)
        failed = data.get("failed", 0)
        total = data.get("total_strategies", 0)

        status = f"  Progress: {completed}/{total} done, {running} running, {failed} failed"
        if status != last_status:
            elapsed = int(time.time() - start)
            print(f"  [{elapsed:3d}s] {completed}/{total} completed, {running} running, {failed} failed")
            last_status = status

        if completed + failed >= total:
            break

        time.sleep(POLL_INTERVAL)

    elapsed = int(time.time() - start)
    check(completed == total, f"All {total} runs completed in {elapsed}s")
    check(failed == 0, f"No failures (failed={failed})")

    return data


def step_verify_results(user_id: str, config_id: str, base_url: str):
    """Step 6: Verify simulation results."""
    print("\n" + "=" * 60)
    print("Step 6: Verify results")
    print("=" * 60)

    data = api("GET", f"/simulations/{config_id}/results", user_id=user_id, base_url=base_url)

    # Baseline
    baseline = data.get("baseline")
    check(baseline is not None, "Baseline result present")

    if baseline:
        eui = baseline["eui_kwh_m2"]
        diff = abs(eui - EXPECTED_BASELINE_EUI) / EXPECTED_BASELINE_EUI * 100
        check(
            diff < EUI_TOLERANCE_PCT,
            f"Baseline EUI = {eui:.2f} (expected {EXPECTED_BASELINE_EUI}, diff {diff:.2f}%)",
        )
        check(baseline["total_energy_kwh"] > 0, f"Total energy = {baseline['total_energy_kwh']:.0f} kWh")
        check(baseline.get("annual_cost_krw", 0) > 0, f"Annual cost = {baseline.get('annual_cost_krw', 0):,} KRW")

        # Monthly profile
        mp = baseline.get("monthly_profile")
        check(mp is not None and len(mp) == 12, f"Monthly profile: {len(mp) if mp else 0} months")

    # Strategies
    strategies = data.get("strategies", [])
    check(len(strategies) >= 1, f"Strategy results: {len(strategies)}")

    m4 = next((s for s in strategies if s["strategy"] == "m4"), None)
    if m4:
        eui = m4["eui_kwh_m2"]
        diff = abs(eui - EXPECTED_M4_EUI) / EXPECTED_M4_EUI * 100
        check(
            diff < EUI_TOLERANCE_PCT,
            f"M4 EUI = {eui:.2f} (expected {EXPECTED_M4_EUI}, diff {diff:.2f}%)",
        )
        check(
            m4.get("savings_pct") is not None and m4["savings_pct"] > 0,
            f"M4 savings = {m4.get('savings_pct', 0):.1f}%",
        )

    # Recommendation
    recommended = data.get("recommended_strategy")
    check(recommended is not None, f"Recommendation: {recommended}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="BuildWise full-stack E2E test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print("=" * 60)
    print("FULL-STACK E2E TEST")
    print(f"Base URL: {args.base_url}")
    print("=" * 60)

    step_health(args.base_url)
    user_id = step_login(args.base_url)
    project_id = step_create_project(user_id, args.base_url)
    building_id = step_create_building(user_id, project_id, args.base_url)
    config_id = step_start_simulation(user_id, building_id, args.base_url)
    step_poll_progress(user_id, config_id, args.base_url)
    step_verify_results(user_id, config_id, args.base_url)

    # Summary
    print(f"\n{'=' * 60}")
    print("E2E TEST COMPLETE")
    print(f"{'=' * 60}")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  TOTAL: {PASS + FAIL}")

    if FAIL > 0:
        print(f"\n*** {FAIL} FAILURES ***")
        sys.exit(1)
    else:
        print("\nAll E2E tests passed!")


if __name__ == "__main__":
    main()
