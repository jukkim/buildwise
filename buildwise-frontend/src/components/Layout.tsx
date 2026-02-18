import { Link, Outlet, useNavigate } from "react-router-dom";

export default function Layout() {
  const navigate = useNavigate();
  const userName = localStorage.getItem("buildwise_user_name") ?? "User";

  const handleLogout = () => {
    localStorage.removeItem("buildwise_user_id");
    localStorage.removeItem("buildwise_user_name");
    navigate("/login");
  };

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
              <Link
                to="/settings"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Settings
              </Link>
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
