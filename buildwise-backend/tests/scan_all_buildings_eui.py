"""Scan all ems_simulation buildings and extract EUI from eplustbl.csv files.

Outputs a summary table of baseline EUI and strategy savings for every building.
"""

import csv
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EMS_ROOT = Path(r"C:\Users\User\Desktop\myjob\8.simulation\ems_simulation\buildings")

# Floor areas from metadata / reference
FLOOR_AREAS = {
    "large_office": 46320,
    "medium_office": 4982,
    "small_office": 511,
    "standalone_retail": 2294,
    "retail": 2294,
    "primary_school": 6871,
    "hospital": 22422,
}


def parse_eplustbl_mj_per_m2(csv_path: Path) -> float | None:
    """Parse eplustbl.csv and extract Energy Per Total Building Area [MJ/m2]."""
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find "Total Site Energy" row — format: ,Total Site Energy,GJ,MJ/m2,MJ/m2
        for row in rows:
            row_str = ",".join(str(c) for c in row)
            if "Total Site Energy" in row_str:
                # MJ/m2 is the 4th column (index 3)
                if len(row) >= 4:
                    try:
                        return float(row[3].strip())
                    except (ValueError, AttributeError):
                        pass
        return None
    except Exception:
        return None


def scan_building(building_dir: Path, building_name: str):
    """Scan all strategy results for a building."""
    results_dir = building_dir / "results" / "default"
    if not results_dir.exists():
        return {}

    data = {}  # {strategy: {city: eui_kwh_m2}}
    FLOOR_AREAS.get(building_name, 0)

    for city_dir in sorted(results_dir.iterdir()):
        if not city_dir.is_dir():
            continue
        city = city_dir.name

        # Check for 1year first, then 1month_summer
        period_dir = city_dir / "1year"
        if not period_dir.exists():
            period_dir = city_dir / "1month_summer"
        if not period_dir.exists():
            continue

        for strategy_dir in sorted(period_dir.iterdir()):
            if not strategy_dir.is_dir():
                continue
            strategy = strategy_dir.name
            if strategy in ("archive", "ems", "schedule", "pmv_schedules", "m2_test", "m2_test2"):
                continue

            eplustbl = strategy_dir / "eplustbl.csv"
            if not eplustbl.exists():
                continue

            mj_m2 = parse_eplustbl_mj_per_m2(eplustbl)
            if mj_m2 and mj_m2 > 0:
                eui = mj_m2 / 3.6  # MJ/m2 -> kWh/m2

                if strategy not in data:
                    data[strategy] = {}
                data[strategy][city] = round(eui, 1)

    return data


def main():
    buildings = [
        "large_office",
        "medium_office",
        "medium_office_backup",
        "small_office",
        "standalone_retail",
        "retail",
        "primary_school",
        "hospital",
    ]

    # Also check analysis JSON files
    print("=" * 80)
    print("  EMS SIMULATION - ALL BUILDINGS EUI SCAN")
    print("=" * 80)

    all_results = {}

    for bname in buildings:
        bdir = EMS_ROOT / bname
        if not bdir.exists():
            continue

        print(f"\n{'=' * 70}")
        print(f"  {bname.upper()} (floor area: {FLOOR_AREAS.get(bname, '?')} m2)")
        print(f"{'=' * 70}")

        data = scan_building(bdir, bname)
        all_results[bname] = data

        if not data:
            print("  No eplustbl.csv data found")

            # Try analysis JSON
            analysis = bdir / "results" / "complete_analysis.json"
            if analysis.exists():
                with open(analysis, encoding="utf-8") as f:
                    a = json.load(f)
                if "baseline_results" in a:
                    br = a["baseline_results"]
                    print(f"  [From analysis JSON] avg_eui = {br.get('avg_eui_kwh_m2', '?')} kWh/m2")
                elif "ems_strategies_tested" in a:
                    for sname, sdata in a["ems_strategies_tested"].items():
                        print(f"  [From analysis JSON] {sname}: avg_eui = {sdata.get('avg_eui_kwh_m2', '?')} kWh/m2")
            continue

        # Print strategy summary
        strategies = sorted(
            data.keys(), key=lambda s: (0 if s == "baseline" else 1 if s.startswith("m") and s[1:].isdigit() else 2, s)
        )

        sorted(set(c for s in data.values() for c in s.keys()))

        # Average EUI per strategy
        print(f"\n  {'Strategy':<20} {'Avg EUI':>10} {'Min':>8} {'Max':>8} {'Cities':>6}")
        print(f"  {'-' * 20} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 6}")

        baseline_avg = None
        for strat in strategies:
            euis = list(data[strat].values())
            avg = sum(euis) / len(euis)
            if strat == "baseline":
                baseline_avg = avg

            savings = ""
            if baseline_avg and strat != "baseline":
                s = (baseline_avg - avg) / baseline_avg * 100
                savings = f"  ({s:+.1f}%)"

            print(f"  {strat:<20} {avg:>10.1f} {min(euis):>8.1f} {max(euis):>8.1f} {len(euis):>6}{savings}")

    # Summary comparison
    print(f"\n\n{'=' * 80}")
    print("  COMPARISON: ems_simulation vs BuildWise mock_runner")
    print(f"{'=' * 80}")

    # Current mock_runner values
    mock_eui = {
        "large_office": 215.7,
        "medium_office": 85.2,
        "small_office": 166.3,
        "standalone_retail": 157.2,
        "primary_school": 134.8,
        "hospital": 280.0,
    }

    print(f"\n  {'Building':<20} {'EP Baseline':>12} {'Mock EUI':>10} {'Ratio':>8} {'Status':>10}")
    print(f"  {'-' * 20} {'-' * 12} {'-' * 10} {'-' * 8} {'-' * 10}")

    for bname in ["large_office", "medium_office", "small_office", "standalone_retail", "primary_school", "hospital"]:
        ep_data = all_results.get(bname, {}).get("baseline", {})
        # Also try retail for standalone_retail
        if not ep_data and bname == "standalone_retail":
            ep_data = all_results.get("retail", {}).get("baseline", {})

        if ep_data:
            ep_avg = sum(ep_data.values()) / len(ep_data.values())
        else:
            ep_avg = None

        mock = mock_eui.get(bname, 0)

        if ep_avg:
            ratio = mock / ep_avg
            status = "OK" if 0.9 <= ratio <= 1.1 else "MISMATCH"
            print(f"  {bname:<20} {ep_avg:>12.1f} {mock:>10.1f} {ratio:>8.2f}x {status:>10}")
        else:
            print(f"  {bname:<20} {'N/A':>12} {mock:>10.1f} {'':>8} {'NO DATA':>10}")


if __name__ == "__main__":
    main()
