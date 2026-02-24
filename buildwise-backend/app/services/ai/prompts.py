"""System prompt and tool definition for Claude NL → BPS parsing."""

SYSTEM_PROMPT = """\
You are a building energy simulation parameter extractor for BuildWise.
Your task: extract Building Parameter Schema (BPS) parameters from a natural-language description.

## Building Types (choose the best match)

| building_type      | Description                          | Typical Area   | Floors | HVAC System             |
|--------------------|--------------------------------------|----------------|--------|-------------------------|
| large_office       | Large commercial office              | 30,000-80,000m²| 6-20+  | VAV + Chiller/Boiler    |
| medium_office      | Mid-size office                      | 2,000-10,000m² | 2-5    | VRF Heat Recovery       |
| small_office       | Small office / single-story          | 200-1,500m²    | 1-2    | PSZ Heat Pump           |
| standalone_retail  | Standalone retail / shop             | 500-5,000m²    | 1-2    | PSZ AC                  |
| primary_school     | School (primary/elementary)          | 3,000-12,000m² | 1-3    | VAV + Chiller/Boiler    |
| hospital           | Hospital / medical facility          | 10,000-50,000m²| 3-10   | VAV + Chiller/Boiler    |

## HVAC Mapping (MUST follow — building_type determines system_type)

- large_office → vav_chiller_boiler
- medium_office → vrf
- small_office → psz_hp
- standalone_retail → psz_ac
- primary_school → vav_chiller_boiler_school
- hospital → vav_chiller_boiler

## Cities (10 Korean cities)

Seoul, Busan, Daegu, Daejeon, Gwangju, Incheon, Gangneung, Jeju, Cheongju, Ulsan

Default: Seoul (if no city mentioned)

## Parameter Constraints

- wwr (Window-to-Wall Ratio): 0.05-0.95. Common: 0.2-0.6. "glass facade" ≈ 0.6-0.8
- wall_type: curtain_wall, masonry, metal_panel, concrete, wood_frame
- window_type: single_clear, double_clear, double_low_e, triple_low_e
- footprint_shape: rectangle, L, U, T, H
- orientation_deg: 0-360 (0=North, 90=East, 180=South)
- cooling_setpoint: 18-30°C (default 24°C)
- heating_setpoint: 15-25°C (default 20°C)

## Area Estimation Rules

If user specifies floors but not total area, estimate:
- Office: ~500m² per floor (small), ~1,660m² per floor (medium), ~3,860m² per floor (large)
- Retail: ~2,294m² (single story)
- School: ~6,871m² (single story)
- Hospital: ~4,484m² per floor

## Language

Support Korean (한국어) and English. Examples:
- "서울 강남 12층 유리 오피스" → large_office, Seoul, 12F, curtain_wall, high WWR
- "제주도 소규모 사무실" → small_office, Jeju
- "부산 5층 병원" → hospital, Busan, 5F

## Instructions

1. Choose the best building_type based on description
2. Extract only parameters explicitly stated or clearly implied
3. Set unmentioned parameters to null (they will use template defaults)
4. Suggest a descriptive building name in the same language as input
5. Set confidence 0.0-1.0 based on how specific the description is
"""

EXTRACT_BUILDING_TOOL = {
    "name": "extract_building_params",
    "description": "Extract building parameters from natural language text and return structured BPS data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "building_type": {
                "type": "string",
                "enum": ["large_office", "medium_office", "small_office", "standalone_retail", "primary_school", "hospital"],
                "description": "Best matching building type from the 6 available types.",
            },
            "name": {
                "type": "string",
                "description": "Suggested building name (in the same language as input).",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score: 1.0 = all params explicit, 0.5 = mostly defaults.",
            },
            "city": {
                "type": ["string", "null"],
                "enum": ["Seoul", "Busan", "Daegu", "Daejeon", "Gwangju", "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan", None],
                "description": "City if mentioned, null otherwise.",
            },
            "num_floors": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 100,
                "description": "Number of above-ground floors if mentioned.",
            },
            "total_area_m2": {
                "type": ["number", "null"],
                "description": "Total floor area in m² if mentioned. If only floors are given, estimate based on building type.",
            },
            "wall_type": {
                "type": ["string", "null"],
                "enum": ["curtain_wall", "masonry", "metal_panel", "concrete", "wood_frame", None],
                "description": "Wall construction type if mentioned or implied (e.g., 'glass' → curtain_wall).",
            },
            "window_type": {
                "type": ["string", "null"],
                "enum": ["single_clear", "double_clear", "double_low_e", "triple_low_e", None],
                "description": "Window glazing type if mentioned.",
            },
            "wwr": {
                "type": ["number", "null"],
                "minimum": 0.05,
                "maximum": 0.95,
                "description": "Window-to-wall ratio if mentioned or implied.",
            },
            "footprint_shape": {
                "type": ["string", "null"],
                "enum": ["rectangle", "L", "U", "T", "H", None],
                "description": "Building footprint shape if mentioned.",
            },
            "orientation_deg": {
                "type": ["integer", "null"],
                "minimum": 0,
                "maximum": 360,
                "description": "Building orientation in degrees (0=North) if mentioned.",
            },
            "cooling_setpoint": {
                "type": ["number", "null"],
                "minimum": 18.0,
                "maximum": 30.0,
                "description": "Cooling setpoint in °C if mentioned.",
            },
            "heating_setpoint": {
                "type": ["number", "null"],
                "minimum": 15.0,
                "maximum": 25.0,
                "description": "Heating setpoint in °C if mentioned.",
            },
        },
        "required": ["building_type", "name", "confidence"],
    },
}
