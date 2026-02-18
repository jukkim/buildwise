import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import ProjectDetail from "./pages/ProjectDetail";
import BuildingEditor from "./pages/BuildingEditor";
import SimulationProgress from "./pages/SimulationProgress";
import Results from "./pages/Results";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
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
      </Route>
    </Routes>
  );
}
