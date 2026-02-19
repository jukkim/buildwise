import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  showDetails: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
          <svg className="h-16 w-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <h1 className="text-2xl font-bold text-gray-900">Something went wrong</h1>
          <p className="mt-2 text-sm text-gray-500 max-w-md">
            {this.state.error?.message ?? "An unexpected error occurred."}
          </p>
          <div className="mt-6 flex gap-3">
            <button
              onClick={() => this.setState({ hasError: false, error: null, showDetails: false })}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Reload Page
            </button>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, showDetails: false });
                window.location.href = "/projects";
              }}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Go to Projects
            </button>
          </div>
          {this.state.error?.stack && (
            <div className="mt-4">
              <button
                onClick={() => this.setState((s) => ({ showDetails: !s.showDetails }))}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {this.state.showDetails ? "Hide details" : "Show details"}
              </button>
              {this.state.showDetails && (
                <pre className="mt-2 max-w-2xl max-h-48 overflow-auto rounded bg-gray-100 p-3 text-left text-xs text-gray-600 font-mono">
                  {this.state.error.stack}
                </pre>
              )}
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
