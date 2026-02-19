import { useQuery } from "@tanstack/react-query";
import { authApi, billingApi, type PlanInfo } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import { STRATEGY_LABELS } from "@/constants/strategies";

export default function Settings() {
  useDocumentTitle("Settings");

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
      <section className="rounded-lg border border-gray-200 bg-white p-6 mb-6">
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
              {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "-"}
            </dd>
          </div>
        </dl>
      </section>

      {/* Current Plan & Usage */}
      <section className="rounded-lg border border-gray-200 bg-white p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Plan & Usage</h2>
        {usageLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : usage ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-800 capitalize">
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
          </div>
        ) : null}
      </section>

      {/* Plan Comparison */}
      {plans && plans.length > 0 && (
        <section className="rounded-lg border border-gray-200 bg-white p-6">
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
      <section className="rounded-lg border border-gray-200 bg-white p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Data</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => {
              const data = {
                exportedAt: new Date().toISOString(),
                user: user ?? null,
                usage: usage ?? null,
              };
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `buildwise-account-${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Export Account Data
          </button>
          <button
            onClick={() => {
              localStorage.removeItem("buildwise_banner_dismissed");
              localStorage.removeItem("buildwise_last_email");
              window.location.reload();
            }}
            className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Clear Local Preferences
          </button>
        </div>
      </section>

      {/* Keyboard Shortcuts */}
      <section className="rounded-lg border border-gray-200 bg-white p-6 mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Keyboard Shortcuts</h2>
        <div className="space-y-2 text-sm">
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
      </section>

      {/* Appearance */}
      <section className="rounded-lg border border-gray-200 bg-white p-6 mt-6">
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
