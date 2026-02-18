"""Seed script: create demo user, project, and buildings for development."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import async_session_factory, engine  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.project import Building, BuildingType, Project  # noqa: E402
from app.models.user import User, UserPlan  # noqa: E402


# --- Demo BPS data (from templates) ---

DEMO_BUILDINGS = [
    {
        "name": "Headquarters Tower",
        "building_type": BuildingType.LARGE_OFFICE,
        "bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "large_office",
                "num_floors_above": 12,
                "num_floors_below": 1,
                "total_floor_area_m2": 46320,
                "floor_to_floor_height_m": 3.96,
                "aspect_ratio": 1.5,
                "footprint_shape": "rectangle",
                "wwr": 0.38,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "curtain_wall",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vav_chiller_boiler",
                "autosize": True,
                "chillers": {"count": 3, "cop": 6.1},
                "boilers": {"count": 2, "efficiency": 0.80},
                "ahu": {"count": 3, "has_economizer": True},
                "vav_terminals": {"reheat_type": "hot_water", "min_airflow_ratio": 0.30},
            },
            "internal_loads": {"people_density": 0.0565, "lighting_power_density": 10.76, "equipment_power_density": 10.76},
            "schedules": {"occupancy_type": "office_standard"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
    },
    {
        "name": "Branch Office A",
        "building_type": BuildingType.MEDIUM_OFFICE,
        "bps": {
            "location": {"city": "Busan"},
            "geometry": {
                "building_type": "medium_office",
                "num_floors_above": 3,
                "num_floors_below": 0,
                "total_floor_area_m2": 4982,
                "floor_to_floor_height_m": 3.96,
                "aspect_ratio": 1.5,
                "footprint_shape": "rectangle",
                "wwr": 0.33,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "curtain_wall",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vrf",
                "autosize": True,
                "vrf_outdoor_units": {"count": 3, "cop_cooling": 4.0, "cop_heating": 3.5, "heat_recovery": True},
            },
            "internal_loads": {"people_density": 0.0565, "lighting_power_density": 10.76, "equipment_power_density": 10.76},
            "schedules": {"occupancy_type": "office_standard"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
    },
]


async def seed():
    """Create demo data."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if demo user exists
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.email == "demo@buildwise.ai"))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Demo user already exists: {existing.id}")
            print("Skipping seed.")
            return

        # Create demo user
        user = User(
            auth0_sub="auth0|demo_user_001",
            email="demo@buildwise.ai",
            name="Demo User",
            plan=UserPlan.PRO,
        )
        db.add(user)
        await db.flush()
        print(f"Created demo user: {user.id}")

        # Create demo project
        project = Project(
            user_id=user.id,
            name="Seoul Campus Energy Optimization",
            description="Multi-building campus energy simulation for headquarters and branch offices.",
        )
        db.add(project)
        await db.flush()
        print(f"Created demo project: {project.id}")

        # Create demo buildings
        for bld_data in DEMO_BUILDINGS:
            building = Building(
                project_id=project.id,
                name=bld_data["name"],
                building_type=bld_data["building_type"],
                bps_json=bld_data["bps"],
                bps_version=1,
            )
            db.add(building)
            await db.flush()
            print(f"Created building: {building.name} ({building.id})")

        await db.commit()

    print("\nSeed complete!")
    print(f"Demo user ID: {user.id}")
    print("Use this ID in X-User-Id header for API requests.")


if __name__ == "__main__":
    asyncio.run(seed())
