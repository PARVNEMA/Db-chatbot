"use client";

import React, { Component, type ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
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
        <div className="flex flex-col items-center justify-center p-8 rounded-2xl border border-red-500/20 bg-red-500/5 text-center space-y-3 my-4">
          <div className="h-10 w-10 rounded-xl bg-red-500/10 text-red-400 flex items-center justify-center">
            <AlertCircle className="h-5 w-5" />
          </div>
          <h3 className="text-sm font-semibold text-white">
            Something went wrong rendering this component
          </h3>
          <p className="text-xs text-zinc-400 max-w-md font-mono">
            {this.state.error?.message || "An unexpected rendering error occurred."}
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={this.handleReset}
            className="border-zinc-700 text-xs gap-1.5"
          >
            <RefreshCw className="h-3 w-3" />
            Try Again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
