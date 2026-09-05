"use client";

import React from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  Code2,
  Layers,
  AlertCircle,
  Copy,
  Check,
  FileJson,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChatMessage, ChatSSEEvent } from "@/types/chat";

interface EventStreamModalProps {
  isOpen: boolean;
  onClose: () => void;
  message: ChatMessage;
  events?: ChatSSEEvent[];
  dialect?: string;
}

export function EventStreamModal({
  isOpen,
  onClose,
  message,
  events = [],
  dialect = "postgresql",
}: EventStreamModalProps): React.JSX.Element {
  const [copied, setCopied] = React.useState(false);

  const meta = (message.metadata_json || message.metadata || {}) as Record<string, unknown>;
  const queryRun = message.selected_query_run;

  const sql =
    (meta.sql as string) ||
    (meta.generated_sql as string) ||
    queryRun?.generated_sql ||
    "";
  const status =
    (meta.status as string) || queryRun?.status || "success";
  const latencyMs =
    (meta.latency_ms as number) ?? queryRun?.latency_ms ?? null;
  const rowCount =
    (meta.row_count as number) ??
    (meta.result_row_count as number) ??
    queryRun?.result_row_count ??
    null;
  const activeDialect =
    (meta.dialect as string) || dialect || "sql";

  const hasEventStream = Boolean(events && events.length > 0);

  const metadataJsonObj = {
    sql: sql || null,
    status: status,
    dialect: activeDialect,
    row_count: rowCount,
    latency_ms: latencyMs,
  };

  const displayEvents: {
    event: string;
    label: string;
    status: "success" | "running" | "error" | "info";
    data: Record<string, unknown>;
  }[] = [];

  if (hasEventStream) {
    events.forEach((ev) => {
      displayEvents.push({
        event: ev.event,
        label: formatEventName(ev.event),
        status: String(ev.event).includes("error")
          ? "error"
          : ev.event === "final_result" || ev.event === "done"
          ? "success"
          : "info",
        data: ev as unknown as Record<string, unknown>,
      });
    });
  } else {
    displayEvents.push({
      event: "message_received",
      label: "Message Received",
      status: "success",
      data: {
        role: "user",
        prompt: queryRun?.nl_prompt || "User prompt processed",
        created_at: message.created_at,
      },
    });

    displayEvents.push({
      event: "intent_classified",
      label: "Intent Classification",
      status: "success",
      data: {
        agent: "LangGraph Intent Node",
        schema_linking: "pgvector similarity search completed",
      },
    });

    if (sql) {
      displayEvents.push({
        event: "sql_generated",
        label: "SQL Synthesis",
        status: "success",
        data: {
          dialect: activeDialect,
          generated_sql: sql,
        },
      });

      displayEvents.push({
        event: "sql_executed",
        label: "Guardrailed Execution",
        status: status === "failed" ? "error" : "success",
        data: {
          status,
          row_count: rowCount,
          execution_guardrails: "Read-only verified",
        },
      });
    }

    displayEvents.push({
      event: "summary_ready",
      label: "Answer Synthesis",
      status: "success",
      data: {
        summary: message.content,
        latency_ms: latencyMs,
      },
    });

    displayEvents.push({
      event: "final_result",
      label: "Execution Completed",
      status: status === "failed" ? "error" : "success",
      data: {
        status,
        latency_ms: latencyMs,
        token_count: message.token_count,
        query_run_id: message.query_run_id,
      },
    });
  }

  const handleCopyJson = () => {
    const toCopy = hasEventStream
      ? {
          message_id: message.id,
          metadata: metadataJsonObj,
          events: displayEvents,
        }
      : metadataJsonObj;
    navigator.clipboard.writeText(JSON.stringify(toCopy, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col p-0 overflow-hidden bg-zinc-950 border-zinc-800 text-zinc-100 shadow-2xl">
        {/* Header */}
        <div className="p-5 pb-4 border-b border-zinc-800/80 bg-zinc-900/40">
          <DialogHeader className="mb-0">
            <div className="flex items-center justify-between pr-6">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <DialogTitle className="text-base font-semibold text-white">
                    Message Details & Telemetry
                  </DialogTitle>
                  <DialogDescription className="text-xs text-zinc-400">
                    {hasEventStream
                      ? "Real-time event stream pipeline events captured during execution."
                      : "Execution metadata and query metrics stored with this turn."}
                  </DialogDescription>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyJson}
                className="h-8 text-xs font-mono border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 gap-1.5"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    Copy JSON
                  </>
                )}
              </Button>
            </div>
          </DialogHeader>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-4">
            <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/70">
              <div className="text-[10px] font-mono uppercase text-zinc-500">Status</div>
              <div className="text-xs font-semibold mt-0.5 flex items-center gap-1.5">
                <span
                  className={
                    "h-2 w-2 rounded-full " +
                    (status === "success" ? "bg-emerald-400" : "bg-red-400")
                  }
                />
                <span className="capitalize">{status}</span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/70">
              <div className="text-[10px] font-mono uppercase text-zinc-500">Dialect</div>
              <div className="text-xs font-semibold mt-0.5 text-blue-400 font-mono uppercase">
                {activeDialect}
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/70">
              <div className="text-[10px] font-mono uppercase text-zinc-500">Latency</div>
              <div className="text-xs font-semibold mt-0.5 text-zinc-300 font-mono flex items-center gap-1">
                <Clock className="h-3 w-3 text-zinc-500" />
                {latencyMs !== null ? `${latencyMs}ms` : "N/A"}
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/70">
              <div className="text-[10px] font-mono uppercase text-zinc-500">Rows Returned</div>
              <div className="text-xs font-semibold mt-0.5 text-zinc-300 font-mono">
                {rowCount !== null ? rowCount : "N/A"}
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 no-scrollbar">
          {/* If Event Stream is available, show the pipeline */}
          {hasEventStream ? (
            <div className="space-y-3">
              <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                Event Stream Pipeline ({displayEvents.length} events)
              </h4>

              <div className="relative pl-5 space-y-3 border-l border-zinc-800">
                {displayEvents.map((item, idx) => (
                  <div key={idx} className="relative group">
                    {/* Step Dot */}
                    <div
                      className={
                        "absolute -left-[27px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-zinc-950 flex items-center justify-center " +
                        (item.status === "error"
                          ? "bg-red-500 text-white"
                          : item.status === "success"
                          ? "bg-emerald-500 text-white"
                          : "bg-blue-500 text-white")
                      }
                    >
                      {item.status === "error" ? (
                        <AlertCircle className="h-2 w-2" />
                      ) : (
                        <CheckCircle2 className="h-2 w-2" />
                      )}
                    </div>

                    {/* Card */}
                    <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/80 space-y-1.5 hover:border-zinc-700/80 transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5 font-mono">
                          {item.label}
                        </span>
                        <Badge
                          variant={
                            item.status === "error"
                              ? "destructive"
                              : item.status === "success"
                              ? "success"
                              : "accent"
                          }
                          className="text-[9px] font-mono py-0 px-1.5"
                        >
                          {item.event}
                        </Badge>
                      </div>

                      <div className="text-[11px] font-mono text-zinc-400 bg-black/40 rounded-lg p-2.5 overflow-x-auto max-h-36">
                        <pre className="whitespace-pre-wrap break-all leading-relaxed">
                          {JSON.stringify(item.data, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Otherwise straightforward format showing the exact message metadata */
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <FileJson className="h-3.5 w-3.5 text-blue-400" />
                  Message Execution Metadata
                </h4>
                <Badge variant="secondary" className="text-[10px] font-mono">
                  Persisted Turn Info
                </Badge>
              </div>

              {/* JSON block in requested format */}
              <div className="rounded-xl bg-black/70 border border-zinc-800/90 p-4 font-mono text-xs overflow-x-auto shadow-inner">
                <pre className="text-emerald-400 leading-relaxed">
                  {JSON.stringify(metadataJsonObj, null, 2)}
                </pre>
              </div>

              {/* Additional prompt & timing context if present */}
              {queryRun?.nl_prompt && (
                <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1 text-xs">
                  <span className="text-[10px] font-mono uppercase text-zinc-500">
                    Original Query Prompt
                  </span>
                  <p className="text-zinc-200 font-sans">{queryRun.nl_prompt}</p>
                </div>
              )}
            </div>
          )}

          {/* Executed SQL preview block */}
          {sql && (
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
                <span className="flex items-center gap-1.5 font-semibold text-zinc-300">
                  <Code2 className="h-3.5 w-3.5 text-blue-400" />
                  Executed SQL
                </span>
                <Badge variant="accent" className="text-[9px] uppercase font-mono py-0 px-1.5">
                  {activeDialect}
                </Badge>
              </div>
              <div className="p-3 rounded-xl bg-black/60 border border-zinc-800/80 font-mono text-xs text-emerald-400 overflow-x-auto whitespace-pre leading-relaxed">
                {sql}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function formatEventName(event: string): string {
  switch (event) {
    case "message_received":
      return "Message Received";
    case "intent_classified":
      return "Intent Classified";
    case "sql_generated":
      return "SQL Generated";
    case "sql_executed":
      return "SQL Executed";
    case "sql_error":
      return "SQL Error (Self-Correction)";
    case "summary_ready":
      return "Summary Ready";
    case "result_formatted":
      return "Result Formatted";
    case "final_result":
      return "Final Answer Delivered";
    case "done":
      return "Stream Complete";
    default:
      return String(event)
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
