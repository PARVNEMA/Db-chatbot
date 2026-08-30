import React from "react";
import { Loader2 } from "lucide-react";

export default function RootLoading(): React.JSX.Element {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-zinc-400">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="text-xs font-mono text-zinc-500">Loading AskMyDB...</p>
      </div>
    </div>
  );
}
