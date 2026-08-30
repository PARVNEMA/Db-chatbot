"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): React.JSX.Element {
  useEffect(() => {
    console.error("Global application error caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-zinc-100 p-6 text-center">
      <div className="h-20 w-20 rounded-3xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 mb-6 shadow-2xl">
        <AlertTriangle className="h-10 w-10" />
      </div>

      <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
        Application Error
      </h1>
      <p className="mt-2 text-xs sm:text-sm text-zinc-400 max-w-md font-mono">
        {error.message || "An unexpected system error occurred."}
      </p>

      {error.digest && (
        <div className="mt-2 px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[10px] font-mono text-zinc-500">
          Digest: {error.digest}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Button
          onClick={() => reset()}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs gap-1.5 shadow-lg shadow-blue-600/20"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Try Again
        </Button>
        <Link href="/projects">
          <Button
            variant="outline"
            className="border-zinc-800 hover:bg-zinc-900 text-zinc-300 text-xs gap-1.5"
          >
            <Home className="h-3.5 w-3.5" />
            Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
