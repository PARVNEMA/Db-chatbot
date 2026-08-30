import React from "react";
import Link from "next/link";
import { Database, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound(): React.JSX.Element {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-zinc-100 p-6 text-center">
      <div className="relative mb-6">
        <div className="h-24 w-24 rounded-3xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shadow-2xl">
          <Database className="h-12 w-12" />
        </div>
        <div className="absolute -bottom-2 -right-2 px-2 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 text-xs font-mono font-bold text-zinc-400">
          404
        </div>
      </div>

      <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
        Page Not Found
      </h1>
      <p className="mt-3 text-sm text-zinc-400 max-w-md leading-relaxed">
        The database entity, workspace route, or query session you are looking for does not exist or has been moved.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link href="/projects">
          <Button className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs gap-1.5 shadow-lg shadow-blue-600/20">
            <Home className="h-3.5 w-3.5" />
            Go to Projects
          </Button>
        </Link>
        <Link href="/">
          <Button
            variant="outline"
            className="border-zinc-800 hover:bg-zinc-900 text-zinc-300 text-xs gap-1.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
