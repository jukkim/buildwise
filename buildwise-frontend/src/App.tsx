import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import { PageSkeleton } from "./components/Skeleton";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const BuildingEditor = lazy(() => import("./pages/BuildingEditor"));
const SimulationProgress = lazy(() => import("./pages/SimulationProgress"));
const Results = lazy(() => import("./pages/Results"));
const Login = lazy(() => import("./pages/Login"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RequireAuth({ children }: { children: React.ReactNode }) {
  const userId = localStorage.getItem("buildwise_user_id");
  if (!userId) return <Navigate to="/login" replace />;
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
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/projects" replace />} />
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
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
