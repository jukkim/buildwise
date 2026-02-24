import { lazy, Suspense, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import { PageSkeleton } from "./components/Skeleton";
import useAuth from "./auth/useAuth";

const LandingPage = lazy(() => import("./pages/LandingPage"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const BuildingEditor = lazy(() => import("./pages/BuildingEditor"));
const SimulationProgress = lazy(() => import("./pages/SimulationProgress"));
const Results = lazy(() => import("./pages/Results"));
const CityComparison = lazy(() => import("./pages/CityComparison"));
const MultiCityProgress = lazy(() => import("./pages/MultiCityProgress"));
const Login = lazy(() => import("./pages/Login"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, login } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      login();
    }
  }, [isLoading, isAuthenticated, login]);

  if (isLoading || !isAuthenticated) return <PageSkeleton />;

  return <>{children}</>;
}

function PageFallback() {
  return <PageSkeleton />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/projects" element={<Dashboard />} />
            <Route path="/projects/:projectId" element={<ProjectDetail />} />
            <Route
              path="/projects/:projectId/buildings/:buildingId"
              element={<BuildingEditor />}
            />
            <Route
              path="/simulations/:configId/progress"
              element={<SimulationProgress />}
            />
            <Route path="/simulations/:configId/results" element={<Results />} />
            <Route path="/compare" element={<CityComparison />} />
            <Route path="/compare/progress" element={<MultiCityProgress />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
