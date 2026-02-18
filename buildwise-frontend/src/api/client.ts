import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// MVP: inject user ID header for dev auth
api.interceptors.request.use((config) => {
  const userId = localStorage.getItem("buildwise_user_id");
  if (userId) {
    config.headers["X-User-Id"] = userId;
  }
  return config;
});

export default api;

// ---- Type definitions ----

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  buildings_count: number;
  created_at: string;
  updated_at: string;
}

export interface Building {
  id: string;
  project_id: string;
  name: string;
  building_type: string;
  bps: Record<string, unknown>;
  bps_version: number;
  model_3d_url: string | null;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface BuildingTemplate {
  building_type: string;
  name: string;
  description: string;
  default_bps: Record<string, unknown>;
  baseline_eui_kwh_m2: number | null;
  available_strategies: string[];
}

export interface SimulationProgress {
  config_id: string;
  total_strategies: number;
  completed: number;
  running: number;
  failed: number;
  runs: SimulationRun[];
  estimated_remaining_seconds: number | null;
}

export interface SimulationRun {
  id: string;
  config_id: string;
  strategy: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface EnergyResult {
  strategy: string;
  total_energy_kwh: number;
  hvac_energy_kwh: number | null;
  cooling_energy_kwh: number | null;
  heating_energy_kwh: number | null;
  fan_energy_kwh: number | null;
  eui_kwh_m2: number;
  peak_demand_kw: number | null;
  savings_pct: number | null;
  annual_cost_krw: number | null;
  annual_savings_krw: number | null;
}

export interface StrategyComparison {
  building_name: string;
  building_type: string;
  climate_city: string;
  baseline: EnergyResult | null;
  strategies: EnergyResult[];
  recommended_strategy: string | null;
  recommendation_reason: string | null;
}

// ---- API functions ----

export const projectsApi = {
  list: (page = 1, perPage = 20) =>
    api.get<{ data: Project[]; meta: PaginationMeta }>("/projects", {
      params: { page, per_page: perPage },
    }),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (name: string, description?: string) =>
    api.post<Project>("/projects", { name, description }),
};

export const buildingsApi = {
  create: (projectId: string, name: string, bps: Record<string, unknown>) =>
    api.post<Building>(`/projects/${projectId}/buildings`, { name, bps }),
  get: (projectId: string, buildingId: string) =>
    api.get<Building>(`/projects/${projectId}/buildings/${buildingId}`),
  updateBps: (
    projectId: string,
    buildingId: string,
    patch: Record<string, unknown>,
  ) =>
    api.patch<Building>(
      `/projects/${projectId}/buildings/${buildingId}/bps`,
      patch,
    ),
};

export const templatesApi = {
  list: () => api.get<BuildingTemplate[]>("/buildings/templates"),
  get: (type: string) => api.get<BuildingTemplate>(`/buildings/templates/${type}`),
};

export const simulationsApi = {
  start: (buildingId: string, climateCity = "Seoul", periodType = "1year") =>
    api.post<SimulationProgress>("/simulations", {
      building_id: buildingId,
      climate_city: climateCity,
      period_type: periodType,
    }),
  progress: (configId: string) =>
    api.get<SimulationProgress>(`/simulations/${configId}/progress`),
  cancel: (configId: string) =>
    api.post(`/simulations/${configId}/cancel`),
  results: (configId: string) =>
    api.get<StrategyComparison>(`/simulations/${configId}/results`),
};
