import { useState } from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import useScrollToTop from "@/hooks/useScrollToTop";

export default function Layout() {
  useScrollToTop();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const userName = localStorage.getItem("buildwise_user_name") ?? "User";
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem("buildwise_user_id");
    localStorage.removeItem("buildwise_user_name");
    navigate("/login");
  };

  const navLinks = [
    { to: "/projects", label: "Projects" },
    { to: "/settings", label: "Settings" },
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
      <nav className="bg-white border-b border-gray-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link to="/projects" className="flex items-center gap-2">
              <span className="text-xl font-bold text-blue-600">BuildWise</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden sm:flex items-center gap-4">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`text-sm ${pathname.startsWith(link.to) ? "font-semibold text-blue-600" : "text-gray-600 hover:text-gray-900"}`}
                >
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

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="sm:hidden rounded p-2 text-gray-500 hover:bg-gray-100"
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

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="sm:hidden border-t border-gray-200 bg-white px-4 py-3 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                className={`block rounded px-3 py-2 text-sm ${pathname.startsWith(link.to) ? "bg-blue-50 font-semibold text-blue-600" : "text-gray-700 hover:bg-gray-100"}`}
              >
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
          <span>BuildWise v0.1.0</span>
          <span>Building Energy Simulation Platform</span>
        </div>
      </footer>
    </div>
  );
}
