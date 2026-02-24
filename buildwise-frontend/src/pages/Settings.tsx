import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { authApi, billingApi, type PlanInfo } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import { STRATEGY_LABELS } from "@/constants/strategies";

export default function Settings() {
  useDocumentTitle("Settings");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const { data: user, isLoading: userLoading, isError: userError, refetch: refetchUser } = useQuery({
    queryKey: ["user-me"],
    queryFn: () => authApi.me().then((r) => r.data),
  });

  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ["billing-usage"],
    queryFn: () => billingApi.usage().then((r) => r.data),
  });

  const { data: plans } = useQuery({
    queryKey: ["billing-plans"],
    queryFn: () => billingApi.plans().then((r) => r.data),
  });

  if (userLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    );
  }

  if (userError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-red-600 font-medium">Failed to load settings</p>
        <button onClick={() => refetchUser()} className="mt-3 rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      {/* Profile */}
      <section className="rounded-xl bg-white shadow-sm p-6 mb-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-lg font-bold text-blue-700">
            {(user?.name ?? "U").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-800">{user?.name ?? "User"}</h2>
            <p className="text-sm text-gray-500">{user?.email}</p>
          </div>
        </div>
        <dl className="space-y-3">
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">Name</dt>
            <dd className="text-sm font-medium text-gray-900">{user?.name ?? "-"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">Email</dt>
            <dd className="text-sm font-medium text-gray-900">{user?.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">User ID</dt>
            <dd className="text-sm font-mono text-gray-400">
              {user?.id ? `${user.id.slice(0, 8)}...${user.id.slice(-4)}` : "-"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">Member Since</dt>
            <dd className="text-sm font-medium text-gray-900">
              {user?.created_at ? (
                <>
                  {new Date(user.created_at).toLocaleDateString()}
                  <span className="ml-1 text-gray-400 font-normal">
                    ({Math.floor((Date.now() - new Date(user.created_at).getTime()) / 86400000)}d ago)
                  </span>
                </>
              ) : "-"}
            </dd>
          </div>
        </dl>
      </section>

      {/* Current Plan & Usage */}
      <section className="rounded-xl bg-white shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Plan & Usage</h2>
        {usageLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : usage ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-800 capitalize">
                {usage.plan === "free" && (
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
                {usage.plan === "pro" && (
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                )}
                {usage.plan === "enterprise" && (
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                )}
                {usage.plan}
              </span>
              {usage.plan === "free" && (
                <span className="text-xs text-gray-400">Upgrade to unlock all strategies</span>
              )}
            </div>

            {/* Simulations usage bar */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Simulations</span>
                <span className="font-medium text-gray-900">
                  {usage.simulations_used} / {usage.simulations_limit}
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all"
                  style={{
                    width: `${Math.min(100, (usage.simulations_used / usage.simulations_limit) * 100)}%`,
                  }}
                />
              </div>
            </div>

            {/* Buildings usage bar */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Buildings</span>
                <span className="font-medium text-gray-900">
                  {usage.buildings_count} / {usage.buildings_limit}
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className="h-full rounded-full bg-green-600 transition-all"
                  style={{
                    width: `${Math.min(100, (usage.buildings_count / usage.buildings_limit) * 100)}%`,
                  }}
                />
              </div>
            </div>

            <p className="text-xs text-gray-400">
              {usage.credits_remaining} simulation credits remaining this month
            </p>
            {usage.simulations_used / usage.simulations_limit >= 0.8 && (
              <p className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                You've used {Math.round((usage.simulations_used / usage.simulations_limit) * 100)}% of your monthly simulations
              </p>
            )}
          </div>
        ) : null}
      </section>

      {/* Plan Comparison */}
      {plans && plans.length > 0 && (
        <section className="rounded-xl bg-white shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Available Plans</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {plans.map((plan: PlanInfo) => {
              const isCurrent = plan.plan === usage?.plan;
              return (
                <div
                  key={plan.plan}
                  className={`rounded-lg border-2 p-4 ${
                    isCurrent ? "border-blue-500 bg-blue-50" : "border-gray-200"
                  }`}
                >
                  <h3 className="text-sm font-bold text-gray-900 capitalize">{plan.plan}</h3>
                  <p className="mt-1 text-2xl font-bold text-gray-900">
                    {plan.price_monthly_usd === 0
                      ? "Free"
                      : `$${plan.price_monthly_usd}`}
                    {plan.price_monthly_usd > 0 && (
                      <span className="text-sm font-normal text-gray-500">/mo</span>
                    )}
                  </p>
                  <ul className="mt-3 space-y-1 text-xs text-gray-600">
                    <li>{plan.max_buildings} buildings</li>
                    <li>{plan.max_simulations_monthly} simulations/month</li>
                    <li>
                      {plan.allowed_strategies.length} strategies
                      <span className="text-gray-400 ml-1">
                        ({plan.allowed_strategies.map((s) => STRATEGY_LABELS[s] ?? s).slice(-2).join(", ")}
                        {plan.allowed_strategies.length > 2 && "..."})
                      </span>
                    </li>
                    <li>{plan.has_pdf_export ? "PDF export" : "No PDF export"}</li>
                  </ul>
                  {isCurrent ? (
                    <p className="mt-3 text-center text-xs font-medium text-blue-600">Current Plan</p>
                  ) : (
                    <button
                      disabled
                      className="mt-3 w-full rounded bg-gray-100 px-3 py-1.5 text-xs text-gray-400 cursor-not-allowed"
                    >
                      Coming Soon
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
      {/* Data Management */}
      <section className="rounded-xl bg-white shadow-sm p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Data</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => {
              const data = {
                exportedAt: new Date().toISOString(),
                user: user ?? null,
                usage: usage ?? null,
                plans: plans ?? null,
              };
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `buildwise-account-${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
              localStorage.setItem("buildwise_last_export", new Date().toISOString());
            }}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Export Account Data
          </button>
          {(() => {
            const lastExport = localStorage.getItem("buildwise_last_export");
            return lastExport ? (
              <span className="text-xs text-gray-400 self-center">
                Last export: {new Date(lastExport).toLocaleDateString()}
              </span>
            ) : null;
          })()}
          <button
            onClick={() => setShowClearConfirm(true)}
            className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Clear Local Preferences
          </button>
          {showClearConfirm && (
            <ConfirmDialog
              title="Clear Local Preferences"
              message="This will reset your banner preference, remembered email, and other local settings. The page will reload."
              confirmLabel="Clear"
              destructive
              onConfirm={() => {
                localStorage.removeItem("buildwise_banner_dismissed");
                localStorage.removeItem("buildwise_last_email");
                window.location.reload();
              }}
              onCancel={() => setShowClearConfirm(false)}
            />
          )}
        </div>
      </section>

      {/* Security */}
      <section className="rounded-xl bg-white shadow-sm p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Security</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700">Password</p>
              <p className="text-xs text-gray-400">Change your account password</p>
            </div>
            <button
              disabled
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-400 cursor-not-allowed"
            >
              Coming Soon
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700">Two-Factor Authentication</p>
              <p className="text-xs text-gray-400">Add an extra layer of security</p>
            </div>
            <button
              disabled
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-400 cursor-not-allowed"
            >
              Coming Soon
            </button>
          </div>
        </div>
      </section>

      {/* Keyboard Shortcuts */}
      <details className="rounded-xl bg-white shadow-sm mt-6 group">
        <summary className="cursor-pointer p-6 text-lg font-semibold text-gray-800 list-none flex items-center justify-between">
          Keyboard Shortcuts
          <svg className="h-5 w-5 text-gray-400 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </summary>
        <div className="space-y-2 text-sm px-6 pb-6">
          {([
            ["Ctrl + S", "Save BPS changes (in Building Editor)"],
            ["\u2190 \u2192", "Navigate BPS sections (when tab focused)"],
            ["N", "New Project (on Dashboard)"],
            ["Enter", "Submit forms / confirm actions"],
            ["Escape", "Close dialogs / cancel editing"],
            ["Tab", "Navigate between interactive elements"],
          ] as [string, string][]).map(([key, desc]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-gray-600">{desc}</span>
              <kbd className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono text-gray-700 border border-gray-200">{key}</kbd>
            </div>
          ))}
        </div>
      </details>

      {/* Appearance */}
      <section className="rounded-xl bg-white shadow-sm p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Appearance</h2>
        <div className="flex gap-4">
          <div className="flex-1 rounded-lg border-2 border-blue-500 bg-white p-4 text-center cursor-default">
            <div className="mx-auto mb-2 h-8 w-12 rounded bg-gray-100 border border-gray-200" />
            <p className="text-xs font-medium text-gray-700">Light</p>
            <p className="text-[10px] text-blue-500">Active</p>
          </div>
          <div className="flex-1 rounded-lg border-2 border-gray-200 bg-gray-50 p-4 text-center cursor-not-allowed opacity-60">
            <div className="mx-auto mb-2 h-8 w-12 rounded bg-gray-700 border border-gray-600" />
            <p className="text-xs font-medium text-gray-500">Dark</p>
            <p className="text-[10px] text-gray-400">Coming soon</p>
          </div>
          <div className="flex-1 rounded-lg border-2 border-gray-200 bg-gray-50 p-4 text-center cursor-not-allowed opacity-60">
            <div className="mx-auto mb-2 h-8 w-12 rounded bg-gradient-to-r from-gray-100 to-gray-700 border border-gray-300" />
            <p className="text-xs font-medium text-gray-500">System</p>
            <p className="text-[10px] text-gray-400">Coming soon</p>
          </div>
        </div>
      </section>
    </div>
  );
}
