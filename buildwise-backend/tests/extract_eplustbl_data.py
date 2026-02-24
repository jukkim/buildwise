"""Extract all EUI data from ems_simulation eplustbl.csv files.

Outputs Python dict literal for direct use in mock_runner.py.
"""

import csv
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EMS_ROOT = Path(r"C:\Users\User\Desktop\myjob\8.simulation\ems_simulation\buildings")


def parse_eui(csv_path):
    """Parse eplustbl.csv → EUI in kWh/m2."""
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            rows = list(csv.reader(f))
        for row in rows:
            if any("Total Site Energy" in str(c) for c in row):
                if len(row) >= 4:
                    try:
                        return round(float(row[3].strip()) / 3.6, 2)
                    except (ValueError, AttributeError):
                        pass
        return None
    except Exception:
        return None


def parse_end_uses(csv_path):
    """Parse eplustbl.csv end uses → dict of {category: kWh/m2}."""
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            rows = list(csv.reader(f))

        end_uses = {}
        # Find "End Uses" section - rows with GJ values
        for row in rows:
            if len(row) < 2:
                continue
            label = str(row[0]).strip() if row[0] else ""
            if not label:
                continue
            # End use categories
            categories = {
                "Heating": "heating",
                "Cooling": "cooling",
                "Interior Lighting": "interior_lighting",
                "Exterior Lighting": "exterior_lighting",
                "Interior Equipment": "interior_equipment",
                "Exterior Equipment": "exterior_equipment",
                "Fans": "fans",
                "Pumps": "pumps",
                "Heat Rejection": "heat_rejection",
                "Humidification": "humidification",
                "Water Systems": "water_systems",
            }
            if label in categories:
                # Sum all GJ columns (electricity, gas, etc.)
                total_gj = 0.0
                for cell in row[1:]:
                    try:
                        val = float(str(cell).strip())
                        total_gj += val
                    except (ValueError, AttributeError):
                        pass
                if total_gj > 0:
                    end_uses[categories[label]] = round(total_gj / 3.6 * 1000, 1)  # GJ → kWh
        return end_uses
    except Exception:
        return {}


def main():
    buildings = [
        "large_office",
        "medium_office",
        "small_office",
        "standalone_retail",
        "retail",
        "primary_school",
        "hospital",
    ]

    all_data = {}

    for bname in buildings:
        bdir = EMS_ROOT / bname
        if not bdir.exists():
            continue
        results_dir = bdir / "results" / "default"
        if not results_dir.exists():
            continue

        bdata = {}
        for city_dir in sorted(results_dir.iterdir()):
            if not city_dir.is_dir():
                continue
            city = city_dir.name

            period_dir = city_dir / "1year"
            if not period_dir.exists():
                period_dir = city_dir / "1month_summer"
            if not period_dir.exists():
                continue

            for strat_dir in sorted(period_dir.iterdir()):
                if not strat_dir.is_dir():
                    continue
                strat = strat_dir.name
                if strat in ("archive", "ems", "schedule", "pmv_schedules", "m2_test", "m2_test2"):
                    continue

                eplustbl = strat_dir / "eplustbl.csv"
                if not eplustbl.exists():
                    continue

                eui = parse_eui(eplustbl)
                if eui and eui > 0:
                    if strat not in bdata:
                        bdata[strat] = {}
                    bdata[strat][city] = eui

        if bdata:
            all_data[bname] = bdata

    # Output as Python dict
    print("# ═══════════════════════════════════════════════════════════════")
    print("# _EUI_TABLE: exact EUI (kWh/m2/year) from eplustbl.csv")
    print("# ═══════════════════════════════════════════════════════════════")
    print("_EUI_TABLE = {")
    for bname in buildings:
        if bname not in all_data:
            continue
        strategies = all_data[bname]
        print(f'    "{bname}": {{')

        # Sort: baseline first, then m0-m8, then named strategies
        def strat_sort_key(s):
            if s == "baseline":
                return (0, s)
            if s.startswith("m") and s[1:].isdigit():
                return (1, int(s[1:]))
            return (2, s)

        for strat in sorted(strategies.keys(), key=strat_sort_key):
            cities = strategies[strat]
            city_strs = []
            for c in [
                "Seoul",
                "Busan",
                "Daegu",
                "Daejeon",
                "Gwangju",
                "Incheon",
                "Gangneung",
                "Jeju",
                "Cheongju",
                "Ulsan",
            ]:
                if c in cities:
                    city_strs.append(f'"{c}": {cities[c]}')
            # Add any cities not in standard list
            for c in sorted(cities.keys()):
                if c not in [
                    "Seoul",
                    "Busan",
                    "Daegu",
                    "Daejeon",
                    "Gwangju",
                    "Incheon",
                    "Gangneung",
                    "Jeju",
                    "Cheongju",
                    "Ulsan",
                ]:
                    city_strs.append(f'"{c}": {cities[c]}')
            print(f'        "{strat}": {{{", ".join(city_strs)}}},')
        print("    },")
    print("}")

    # Also output summary stats
    print("\n\n# ═══════════════════════════════════════════════════════════════")
    print("# Summary: avg EUI and savings per building/strategy")
    print("# ═══════════════════════════════════════════════════════════════")
    for bname in buildings:
        if bname not in all_data:
            continue
        strategies = all_data[bname]
        baseline_euis = strategies.get("baseline", {})
        if not baseline_euis:
            continue

        baseline_avg = sum(baseline_euis.values()) / len(baseline_euis)
        print(f"\n# {bname}: baseline avg = {baseline_avg:.1f} kWh/m2 ({len(baseline_euis)} cities)")

        for strat in sorted(
            strategies.keys(),
            key=lambda s: (0, s)
            if s == "baseline"
            else (1, int(s[1:]))
            if s.startswith("m") and s[1:].isdigit()
            else (2, s),
        ):
            if strat == "baseline":
                continue
            euis = strategies[strat]
            avg = sum(euis.values()) / len(euis)
            # Calculate per-city savings
            savings_list = []
            for city in euis:
                if city in baseline_euis:
                    s = (baseline_euis[city] - euis[city]) / baseline_euis[city] * 100
                    savings_list.append(s)
            if savings_list:
                avg_savings = sum(savings_list) / len(savings_list)
                print(f"#   {strat}: avg EUI={avg:.1f}, avg savings={avg_savings:.1f}% ({len(euis)} cities)")


if __name__ == "__main__":
    main()
