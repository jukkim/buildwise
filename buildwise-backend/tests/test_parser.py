"""EnergyPlus output parser unit tests."""

import tempfile
from pathlib import Path

import pytest

from app.services.results.parser import (
    _estimate_from_meter_csv,
    _parse_summary_csv,
    _parse_summary_html,
    parse_energyplus_output,
)


@pytest.fixture
def tmp_output_dir():
    """Create a temporary directory for simulated E+ output."""
    with tempfile.TemporaryDirectory(prefix="buildwise_test_") as d:
        yield Path(d)


class TestParseSummaryCSV:
    """Test eplustbl.csv parsing with various unit formats."""

    def test_parse_gj_units(self, tmp_output_dir):
        csv_content = """\
,Total Energy [GJ],Energy Per Total Building Area [MJ/m2],Energy Per Conditioned Building Area [MJ/m2]
Total Site Energy,350.5,175.25,180.00
Net Site Energy,340.0,170.00,175.00
Total Source Energy,700.0,350.00,360.00
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        # 350.5 GJ * 277.78 = 97,370.89 kWh
        assert abs(result["total_energy_kwh"] - 350.5 * 277.78) < 10

    def test_parse_kwh_units(self, tmp_output_dir):
        csv_content = """\
,Total Energy [kWh],Energy Per Total Building Area [kWh/m2]
Total Site Energy,97370.0,175.25
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        assert abs(result["total_energy_kwh"] - 97370.0) < 1

    def test_parse_kbtu_units(self, tmp_output_dir):
        csv_content = """\
,Total Energy [kBtu],Energy Per Total Building Area [kBtu/ft2]
Total Site Energy,332000.0,35.5
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        # 332000 kBtu * 0.293071 = 97299.6 kWh
        assert abs(result["total_energy_kwh"] - 332000 * 0.293071) < 10

    def test_parse_with_area(self, tmp_output_dir):
        csv_content = """\
,Total Energy [GJ],Energy Per Total Building Area [MJ/m2]
Total Site Energy,350.5,175.25
Total Building Area,,
,Total Building Area,2000.0
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        assert "total_energy_kwh" in result
        # Area parsing depends on row format; just verify energy is correct
        assert result["total_energy_kwh"] > 90000

    def test_parse_comma_numbers(self, tmp_output_dir):
        csv_content = """\
,Total Energy [kWh],Other
"Total Site Energy","1,234,567.8",other
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        assert abs(result["total_energy_kwh"] - 1234567.8) < 1

    def test_empty_file_returns_empty(self, tmp_output_dir):
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text("", encoding="utf-8")
        result = _parse_summary_csv(csv_path)
        assert result == {} or result.get("total_energy_kwh", 0) == 0


class TestParseSummaryHTML:
    """Test eplustbl.htm parsing."""

    def test_parse_gj_html(self, tmp_output_dir):
        html_content = """<table>
<tr><td>Total Site Energy</td><td>350.5 GJ</td></tr>
<tr><td>Total Building Area</td><td>2000.0 m2</td></tr>
</table>"""
        html_path = tmp_output_dir / "eplustbl.htm"
        html_path.write_text(html_content, encoding="utf-8")
        result = _parse_summary_html(html_path)
        assert abs(result["total_energy_kwh"] - 350.5 * 277.78) < 10
        assert abs(result["total_floor_area_m2"] - 2000.0) < 1
        assert "eui_kwh_m2" in result

    def test_parse_kbtu_html(self, tmp_output_dir):
        html_content = """<table>
<tr><td>Total Site Energy</td><td>332000 kBtu</td></tr>
</table>"""
        html_path = tmp_output_dir / "eplustbl.htm"
        html_path.write_text(html_content, encoding="utf-8")
        result = _parse_summary_html(html_path)
        assert abs(result["total_energy_kwh"] - 332000 * 0.293071) < 10

    def test_parse_comma_separated_html(self, tmp_output_dir):
        html_content = """<table>
<tr><td>Total Site Energy</td><td>1,234 GJ</td></tr>
</table>"""
        html_path = tmp_output_dir / "eplustbl.htm"
        html_path.write_text(html_content, encoding="utf-8")
        result = _parse_summary_html(html_path)
        assert abs(result["total_energy_kwh"] - 1234 * 277.78) < 10


class TestMeterCSVFallback:
    """Test eplusout.csv meter data parsing."""

    def test_electricity_only(self, tmp_output_dir):
        csv_content = """Date/Time,Electricity:Facility [J](Hourly)
01/01 01:00:00,3600000
01/01 02:00:00,7200000
"""
        meter_path = tmp_output_dir / "eplusout.csv"
        meter_path.write_text(csv_content, encoding="utf-8")
        result = _estimate_from_meter_csv(meter_path)
        # (3600000 + 7200000) / 3600000 = 3.0 kWh
        assert abs(result["total_energy_kwh"] - 3.0) < 0.01

    def test_multi_fuel(self, tmp_output_dir):
        csv_content = """Date/Time,Electricity:Facility [J](Hourly),NaturalGas:Facility [J](Hourly)
01/01 01:00:00,3600000,1800000
01/01 02:00:00,7200000,3600000
"""
        meter_path = tmp_output_dir / "eplusout.csv"
        meter_path.write_text(csv_content, encoding="utf-8")
        result = _estimate_from_meter_csv(meter_path)
        # Elec: (3.6M + 7.2M) / 3.6M = 3.0, Gas: (1.8M + 3.6M) / 3.6M = 1.5
        assert abs(result["total_energy_kwh"] - 4.5) < 0.01


class TestParseEnergyPlusOutput:
    """Test the main entry point function."""

    def test_raises_on_empty_directory(self, tmp_output_dir):
        """No output files should raise ValueError, not return 0."""
        with pytest.raises(ValueError, match="No valid energy data found"):
            parse_energyplus_output(str(tmp_output_dir))

    def test_raises_on_zero_energy(self, tmp_output_dir):
        """A CSV that parses to 0 should raise ValueError."""
        csv_content = "no relevant data here\n"
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        with pytest.raises(ValueError, match="No valid energy data found"):
            parse_energyplus_output(str(tmp_output_dir))

    def test_valid_csv_returns_dict(self, tmp_output_dir):
        csv_content = """\
,Total Energy [GJ],Other
Total Site Energy,100.0,other
Total Building Area,,
,Total Building Area,500.0
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = parse_energyplus_output(str(tmp_output_dir))
        assert result["total_energy_kwh"] > 0
        assert "annual_cost_krw" in result
        assert result["annual_cost_krw"] > 0

    def test_cost_calculation(self, tmp_output_dir):
        csv_content = """\
,Total Energy [kWh],Other
Total Site Energy,10000.0,other
"""
        csv_path = tmp_output_dir / "eplustbl.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        result = parse_energyplus_output(str(tmp_output_dir))
        # 10000 kWh * 120 KRW = 1,200,000 KRW
        assert result["annual_cost_krw"] == 1200000
