"""Result validation service.

Adapted from ems_simulation/validation/result_validator.py.
Validates parsed simulation results against physics rules and expected ranges.

Validation rules reference: config/validation_rules.yaml
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# EUI reference ranges (kWh/m2/year) from eplustbl.csv 10-city averages
# Range: ~±25% around baseline EUI to accommodate climate variation + strategies
_EUI_RANGES: dict[str, tuple[float, float]] = {
    "large_office": (85, 155),  # baseline 120.1
    "medium_office": (55, 100),  # baseline 77.8
    "small_office": (70, 130),  # baseline 97.8
    "standalone_retail": (90, 165),  # baseline 125.6
    "primary_school": (100, 180),  # baseline 139.5
    "hospital": (250, 440),  # baseline 339.6
}

_DEFAULT_EUI_RANGE = (30, 2000)


@dataclass
class ValidationIssue:
    """A single validation finding."""

    rule_id: str
    severity: str  # "error" | "warning" | "info"
    message: str
    field: str | None = None
    value: float | None = None


@dataclass
class ValidationReport:
    """Aggregated validation result."""

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def validate_result(
    parsed: dict,
    building_type: str | None = None,
    strategy: str | None = None,
) -> ValidationReport:
    """Validate parsed simulation results.

    Args:
        parsed: Dict from parse_energyplus_output() or generate_mock_result()
        building_type: Building type for EUI range check
        strategy: Strategy name for savings direction check

    Returns:
        ValidationReport with pass/fail and list of issues
    """
    issues: list[ValidationIssue] = []

    # RES-003: Numerical validity (NaN/Inf)
    _check_numerical_validity(parsed, issues)

    # RES-001: Energy range
    _check_energy_range(parsed, issues)

    # RES-001b: EUI range for building type
    _check_eui_range(parsed, building_type, issues)

    # RES-004: Component consistency
    _check_component_consistency(parsed, issues)

    # PHY-004: Strategy effect (savings should be >= 0)
    if strategy and strategy != "baseline":
        _check_strategy_effect(parsed, strategy, issues)

    passed = len([i for i in issues if i.severity == "error"]) == 0
    return ValidationReport(passed=passed, issues=issues)


def _check_numerical_validity(parsed: dict, issues: list[ValidationIssue]) -> None:
    """RES-003: Check for NaN/Inf in numeric fields."""
    numeric_keys = [
        "total_energy_kwh",
        "hvac_energy_kwh",
        "cooling_energy_kwh",
        "heating_energy_kwh",
        "fan_energy_kwh",
        "pump_energy_kwh",
        "lighting_energy_kwh",
        "equipment_energy_kwh",
        "eui_kwh_m2",
        "peak_demand_kw",
        "savings_pct",
    ]
    for key in numeric_keys:
        val = parsed.get(key)
        if val is None:
            continue
        if not isinstance(val, int | float):
            issues.append(
                ValidationIssue(
                    rule_id="RES-003",
                    severity="error",
                    message=f"{key} is not numeric: {type(val).__name__}",
                    field=key,
                )
            )
        elif math.isnan(val) or math.isinf(val):
            issues.append(
                ValidationIssue(
                    rule_id="RES-003",
                    severity="error",
                    message=f"{key} contains NaN/Inf: {val}",
                    field=key,
                    value=val,
                )
            )


def _check_energy_range(parsed: dict, issues: list[ValidationIssue]) -> None:
    """RES-001: Check energy values are non-negative."""
    energy_keys = [
        "total_energy_kwh",
        "hvac_energy_kwh",
        "cooling_energy_kwh",
        "heating_energy_kwh",
        "fan_energy_kwh",
        "pump_energy_kwh",
        "lighting_energy_kwh",
        "equipment_energy_kwh",
    ]
    for key in energy_keys:
        val = parsed.get(key)
        if val is not None and isinstance(val, int | float) and val < 0:
            issues.append(
                ValidationIssue(
                    rule_id="RES-001",
                    severity="error",
                    message=f"{key} is negative: {val}",
                    field=key,
                    value=val,
                )
            )


def _check_eui_range(
    parsed: dict,
    building_type: str | None,
    issues: list[ValidationIssue],
) -> None:
    """RES-001b: Check EUI is within expected range for building type."""
    eui = parsed.get("eui_kwh_m2")
    if eui is None or not isinstance(eui, int | float):
        return

    min_eui, max_eui = _EUI_RANGES.get(building_type or "", _DEFAULT_EUI_RANGE)

    if eui < min_eui * 0.5:
        issues.append(
            ValidationIssue(
                rule_id="RES-001",
                severity="warning",
                message=f"EUI {eui:.1f} is far below expected range [{min_eui}, {max_eui}] for {building_type}",
                field="eui_kwh_m2",
                value=eui,
            )
        )
    elif eui > max_eui * 1.5:
        issues.append(
            ValidationIssue(
                rule_id="RES-001",
                severity="warning",
                message=f"EUI {eui:.1f} is far above expected range [{min_eui}, {max_eui}] for {building_type}",
                field="eui_kwh_m2",
                value=eui,
            )
        )


def _check_component_consistency(parsed: dict, issues: list[ValidationIssue]) -> None:
    """RES-004: Check HVAC components sum to HVAC total."""
    hvac_total = parsed.get("hvac_energy_kwh")
    if hvac_total is None:
        return

    components = ["cooling_energy_kwh", "heating_energy_kwh", "fan_energy_kwh", "pump_energy_kwh"]
    component_sum = sum(parsed.get(k, 0.0) for k in components)

    if component_sum > 0 and abs(component_sum - hvac_total) > hvac_total * 0.01:
        issues.append(
            ValidationIssue(
                rule_id="RES-004",
                severity="warning",
                message=f"HVAC component sum ({component_sum:.1f}) != HVAC total ({hvac_total:.1f})",
                field="hvac_energy_kwh",
                value=hvac_total,
            )
        )


def _check_strategy_effect(parsed: dict, strategy: str, issues: list[ValidationIssue]) -> None:
    """PHY-004: Strategy savings should be non-negative (with 2% tolerance)."""
    savings_pct = parsed.get("savings_pct")
    if savings_pct is None:
        return

    if savings_pct < -2.0:
        issues.append(
            ValidationIssue(
                rule_id="PHY-004",
                severity="warning",
                message=f"Strategy {strategy} shows negative savings: {savings_pct:.1f}% "
                f"(EMS rebound effect or measurement error)",
                field="savings_pct",
                value=savings_pct,
            )
        )
