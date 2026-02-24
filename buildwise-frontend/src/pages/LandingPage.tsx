import { useState } from "react";
import { Link } from "react-router-dom";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import useInView from "@/hooks/useInView";

/* ─── Reusable section wrapper with scroll animation ─── */
function Section({
  children,
  className = "",
  id,
}: {
  children: React.ReactNode;
  className?: string;
  id?: string;
}) {
  const { ref, inView } = useInView(0.1);
  return (
    <section
      ref={ref}
      id={id}
      className={`transition-all duration-700 ${inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"} ${className}`}
    >
      {children}
    </section>
  );
}

/* ─── Logo component (shared with Login) ─── */
function Logo({ size = "lg" }: { size?: "sm" | "lg" }) {
  const s = size === "lg" ? "h-12 w-12" : "h-9 w-9";
  const icon = size === "lg" ? "h-6 w-6" : "h-5 w-5";
  return (
    <div
      className={`flex ${s} items-center justify-center rounded-2xl bg-blue-500 shadow-lg shadow-blue-500/25`}
    >
      <svg className={`${icon} text-white`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    </div>
  );
}

/* ─── Screenshot tabs ─── */
const SCREENSHOTS = [
  { key: "dashboard", label: "Dashboard", src: "/screenshots/dashboard.png" },
  { key: "editor", label: "Building Editor", src: "/screenshots/building-editor.png" },
  { key: "results", label: "Results", src: "/screenshots/results.png" },
] as const;

/* ─── How-it-works steps ─── */
const STEPS = [
  { icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4", title: "Select Building", desc: "Choose from 6 DOE reference types" },
  { icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z", title: "Configure", desc: "HVAC, schedule, climate zone" },
  { icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z", title: "Simulate", desc: "EnergyPlus baseline run" },
  { icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z", title: "Compare", desc: "9 EMS strategies (M0-M8)" },
  { icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z", title: "Analyze", desc: "Charts, PDF report, AI insights" },
];

/* ─── Feature cards ─── */
const FEATURES = [
  { icon: "M13 10V3L4 14h7v7l9-11h-7z", title: "Mock Simulation", desc: "Instant results from calibrated EUI lookup tables — 398 validated data points." },
  { icon: "M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5", title: "3D Preview", desc: "Interactive building visualization powered by Three.js and React Three Fiber." },
  { icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z", title: "Strategy Comparison", desc: "Side-by-side analysis of 9 EMS strategies with savings breakdown." },
  { icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z", title: "Multi-City Analysis", desc: "Compare across 10 Korean cities with real climate data (EPW)." },
];

/* ─── Pricing tiers ─── */
const PRICING = [
  { name: "Free", price: "$0", period: "/month", features: ["1 project", "3 buildings", "Mock simulation", "Basic charts"], cta: "Get Started", highlight: false },
  { name: "Pro", price: "$29", period: "/month", features: ["Unlimited projects", "EnergyPlus engine", "PDF reports", "Priority support"], cta: "Coming Soon", highlight: true },
  { name: "Enterprise", price: "Custom", period: "", features: ["Self-hosted option", "API access", "Custom strategies", "Dedicated support"], cta: "Contact Us", highlight: false },
];

/* ─── Stat items ─── */
const STATS = [
  { value: "6", label: "Building Types" },
  { value: "10", label: "Cities" },
  { value: "9", label: "EMS Strategies" },
  { value: "398", label: "Validated Data Points" },
];

export default function LandingPage() {
  useDocumentTitle("BuildWise — Building Energy Simulation Platform");
  const [activeTab, setActiveTab] = useState(0);
  const [waitlistEmail, setWaitlistEmail] = useState("");
  const [waitlistDone, setWaitlistDone] = useState(false);

  const handleWaitlist = (e: React.FormEvent) => {
    e.preventDefault();
    if (!waitlistEmail.trim()) return;
    const existing = JSON.parse(localStorage.getItem("buildwise_waitlist") || "[]") as string[];
    if (!existing.includes(waitlistEmail.trim())) {
      existing.push(waitlistEmail.trim());
      localStorage.setItem("buildwise_waitlist", JSON.stringify(existing));
    }
    setWaitlistDone(true);
    setWaitlistEmail("");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white">
      {/* ─── Navbar ─── */}
      <nav className="fixed top-0 z-50 w-full border-b border-white/5 bg-slate-900/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="text-lg font-bold">BuildWise</span>
          </div>
          <div className="hidden items-center gap-8 text-sm text-gray-400 md:flex">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#screenshots" className="hover:text-white transition-colors">Screenshots</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          </div>
          <Link
            to="/login"
            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold shadow-lg shadow-blue-500/25 hover:bg-blue-400 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <header className="relative flex min-h-screen flex-col items-center justify-center px-6 pt-16 text-center">
        {/* Glow orbs */}
        <div className="pointer-events-none absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-1/4 right-1/4 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl" />
        {/* Grid pattern */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }} />

        <div className="relative z-10 max-w-3xl">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-500 shadow-xl shadow-blue-500/30">
            <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>

          <h1 className="text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            Smarter Buildings,{" "}
            <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              Lower Energy
            </span>
          </h1>

          <p className="mt-6 text-lg leading-relaxed text-blue-100/70 sm:text-xl">
            Simulate building energy performance with EnergyPlus.
            <br className="hidden sm:block" />
            Compare 9 EMS strategies. Make data-driven decisions.
          </p>

          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              to="/login"
              className="rounded-xl bg-blue-500 px-8 py-3.5 text-base font-semibold shadow-xl shadow-blue-500/25 hover:bg-blue-400 hover:shadow-blue-400/30 transition-all"
            >
              Get Started Free
            </Link>
            <a
              href="#how-it-works"
              className="rounded-xl border border-white/10 bg-white/5 px-8 py-3.5 text-base font-semibold backdrop-blur hover:bg-white/10 transition-all"
            >
              See How It Works
            </a>
          </div>
        </div>

        {/* Hero screenshot */}
        <div className="relative z-10 mt-16 w-full max-w-4xl px-4">
          <div className="overflow-hidden rounded-xl border border-white/10 shadow-2xl shadow-blue-500/10">
            <img
              src="/screenshots/dashboard.png"
              alt="BuildWise Dashboard"
              className="w-full"
              loading="eager"
            />
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce text-gray-500">
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </header>

      {/* ─── Stats ─── */}
      <Section className="py-20 px-6">
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 sm:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-4xl font-extrabold text-blue-400">{s.value}</div>
              <div className="mt-2 text-sm text-gray-400">{s.label}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* ─── How It Works ─── */}
      <Section id="how-it-works" className="py-20 px-6">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-4 text-center text-3xl font-bold">How It Works</h2>
          <p className="mb-16 text-center text-gray-400">Five simple steps from building selection to energy insights</p>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-5">
            {STEPS.map((step, i) => (
              <div key={step.title} className="group relative flex flex-col items-center text-center">
                {/* Connector line (hidden on first item & mobile) */}
                {i > 0 && (
                  <div className="pointer-events-none absolute left-0 top-8 hidden h-px w-full -translate-x-1/2 bg-gradient-to-r from-blue-500/30 to-transparent sm:block" />
                )}
                <div className="relative z-10 mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5 backdrop-blur transition-colors group-hover:border-blue-500/30 group-hover:bg-blue-500/10">
                  <svg className="h-7 w-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={step.icon} />
                  </svg>
                </div>
                <div className="mb-1 text-xs font-semibold text-blue-400/70">Step {i + 1}</div>
                <h3 className="text-sm font-semibold">{step.title}</h3>
                <p className="mt-1 text-xs text-gray-500">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ─── Screenshots ─── */}
      <Section id="screenshots" className="py-20 px-6">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-4 text-center text-3xl font-bold">See It in Action</h2>
          <p className="mb-12 text-center text-gray-400">Real screenshots from the BuildWise platform</p>

          {/* Tabs */}
          <div className="mb-8 flex justify-center gap-2">
            {SCREENSHOTS.map((s, i) => (
              <button
                key={s.key}
                onClick={() => setActiveTab(i)}
                className={`rounded-lg px-5 py-2 text-sm font-medium transition-all ${
                  activeTab === i
                    ? "bg-blue-500 text-white shadow-lg shadow-blue-500/25"
                    : "bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Image */}
          <div className="overflow-hidden rounded-xl border border-white/10 shadow-2xl">
            <img
              src={SCREENSHOTS[activeTab].src}
              alt={SCREENSHOTS[activeTab].label}
              className="w-full transition-opacity duration-300"
            />
          </div>
        </div>
      </Section>

      {/* ─── Features ─── */}
      <Section id="features" className="py-20 px-6">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-4 text-center text-3xl font-bold">Features</h2>
          <p className="mb-12 text-center text-gray-400">Everything you need for building energy analysis</p>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur transition-all hover:border-blue-500/20 hover:bg-white/[0.06]"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10">
                  <svg className="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={f.icon} />
                  </svg>
                </div>
                <h3 className="mb-2 text-lg font-semibold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-gray-400">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ─── Pricing ─── */}
      <Section id="pricing" className="py-20 px-6">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-4 text-center text-3xl font-bold">Pricing</h2>
          <p className="mb-12 text-center text-gray-400">
            Currently in <span className="text-blue-400 font-semibold">Beta</span> — all features free
          </p>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            {PRICING.map((tier) => (
              <div
                key={tier.name}
                className={`relative rounded-2xl border p-8 transition-all ${
                  tier.highlight
                    ? "border-blue-500/40 bg-blue-500/5 shadow-xl shadow-blue-500/10"
                    : "border-white/10 bg-white/[0.03]"
                }`}
              >
                {tier.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-4 py-1 text-xs font-semibold">
                    Popular
                  </div>
                )}
                <h3 className="text-xl font-bold">{tier.name}</h3>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-4xl font-extrabold">{tier.price}</span>
                  <span className="text-sm text-gray-400">{tier.period}</span>
                </div>
                <ul className="mt-8 space-y-3">
                  {tier.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-3 text-sm text-gray-300">
                      <svg className="h-4 w-4 shrink-0 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/login"
                  className={`mt-8 block w-full rounded-xl py-3 text-center text-sm font-semibold transition-all ${
                    tier.highlight
                      ? "bg-blue-500 text-white shadow-lg shadow-blue-500/25 hover:bg-blue-400"
                      : "border border-white/10 bg-white/5 hover:bg-white/10"
                  }`}
                >
                  {tier.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ─── Waitlist CTA ─── */}
      <Section className="py-20 px-6">
        <div className="mx-auto max-w-xl text-center">
          <h2 className="mb-4 text-3xl font-bold">Join the Waitlist</h2>
          <p className="mb-8 text-gray-400">
            Be the first to know when we launch EnergyPlus live simulation.
          </p>

          {waitlistDone ? (
            <div className="rounded-xl border border-green-500/30 bg-green-500/10 px-6 py-4">
              <p className="font-semibold text-green-300">You're on the list! We'll be in touch.</p>
            </div>
          ) : (
            <form onSubmit={handleWaitlist} className="flex flex-col gap-3 sm:flex-row">
              <input
                type="email"
                required
                value={waitlistEmail}
                onChange={(e) => setWaitlistEmail(e.target.value)}
                placeholder="you@company.com"
                className="flex-1 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm text-white placeholder-gray-500 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/50"
              />
              <button
                type="submit"
                className="rounded-xl bg-blue-500 px-8 py-3 text-sm font-semibold shadow-lg shadow-blue-500/25 hover:bg-blue-400 transition-colors"
              >
                Join Waitlist
              </button>
            </form>
          )}
        </div>
      </Section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/5 py-8 text-center text-sm text-gray-500">
        &copy; 2026 BuildWise &middot; Building Energy Simulation Platform
      </footer>
    </div>
  );
}
