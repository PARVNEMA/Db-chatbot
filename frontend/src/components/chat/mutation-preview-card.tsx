"use client";

import React, { useState, useEffect } from "react";
import {
  Clock,
  Table as TableIcon,
  Eye,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Sparkles,
  Layers,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { MutationPreviewData } from "@/types/chat";

interface MutationPreviewCardProps {
  preview: MutationPreviewData;
  status?: string;
  expiresAt?: string;
  isDryRun?: boolean;
}

export function MutationPreviewCard({
  preview,
  status = "PENDING_APPROVAL",
  expiresAt,
  isDryRun = false,
}: MutationPreviewCardProps): React.JSX.Element {
  const effectiveExpiresAt = expiresAt || preview.expires_at;
  const effectiveDryRun = isDryRun || preview.dry_run || status === "DRY_RUN";

  // Countdown timer state
  const [timeLeftSec, setTimeLeftSec] = useState<number | null>(null);
  const [isExpired, setIsExpired] = useState<boolean>(false);
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!effectiveExpiresAt || status === "EXECUTED" || status === "FAILED" || effectiveDryRun) {
      return;
    }

    const calcTimeLeft = () => {
      const target = new Date(effectiveExpiresAt).getTime();
      const now = Date.now();
      const diffSec = Math.max(0, Math.floor((target - now) / 1000));
      setTimeLeftSec(diffSec);
      if (diffSec <= 0) {
        setIsExpired(true);
      }
    };

    calcTimeLeft();
    const interval = setInterval(calcTimeLeft, 1000);
    return () => clearInterval(interval);
  }, [effectiveExpiresAt, status, effectiveDryRun]);

  const toggleTableExpand = (tableName: string) => {
    setExpandedTables((prev) => ({
      ...prev,
      [tableName]: !prev[tableName],
    }));
  };

  const formatCountdown = (totalSeconds: number): string => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const mutations = preview.change_set?.mutations || [];
  const previewRowCounts = preview.preview_row_counts || {};
  const totalRows =
    preview.total_rows_affected ??
    Object.values(previewRowCounts).reduce((a, b) => a + b, 0);

  const getStatusBadge = () => {
    if (effectiveDryRun) {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
          <Sparkles className="h-3 w-3" /> Dry-Run Validated
        </span>
      );
    }
    if (status === "EXECUTED") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
          <CheckCircle2 className="h-3 w-3" /> Executed
        </span>
      );
    }
    if (status === "EXECUTING") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 animate-pulse">
          Executing Transaction...
        </span>
      );
    }
    if (status === "APPROVED") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
          <CheckCircle2 className="h-3 w-3" /> Approved
        </span>
      );
    }
    if (status === "UNDONE") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
          <RotateCcw className="h-3 w-3" /> Undone / Reverted
        </span>
      );
    }
    if (status === "FAILED" || status === "REJECTED") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30">
          <XCircle className="h-3 w-3" /> {status}
        </span>
      );
    }
    if (isExpired || status === "EXPIRED") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30">
          <Clock className="h-3 w-3" /> Expired
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
        <Clock className="h-3 w-3" /> Pending Approval
      </span>
    );
  };

  return (
    <div className="my-3 rounded-2xl border border-zinc-800 bg-zinc-900/90 shadow-xl overflow-hidden font-sans">
      {/* Header Bar */}
      <div className="p-3.5 bg-zinc-950/70 border-b border-zinc-800/80 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Layers className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              Proposed Change-Set Preview
              {getStatusBadge()}
            </h4>
            {preview.change_set?.summary && (
              <p className="text-[11px] text-zinc-400 mt-0.5">
                {preview.change_set.summary}
              </p>
            )}
          </div>
        </div>

        {/* Expiration Timer & Row Count */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-2 py-0.5 rounded-md bg-zinc-800/90 border border-zinc-700 text-zinc-300 text-[11px]">
            {totalRows} {totalRows === 1 ? "row" : "rows"} affected
          </span>

          {timeLeftSec !== null && !effectiveDryRun && status === "PENDING_APPROVAL" && (
            <span
              className={`flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] ${
                timeLeftSec <= 60
                  ? "bg-red-500/20 text-red-300 border-red-500/40 animate-pulse"
                  : "bg-zinc-800/90 text-amber-300 border-amber-500/30"
              }`}
              title="Time left before approval token expires"
            >
              <Clock className="h-3 w-3" />
              {isExpired ? "Expired" : formatCountdown(timeLeftSec)}
            </span>
          )}
        </div>
      </div>

      {/* Multi-Table Proposals Breakdown */}
      <div className="p-3.5 space-y-3">
        {mutations.map((m, idx) => {
          const tableName = m.table;
          const op = (m.operation || "insert").toUpperCase();
          const rowCount = previewRowCounts[tableName] ?? (m.rows?.length || 1);
          const isExpanded = expandedTables[tableName] ?? (idx === 0);
          const candidates = preview.candidate_rows?.[tableName] || [];

          return (
            <div
              key={`${tableName}-${idx}`}
              className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 overflow-hidden"
            >
              {/* Table Header Row */}
              <button
                type="button"
                onClick={() => toggleTableExpand(tableName)}
                className="w-full p-2.5 flex items-center justify-between bg-zinc-900/50 hover:bg-zinc-900 transition text-left"
              >
                <div className="flex items-center gap-2">
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />
                  )}
                  <TableIcon className="h-3.5 w-3.5 text-blue-400" />
                  <span className="text-xs font-mono font-semibold text-zinc-200">
                    {tableName}
                  </span>
                  <span
                    className={`text-[10px] font-mono font-medium px-1.5 py-0.2 rounded border ${
                      op === "INSERT"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    }`}
                  >
                    {op}
                  </span>
                </div>

                <span className="text-[11px] font-mono text-zinc-400">
                  {rowCount} {rowCount === 1 ? "row" : "rows"}
                </span>
              </button>

              {/* Table Body Diff / Details */}
              {isExpanded && (
                <div className="p-3 border-t border-zinc-800/60 space-y-3 text-xs">
                  {/* INSERT Operation: Proposed Rows */}
                  {op === "INSERT" && m.rows && m.rows.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                        Values to Insert ({m.rows.length}):
                      </span>
                      <div className="overflow-x-auto rounded-lg border border-zinc-800/80 bg-zinc-900/70 p-2 font-mono text-[11px] text-emerald-300/90 max-h-48 no-scrollbar">
                        <pre>{JSON.stringify(m.rows, null, 2)}</pre>
                      </div>
                    </div>
                  )}

                  {/* PATCH Operation: Filter and Values */}
                  {op === "PATCH" && (
                    <div className="space-y-2.5">
                      {m.filter && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                            Target Filter (WHERE):
                          </span>
                          <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/70 p-2 font-mono text-[11px] text-amber-300/90">
                            <pre>{JSON.stringify(m.filter, null, 2)}</pre>
                          </div>
                        </div>
                      )}

                      {m.values && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                            Proposed Updates (SET):
                          </span>
                          <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/70 p-2 font-mono text-[11px] text-blue-300/90">
                            <pre>{JSON.stringify(m.values, null, 2)}</pre>
                          </div>
                        </div>
                      )}

                      {/* Candidate Row Preview */}
                      {candidates.length > 0 && (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                            <Eye className="h-3 w-3 text-blue-400" />
                            <span>Matched Existing Rows ({candidates.length}):</span>
                          </div>
                          <div className="overflow-x-auto rounded-lg border border-zinc-800/80 bg-zinc-900/70 p-2 font-mono text-[11px] text-zinc-300 max-h-40 no-scrollbar">
                            <pre>{JSON.stringify(candidates, null, 2)}</pre>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Info Notice */}
      <div className="px-3.5 py-2.5 bg-zinc-950/80 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
          <span>
            {effectiveDryRun
              ? "Dry-Run: No database state was modified or staged."
              : "Single atomic transaction with row locking and append-only audit snapshot."}
          </span>
        </div>
        {preview.mutation_id && (
          <span className="font-mono text-[10px] text-zinc-500">
            ID: {preview.mutation_id.substring(0, 8)}...
          </span>
        )}
      </div>
    </div>
  );
}
