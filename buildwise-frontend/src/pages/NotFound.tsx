import { Link, useNavigate } from "react-router-dom";
import useDocumentTitle from "@/hooks/useDocumentTitle";

export default function NotFound() {
  useDocumentTitle("Not Found");
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <svg className="h-20 w-20 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
      <h1 className="mt-4 text-6xl font-bold text-gray-300">404</h1>
      <p className="mt-4 text-lg font-medium text-gray-600">Page not found</p>
      <p className="mt-2 text-sm text-gray-400 max-w-sm">
        The page you're looking for doesn't exist, has been moved, or the simulation may have expired.
      </p>
      <div className="mt-6 flex gap-3">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
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
