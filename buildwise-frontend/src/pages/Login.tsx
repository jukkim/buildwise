import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/api/client";
import useDocumentTitle from "@/hooks/useDocumentTitle";

export default function Login() {
  useDocumentTitle("Sign In");
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@buildwise.ai");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      // MVP: lookup user by email via auth endpoint
      const res = await api.post<{ id: string; name: string; email: string }>(
        "/auth/login",
        { email },
      );
      localStorage.setItem("buildwise_user_id", res.data.id);
      localStorage.setItem("buildwise_user_name", res.data.name ?? res.data.email);
      navigate("/projects");
    } catch {
      // Fallback: try demo user ID directly
      try {
        const res = await api.get<{ id: string; name: string; email: string }>(
          "/auth/me",
          { headers: { "X-User-Id": email } },
        );
        localStorage.setItem("buildwise_user_id", res.data.id);
        localStorage.setItem("buildwise_user_name", res.data.name ?? res.data.email);
        navigate("/projects");
      } catch {
        setError("User not found. Run 'make seed' to create the demo user.");
      }
    }
    setLoading(false);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-blue-600">BuildWise</h1>
          <p className="mt-1 text-sm text-gray-500">Building Energy Simulation Platform</p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="demo@buildwise.ai"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLogin();
              }}
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <button
            onClick={handleLogin}
            disabled={loading || !email.trim()}
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In (Dev Mode)"}
          </button>

          <p className="text-center text-xs text-gray-400">
            MVP development auth. Use demo@buildwise.ai after running seed.
          </p>
        </div>
      </div>
    </div>
  );
}
