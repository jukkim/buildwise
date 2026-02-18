"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("auth0_sub", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("plan", sa.Enum("free", "pro", "enterprise", name="userplan"), nullable=False, server_default="free"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True)),
        sa.Column("simulation_count_monthly", sa.Integer, nullable=False, server_default="0"),
        sa.Column("simulation_count_reset_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("plan", sa.Enum("free", "pro", "enterprise", name="userplan", create_type=False), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.Enum("active", "archived", "deleted", name="projectstatus"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Buildings
    op.create_table(
        "buildings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("building_type", sa.Enum("large_office", "medium_office", "small_office", "standalone_retail", "primary_school", "hospital", name="buildingtype"), nullable=False),
        sa.Column("bps_json", postgresql.JSONB, nullable=False),
        sa.Column("bps_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("model_3d_url", sa.Text),
        sa.Column("thumbnail_url", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Simulation Configs
    op.create_table(
        "simulation_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("building_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("climate_city", sa.String(50), nullable=False),
        sa.Column("epw_file", sa.String(100), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False, server_default="1year"),
        sa.Column("period_start", sa.String(10), nullable=False, server_default="01/01"),
        sa.Column("period_end", sa.String(10), nullable=False, server_default="12/31"),
        sa.Column("timestep_per_hour", sa.Integer, nullable=False, server_default="4"),
        sa.Column("strategies", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Simulation Runs
    _sim_strategy = sa.Enum("baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", name="simulationstrategy")
    _sim_status = sa.Enum("pending", "queued", "running", "completed", "failed", "cancelled", name="simulationstatus")

    op.create_table(
        "simulation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("strategy", _sim_strategy, nullable=False),
        sa.Column("status", _sim_status, nullable=False, server_default="pending"),
        sa.Column("idf_url", sa.Text),
        sa.Column("idf_hash", sa.String(64)),
        sa.Column("result_csv_url", sa.Text),
        sa.Column("error_log", sa.Text),
        sa.Column("equipment_baseline_hash", sa.String(64)),
        sa.Column("fair_comparison_verified", sa.Boolean, server_default="false"),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("runner_type", sa.String(20)),
        sa.Column("runner_id", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("config_id", "strategy", name="unique_strategy_per_config"),
    )

    # Energy Results
    op.create_table(
        "energy_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("total_energy_kwh", sa.Float, nullable=False),
        sa.Column("hvac_energy_kwh", sa.Float),
        sa.Column("cooling_energy_kwh", sa.Float),
        sa.Column("heating_energy_kwh", sa.Float),
        sa.Column("fan_energy_kwh", sa.Float),
        sa.Column("pump_energy_kwh", sa.Float),
        sa.Column("lighting_energy_kwh", sa.Float),
        sa.Column("equipment_energy_kwh", sa.Float),
        sa.Column("eui_kwh_m2", sa.Float, nullable=False),
        sa.Column("peak_demand_kw", sa.Float),
        sa.Column("peak_demand_month", sa.Integer),
        sa.Column("savings_kwh", sa.Float),
        sa.Column("savings_pct", sa.Float),
        sa.Column("annual_cost_krw", sa.Integer),
        sa.Column("annual_savings_krw", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Comfort Results
    op.create_table(
        "comfort_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("mean_pmv", sa.Float),
        sa.Column("pmv_std_dev", sa.Float),
        sa.Column("unmet_hours_heating", sa.Float),
        sa.Column("unmet_hours_cooling", sa.Float),
        sa.Column("unmet_hours_total", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Zone Results
    op.create_table(
        "zone_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("zone_name", sa.String(100), nullable=False),
        sa.Column("avg_temp_c", sa.Float),
        sa.Column("max_temp_c", sa.Float),
        sa.Column("min_temp_c", sa.Float),
        sa.Column("avg_pmv", sa.Float),
        sa.Column("unmet_hours", sa.Float),
        sa.Column("zone_energy_kwh", sa.Float),
        sa.UniqueConstraint("run_id", "zone_name", name="unique_zone_per_run"),
    )


def downgrade() -> None:
    op.drop_table("zone_results")
    op.drop_table("comfort_results")
    op.drop_table("energy_results")
    op.drop_table("simulation_runs")
    op.drop_table("simulation_configs")
    op.drop_table("buildings")
    op.drop_table("projects")
    op.drop_table("subscriptions")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS simulationstatus")
    op.execute("DROP TYPE IF EXISTS simulationstrategy")
    op.execute("DROP TYPE IF EXISTS buildingtype")
    op.execute("DROP TYPE IF EXISTS projectstatus")
    op.execute("DROP TYPE IF EXISTS userplan")
