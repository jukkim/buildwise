import { Link, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link to="/projects" className="flex items-center gap-2">
              <span className="text-xl font-bold text-blue-600">BuildWise</span>
            </Link>
            <div className="flex items-center gap-4">
              <Link
                to="/projects"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Projects
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
