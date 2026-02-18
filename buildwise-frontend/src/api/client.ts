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

// Response error interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("buildwise_user_id");
      localStorage.removeItem("buildwise_user_name");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

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

export interface SimulationHistoryItem {
  config_id: string;
  climate_city: string;
  period_type: string;
  strategies: string[];
  total: number;
  completed: number;
  failed: number;
  created_at: string;
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
  update: (id: string, data: { name?: string; description?: string }) =>
    api.patch<Project>(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
};

export const buildingsApi = {
  list: (projectId: string) =>
    api.get<Building[]>(`/projects/${projectId}/buildings`),
  create: (projectId: string, name: string, bps: Record<string, unknown>) =>
    api.post<Building>(`/projects/${projectId}/buildings`, { name, bps }),
  get: (projectId: string, buildingId: string) =>
    api.get<Building>(`/projects/${projectId}/buildings/${buildingId}`),
  update: (projectId: string, buildingId: string, data: { name?: string }) =>
    api.patch<Building>(`/projects/${projectId}/buildings/${buildingId}`, data),
  updateBps: (
    projectId: string,
    buildingId: string,
    patch: Record<string, unknown>,
  ) =>
    api.patch<Building>(
      `/projects/${projectId}/buildings/${buildingId}/bps`,
      patch,
    ),
  simulations: (projectId: string, buildingId: string) =>
    api.get<SimulationHistoryItem[]>(
      `/projects/${projectId}/buildings/${buildingId}/simulations`,
    ),
  delete: (projectId: string, buildingId: string) =>
    api.delete(`/projects/${projectId}/buildings/${buildingId}`),
  clone: (projectId: string, buildingId: string) =>
    api.post<Building>(`/projects/${projectId}/buildings/${buildingId}/clone`),
};

export const templatesApi = {
  list: () => api.get<BuildingTemplate[]>("/buildings/templates"),
  get: (type: string) => api.get<BuildingTemplate>(`/buildings/templates/${type}`),
};

export interface PlanInfo {
  plan: string;
  price_monthly_usd: number;
  max_buildings: number;
  max_simulations_monthly: number;
  allowed_strategies: string[];
  has_pdf_export: boolean;
}

export interface UsageInfo {
  plan: string;
  simulations_used: number;
  simulations_limit: number;
  buildings_count: number;
  buildings_limit: number;
  credits_remaining: number;
}

export interface UserInfo {
  id: string;
  email: string;
  name: string | null;
  plan: string;
  simulation_count_monthly: number;
  created_at: string;
}

export const billingApi = {
  plans: () => api.get<PlanInfo[]>("/billing/plans"),
  usage: () => api.get<UsageInfo>("/billing/usage"),
};

export const authApi = {
  me: () => api.get<UserInfo>("/auth/me"),
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
