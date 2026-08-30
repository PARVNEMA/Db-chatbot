"use client";

import React, { useEffect } from "react";
import { AlertCircle, RefreshCw, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): React.JSX.Element {
  useEffect(() => {
    console.error("Dashboard error caught:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center space-y-4 rounded-2xl border border-zinc-800/80 bg-zinc-900/40 my-8">
      <div className="h-12 w-12 rounded-2xl bg-red-500/10 text-red-400 flex items-center justify-center border border-red-500/20">
        <AlertCircle className="h-6 w-6" />
      </div>

      <div className="space-y-1">
        <h2 className="text-lg font-bold text-white">
          Failed to load workspace data
        </h2>
        <p className="text-xs text-zinc-400 max-w-md font-mono">
          {error.message || "An unexpected error occurred while loading this dashboard view."}
        </p>
      </div>

      <div className="flex items-center gap-2 pt-2">
        <Button
          size="sm"
          onClick={() => reset()}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs gap-1.5"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </Button>
        <Link href="/projects">
          <Button
            size="sm"
            variant="outline"
            className="border-zinc-800 hover:bg-zinc-800 text-zinc-300 text-xs gap-1.5"
          >
            <Layers className="h-3.5 w-3.5" />
            All Projects
          </Button>
        </Link>
      </div>
    </div>
  );
}
