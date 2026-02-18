import { Link, useNavigate } from "react-router-dom";
import useDocumentTitle from "@/hooks/useDocumentTitle";

export default function NotFound() {
  useDocumentTitle("Not Found");
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <h1 className="text-6xl font-bold text-gray-300">404</h1>
      <p className="mt-4 text-lg text-gray-600">Page not found</p>
      <p className="mt-2 text-sm text-gray-400">The page you're looking for doesn't exist or has been moved.</p>
      <div className="mt-6 flex gap-3">
        <button
          onClick={() => navigate(-1)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Go Back
        </button>
        <Link
          to="/projects"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Go to Projects
        </Link>
      </div>
    </div>
  );
}
