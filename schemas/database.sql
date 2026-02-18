-- =============================================================================
-- BuildWise Database Schema
-- PostgreSQL 16 + TimescaleDB
-- =============================================================================
-- 실행: psql -U buildwise -d buildwise -f database.sql
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";

-- =============================================================================
-- Enums
-- =============================================================================

CREATE TYPE user_plan AS ENUM ('free', 'pro', 'enterprise');
CREATE TYPE project_status AS ENUM ('active', 'archived', 'deleted');
CREATE TYPE simulation_strategy AS ENUM (
    'baseline', 'm0', 'm1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8'
);
CREATE TYPE simulation_status AS ENUM (
    'pending', 'queued', 'running', 'completed', 'failed', 'cancelled'
);
CREATE TYPE building_type AS ENUM (
    'large_office', 'medium_office', 'small_office',
    'standalone_retail', 'primary_school', 'hospital'
);

-- =============================================================================
-- Users
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth0_sub VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(200),
    plan user_plan NOT NULL DEFAULT 'free',
    plan_expires_at TIMESTAMPTZ,
    simulation_count_monthly INT NOT NULL DEFAULT 0,
    simulation_count_reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_auth0_sub ON users(auth0_sub);
CREATE INDEX idx_users_email ON users(email);

-- =============================================================================
-- Projects
-- =============================================================================

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status project_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);

-- =============================================================================
-- Buildings (BPS as JSONB)
-- =============================================================================

CREATE TABLE buildings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    building_type building_type NOT NULL,
    bps_json JSONB NOT NULL,
    bps_version INT NOT NULL DEFAULT 1,
    model_3d_url TEXT,            -- GCS URL for glTF/glb
    thumbnail_url TEXT,           -- 건물 썸네일
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- BPS JSON 유효성은 애플리케이션 레이어에서 JSON Schema로 검증
    CONSTRAINT bps_has_geometry CHECK (bps_json ? 'geometry'),
    CONSTRAINT bps_has_hvac CHECK (bps_json ? 'hvac')
);

CREATE INDEX idx_buildings_project_id ON buildings(project_id);
CREATE INDEX idx_buildings_type ON buildings(building_type);
CREATE INDEX idx_buildings_bps_city ON buildings USING GIN ((bps_json -> 'location' -> 'city'));

-- =============================================================================
-- Simulation Configs
-- =============================================================================

CREATE TABLE simulation_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    building_id UUID NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    climate_city VARCHAR(50) NOT NULL,
    epw_file VARCHAR(100) NOT NULL,
    period_type VARCHAR(20) NOT NULL DEFAULT '1year',
    period_start DATE NOT NULL DEFAULT '2024-01-01',
    period_end DATE NOT NULL DEFAULT '2024-12-31',
    timestep_per_hour INT NOT NULL DEFAULT 4,
    strategies simulation_strategy[] NOT NULL DEFAULT '{baseline,m0,m1,m2,m3,m4,m5,m6,m7,m8}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_timestep CHECK (timestep_per_hour IN (1, 2, 4, 6))
);

CREATE INDEX idx_sim_configs_building_id ON simulation_configs(building_id);

-- =============================================================================
-- Simulation Runs (1 row per strategy)
-- =============================================================================

CREATE TABLE simulation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_id UUID NOT NULL REFERENCES simulation_configs(id) ON DELETE CASCADE,
    strategy simulation_strategy NOT NULL,
    status simulation_status NOT NULL DEFAULT 'pending',

    -- 파일 참조 (GCS)
    idf_url TEXT,                 -- 생성된 IDF 파일 GCS URL
    idf_hash VARCHAR(64),         -- SHA256 해시 (재현성 검증)
    result_csv_url TEXT,          -- eplusout.csv GCS URL
    error_log TEXT,               -- E+ 에러 로그

    -- 공정비교 메타데이터
    equipment_baseline_hash VARCHAR(64),  -- M0 설비 크기 해시
    fair_comparison_verified BOOLEAN DEFAULT FALSE,

    -- 타이밍
    queued_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INT,

    -- 실행 환경
    runner_type VARCHAR(20),       -- 'cloud_run' | 'gke_job'
    runner_id VARCHAR(200),        -- Cloud Run job ID 또는 K8s pod name

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_strategy_per_config UNIQUE (config_id, strategy)
);

CREATE INDEX idx_sim_runs_config_id ON simulation_runs(config_id);
CREATE INDEX idx_sim_runs_status ON simulation_runs(status);
CREATE INDEX idx_sim_runs_strategy ON simulation_runs(strategy);

-- =============================================================================
-- Energy Results (요약)
-- =============================================================================

CREATE TABLE energy_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID UNIQUE NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,

    -- 연간 에너지
    total_energy_kwh DOUBLE PRECISION NOT NULL,
    hvac_energy_kwh DOUBLE PRECISION,
    cooling_energy_kwh DOUBLE PRECISION,
    heating_energy_kwh DOUBLE PRECISION,
    fan_energy_kwh DOUBLE PRECISION,
    pump_energy_kwh DOUBLE PRECISION,
    lighting_energy_kwh DOUBLE PRECISION,
    equipment_energy_kwh DOUBLE PRECISION,

    -- KPI
    eui_kwh_m2 DOUBLE PRECISION NOT NULL,
    peak_demand_kw DOUBLE PRECISION,
    peak_demand_month INT,           -- 피크 발생 월

    -- 비교 (vs Baseline)
    savings_kwh DOUBLE PRECISION,
    savings_pct DOUBLE PRECISION,    -- 0~100
    annual_cost_krw BIGINT,          -- 연간 에너지 비용 (원)
    annual_savings_krw BIGINT,       -- 연간 절감액 (원)

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_energy_results_run_id ON energy_results(run_id);

-- =============================================================================
-- Comfort Results (요약)
-- =============================================================================

CREATE TABLE comfort_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID UNIQUE NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,

    mean_pmv DOUBLE PRECISION,
    pmv_std_dev DOUBLE PRECISION,
    unmet_hours_heating DOUBLE PRECISION,
    unmet_hours_cooling DOUBLE PRECISION,
    unmet_hours_total DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Zone Results (존별 요약)
-- =============================================================================

CREATE TABLE zone_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    zone_name VARCHAR(100) NOT NULL,

    avg_temp_c DOUBLE PRECISION,
    max_temp_c DOUBLE PRECISION,
    min_temp_c DOUBLE PRECISION,
    avg_pmv DOUBLE PRECISION,
    unmet_hours DOUBLE PRECISION,
    zone_energy_kwh DOUBLE PRECISION,

    CONSTRAINT unique_zone_per_run UNIQUE (run_id, zone_name)
);

CREATE INDEX idx_zone_results_run_id ON zone_results(run_id);

-- =============================================================================
-- Energy Time Series (TimescaleDB Hypertable)
-- =============================================================================

CREATE TABLE energy_timeseries (
    time TIMESTAMPTZ NOT NULL,
    run_id UUID NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    variable_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL
);

-- TimescaleDB hypertable 변환
SELECT create_hypertable('energy_timeseries', 'time');

-- 복합 인덱스
CREATE INDEX idx_ts_run_var ON energy_timeseries(run_id, variable_name, time DESC);

-- 데이터 보관 정책: 1년 이상 된 시계열은 압축
SELECT add_compression_policy('energy_timeseries', INTERVAL '90 days');

-- 1년 이상 된 데이터 자동 삭제 (선택적)
-- SELECT add_retention_policy('energy_timeseries', INTERVAL '365 days');

-- =============================================================================
-- Monthly Aggregates (미리 계산된 월별 집계)
-- =============================================================================

CREATE TABLE energy_monthly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    month INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    variable_name VARCHAR(100) NOT NULL,
    total_kwh DOUBLE PRECISION NOT NULL,
    peak_kw DOUBLE PRECISION,
    avg_value DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,

    CONSTRAINT unique_monthly UNIQUE (run_id, month, variable_name)
);

CREATE INDEX idx_monthly_run_id ON energy_monthly(run_id);

-- =============================================================================
-- Subscriptions & Billing
-- =============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan user_plan NOT NULL DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usage_credits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credits_total INT NOT NULL DEFAULT 0,
    credits_used INT NOT NULL DEFAULT 0,
    purchased_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    CONSTRAINT positive_credits CHECK (credits_total >= credits_used)
);

CREATE INDEX idx_credits_user_id ON usage_credits(user_id);

-- =============================================================================
-- Plan Limits (참조 테이블)
-- =============================================================================

CREATE TABLE plan_limits (
    plan user_plan PRIMARY KEY,
    max_buildings INT NOT NULL,
    max_simulations_monthly INT NOT NULL,
    allowed_strategies simulation_strategy[] NOT NULL,
    has_pdf_export BOOLEAN NOT NULL DEFAULT FALSE,
    has_api_access BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO plan_limits VALUES
    ('free', 1, 5, '{baseline,m0,m1,m2,m3}', FALSE, FALSE),
    ('pro', -1, 100, '{baseline,m0,m1,m2,m3,m4,m5,m6,m7,m8}', TRUE, FALSE),
    ('enterprise', -1, -1, '{baseline,m0,m1,m2,m3,m4,m5,m6,m7,m8}', TRUE, TRUE);

-- =============================================================================
-- Audit Log
-- =============================================================================

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);

-- =============================================================================
-- Updated_at Trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER tr_projects_updated_at
    BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER tr_buildings_updated_at
    BEFORE UPDATE ON buildings FOR EACH ROW EXECUTE FUNCTION update_updated_at();
