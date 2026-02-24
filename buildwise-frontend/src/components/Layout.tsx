import { useState, useEffect, useRef } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import useScrollToTop from "@/hooks/useScrollToTop";
import useAuth from "@/auth/useAuth";

export default function Layout() {
  useScrollToTop();
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  // Move focus to main content after route change for screen readers
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
  }, [pathname]);
  const { user, logout } = useAuth();
  const userName = user?.name || localStorage.getItem("buildwise_user_name") || "User";
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 0);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const handleLogout = () => logout();

  const navLinks = [
    {
      to: "/projects",
      label: "Projects",
      icon: (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
    },
    {
      to: "/settings",
      label: "Settings",
      icon: (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="flex min-h-screen flex-col">
      {/* Skip to content (keyboard accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:rounded focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      {/* Navbar — dark branded header */}
      <nav className={`sticky top-0 z-30 bg-gradient-to-r from-gray-900 to-slate-800 transition-shadow ${scrolled ? "shadow-lg shadow-black/10" : ""}`}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <Link to="/projects" className="flex items-center gap-2.5">
              {/* Logo mark */}
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500">
                <svg className="h-4.5 w-4.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="text-lg font-bold text-white tracking-tight">BuildWise</span>
              <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-medium text-blue-300 uppercase tracking-wider">Beta</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden sm:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    pathname.startsWith(link.to)
                      ? "bg-white/10 font-medium text-white"
                      : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                  }`}
                >
                  {link.icon}
                  {link.label}
                </Link>
              ))}
              <div className="ml-4 flex items-center gap-3 border-l border-white/10 pl-4">
                <span className="text-sm text-gray-400">{userName}</span>
                <button
                  onClick={handleLogout}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:bg-white/10 hover:text-white"
                >
                  Sign Out
                </button>
              </div>
            </div>

            {/* Mobile current page + hamburger */}
            <div className="flex sm:hidden items-center gap-2">
              <span className="text-sm font-medium text-gray-300">
                {navLinks.find((l) => pathname.startsWith(l.to))?.label ?? ""}
              </span>
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                className="rounded-lg p-2 text-gray-400 hover:bg-white/10 hover:text-white"
                aria-label={mobileOpen ? "Close menu" : "Open menu"}
                aria-expanded={mobileOpen}
              >
                {mobileOpen ? (
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="sm:hidden border-t border-white/10 bg-gray-900/95 backdrop-blur px-4 py-3 space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  pathname.startsWith(link.to)
                    ? "bg-white/10 font-medium text-white"
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
            <div className="flex items-center justify-between border-t border-white/10 pt-3 mt-2">
              <span className="text-sm text-gray-400">{userName}</span>
              <button
                onClick={handleLogout}
                className="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-white/10 hover:text-white"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Content */}
      <main ref={mainRef} id="main-content" tabIndex={-1} className="mx-auto max-w-7xl flex-1 px-4 py-6 sm:py-8 sm:px-6 lg:px-8 w-full animate-fade-in outline-none">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white py-4 mt-auto print:hidden">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center justify-between text-xs text-gray-400">
          <span>&copy; {new Date().getFullYear()} BuildWise v0.1.0</span>
          <div className="flex items-center gap-4">
            <span className="hidden sm:inline" title="Powered by EnergyPlus simulation engine">EnergyPlus 24.1</span>
            <span>Building Energy Simulation Platform</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
