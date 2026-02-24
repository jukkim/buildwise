import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import api from "@/api/client";
import useAuth from "@/auth/useAuth";
import useDocumentTitle from "@/hooks/useDocumentTitle";

export default function Login() {
  useDocumentTitle("Sign In");
  const navigate = useNavigate();
  const { isAuthenticated, login: auth0Login } = useAuth();

  const [email, setEmail] = useState(
    () => localStorage.getItem("buildwise_last_email") ?? "demo@buildwise.ai",
  );
  const [rememberEmail, setRememberEmail] = useState(
    () => !!localStorage.getItem("buildwise_last_email"),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If already authenticated (Auth0 redirect back), go to projects
  if (isAuthenticated) {
    return <Navigate to="/projects" replace />;
  }

  const handleDevLogin = async () => {
    setLoading(true);
    setError(null);
    if (rememberEmail) {
      localStorage.setItem("buildwise_last_email", email);
    } else {
      localStorage.removeItem("buildwise_last_email");
    }
    try {
      const res = await api.post<{ id: string; name: string; email: string }>(
        "/auth/login",
        { email },
      );
      localStorage.setItem("buildwise_user_id", res.data.id);
      localStorage.setItem(
        "buildwise_user_name",
        res.data.name ?? res.data.email,
      );
      window.dispatchEvent(new Event("buildwise-auth-change"));
      navigate("/projects");
    } catch (err: unknown) {
      const errObj = err as { response?: { status?: number; data?: { detail?: string } } };
      const statusCode = errObj?.response?.status;
      const detail = errObj?.response?.data?.detail;
      if (statusCode === 400 || statusCode === 403) {
        // Server has Auth0 configured or dev login disabled — redirect to Auth0
        auth0Login();
        return;
      } else {
        setError(
          detail || "User not found. Run 'make seed' to create the demo user.",
        );
      }
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900" />
      {/* Subtle grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
      }} />
      {/* Glow orbs */}
      <div className="absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl" />

      <div className="relative z-10 w-full max-w-sm px-4">
        {/* Card */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 shadow-2xl backdrop-blur-xl">
          <div className="mb-8 text-center">
            {/* Logo */}
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500 shadow-lg shadow-blue-500/25">
              <svg className="h-7 w-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-white">BuildWise</h1>
            <p className="mt-2 text-sm text-blue-200/60">
              Simulate. Compare. Optimize.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/50"
                placeholder="demo@buildwise.ai"
                autoFocus
                disabled={loading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && email.trim()) handleDevLogin();
                }}
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-400">
              <input
                type="checkbox"
                checked={rememberEmail}
                onChange={(e) => setRememberEmail(e.target.checked)}
                className="rounded border-white/20 bg-white/5"
              />
              Remember email
            </label>

            {error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2">
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            <button
              onClick={handleDevLogin}
              disabled={loading || !email.trim()}
              className="w-full rounded-xl bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-400 hover:shadow-blue-400/30 disabled:opacity-50 disabled:shadow-none transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Signing in...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </div>
        </div>

        {/* Tagline under card */}
        <p className="mt-6 text-center text-xs text-gray-500">
          Building Energy Simulation Platform
        </p>
      </div>
    </div>
  );
}
