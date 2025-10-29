import React from 'react';
import { AlertCircle } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error boundary caught error:', error, errorInfo);
    this.state = {
      hasError: true,
      error: error,
      errorInfo: errorInfo
    };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6 flex items-center justify-center">
          <div className="max-w-2xl w-full">
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-8">
              <div className="flex items-start gap-4">
                <div className="p-3 bg-red-500/20 rounded-lg">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                </div>
                <div className="flex-1">
                  <h1 className="text-2xl font-bold text-white mb-2">Something went wrong</h1>
                  <p className="text-red-300 mb-4">
                    The page encountered an error and couldn't render properly.
                  </p>

                  {this.state.error && (
                    <div className="bg-black/30 rounded p-4 mb-4">
                      <p className="text-red-400 text-sm font-mono">
                        {this.state.error.toString()}
                      </p>
                    </div>
                  )}

                  {this.state.errorInfo && (
                    <details className="mb-4">
                      <summary className="text-gray-400 text-sm cursor-pointer hover:text-white">
                        Show error details
                      </summary>
                      <div className="bg-black/30 rounded p-4 mt-2">
                        <pre className="text-red-400 text-xs font-mono overflow-auto">
                          {this.state.errorInfo.componentStack}
                        </pre>
                      </div>
                    </details>
                  )}

                  <div className="flex gap-3">
                    <button
                      onClick={() => window.location.reload()}
                      className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6 py-2 rounded-lg font-medium transition-all"
                    >
                      Reload Page
                    </button>
                    <button
                      onClick={() => window.location.href = '/dashboard'}
                      className="bg-gray-700 hover:bg-gray-600 text-white px-6 py-2 rounded-lg font-medium transition-all"
                    >
                      Go to Dashboard
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
