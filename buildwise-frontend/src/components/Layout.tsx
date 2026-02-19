import { useState, useEffect } from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import useScrollToTop from "@/hooks/useScrollToTop";

export default function Layout() {
  useScrollToTop();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const userName = localStorage.getItem("buildwise_user_name") ?? "User";
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 0);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("buildwise_user_id");
    localStorage.removeItem("buildwise_user_name");
    navigate("/login");
  };

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
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* Skip to content (keyboard accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:rounded focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      {/* Navbar */}
      <nav className={`sticky top-0 z-30 bg-white border-b border-gray-200 transition-shadow ${scrolled ? "shadow-sm" : ""}`}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link to="/projects" className="flex items-center gap-2">
              <span className="text-xl font-bold text-blue-600">BuildWise</span>
              <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600 uppercase tracking-wider">Beta</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden sm:flex items-center gap-4">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`flex items-center gap-1.5 text-sm py-1 border-b-2 ${pathname.startsWith(link.to) ? "font-semibold text-blue-600 border-blue-600" : "text-gray-600 hover:text-gray-900 border-transparent"}`}
                >
                  {link.icon}
                  {link.label}
                </Link>
              ))}
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span>{userName}</span>
                <button
                  onClick={handleLogout}
                  className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                >
                  Sign Out
                </button>
              </div>
            </div>

            {/* Mobile current page + hamburger */}
            <div className="flex sm:hidden items-center gap-2">
              <span className="text-sm font-medium text-gray-600">
                {navLinks.find((l) => pathname.startsWith(l.to))?.label ?? ""}
              </span>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="rounded p-2 text-gray-500 hover:bg-gray-100"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="sm:hidden border-t border-gray-200 bg-white px-4 py-3 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-2 rounded px-3 py-2 text-sm transition-colors ${pathname.startsWith(link.to) ? "bg-blue-50 font-semibold text-blue-600" : "text-gray-700 hover:bg-gray-100"}`}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
            <div className="flex items-center justify-between border-t border-gray-100 pt-2 mt-2">
              <span className="text-sm text-gray-500">{userName}</span>
              <button
                onClick={handleLogout}
                className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Content */}
      <main id="main-content" className="mx-auto max-w-7xl flex-1 px-4 py-6 sm:py-8 sm:px-6 lg:px-8 w-full">
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
