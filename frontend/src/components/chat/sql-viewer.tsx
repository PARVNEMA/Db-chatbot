"use client";

import React, { useState } from "react";
import { Code2, Copy, Check, ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SqlViewerProps {
  sql: string;
  dialect?: string;
  defaultExpanded?: boolean;
}

export function SqlViewer({
  sql,
  dialect = "sql",
  defaultExpanded = true,
}: SqlViewerProps): React.JSX.Element {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = sql.trim().split("\n");

  return (
    <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/80 overflow-hidden shadow-md my-2">
      {/* Header Bar */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="px-3.5 py-2 bg-zinc-900/80 border-b border-zinc-800/80 flex items-center justify-between cursor-pointer hover:bg-zinc-900 transition select-none"
      >
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-300">
          <span className="text-zinc-500">
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5 text-blue-400" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
            )}
          </span>
          <Code2 className="h-3.5 w-3.5 text-blue-400" />
          <span>Generated SQL Query</span>
          <Badge
            variant="accent"
            className="uppercase text-[9px] py-0 px-1 font-mono text-blue-300 bg-blue-500/10 border-blue-500/20"
          >
            {dialect}
          </Badge>
        </div>

        <Button
          size="icon-xs"
          variant="ghost"
          onClick={handleCopy}
          className="text-zinc-400 hover:text-white h-6 w-6"
          title="Copy SQL Query"
        >
          {copied ? (
            <Check className="h-3 w-3 text-emerald-400" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </Button>
      </div>

      {/* Code Block */}
      {expanded && (
        <div className="p-3 bg-black/50 font-mono text-xs overflow-x-auto">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, idx) => (
                <tr key={idx} className="hover:bg-zinc-900/40">
                  <td className="pr-4 text-zinc-600 select-none text-[11px] text-right w-8">
                    {idx + 1}
                  </td>
                  <td className="text-emerald-400 font-mono whitespace-pre leading-relaxed">
                    {line}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
