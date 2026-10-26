import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary — catches any uncaught render errors in child components and
 * displays a fallback UI instead of crashing the entire application.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // In production, send to error tracking service (e.g. Sentry)
    console.error('[ErrorBoundary] Uncaught error:', error, info.componentStack);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            background: '#0a0f1e',
            color: '#f1f5f9',
            fontFamily: 'Inter, sans-serif',
            padding: '2rem',
            textAlign: 'center',
            gap: '1rem',
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 24,
              marginBottom: 8,
            }}
          >
            ⚠️
          </div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
            Something went wrong
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#94a3b8', maxWidth: 400, margin: 0 }}>
            An unexpected error occurred in the dashboard. The error has been logged.
          </p>
          {import.meta.env.DEV && this.state.error && (
            <pre
              style={{
                marginTop: 8,
                padding: '0.75rem 1rem',
                background: '#1e293b',
                borderRadius: 8,
                fontSize: '0.75rem',
                color: '#f87171',
                textAlign: 'left',
                maxWidth: 600,
                overflowX: 'auto',
                border: '1px solid rgba(239,68,68,0.2)',
              }}
            >
              {this.state.error.toString()}
            </pre>
          )}
          <button
            onClick={this.handleReset}
            style={{
              marginTop: 8,
              padding: '0.5rem 1.5rem',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: '0.875rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
