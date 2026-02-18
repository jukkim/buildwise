import { describe, it, expect } from "vitest";
import { projectsApi, buildingsApi, simulationsApi, billingApi, authApi } from "@/api/client";

describe("API client", () => {
  it("projectsApi has required methods", () => {
    expect(projectsApi.list).toBeDefined();
    expect(projectsApi.get).toBeDefined();
    expect(projectsApi.create).toBeDefined();
    expect(projectsApi.update).toBeDefined();
    expect(projectsApi.delete).toBeDefined();
  });

  it("buildingsApi has required methods", () => {
    expect(buildingsApi.list).toBeDefined();
    expect(buildingsApi.create).toBeDefined();
    expect(buildingsApi.get).toBeDefined();
    expect(buildingsApi.update).toBeDefined();
    expect(buildingsApi.updateBps).toBeDefined();
    expect(buildingsApi.delete).toBeDefined();
    expect(buildingsApi.simulations).toBeDefined();
    expect(buildingsApi.clone).toBeDefined();
  });

  it("simulationsApi has required methods", () => {
    expect(simulationsApi.start).toBeDefined();
    expect(simulationsApi.progress).toBeDefined();
    expect(simulationsApi.cancel).toBeDefined();
    expect(simulationsApi.results).toBeDefined();
  });

  it("billingApi has required methods", () => {
    expect(billingApi.plans).toBeDefined();
    expect(billingApi.usage).toBeDefined();
  });

  it("authApi has required methods", () => {
    expect(authApi.me).toBeDefined();
  });
});
