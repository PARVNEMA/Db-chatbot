"use client";

import React, { useState, useRef } from "react";
import {
  Sparkles,
  Play,
  Square,
  CheckCircle2,
  Cpu,
  Layers,
  Terminal,
} from "lucide-react";
import { streamEmbeddingGeneration } from "@/lib/api/embeddings";
import type { EmbeddingSSEEvent } from "@/types/embedding";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

interface EmbeddingGeneratorDialogProps {
  projectId: string;
  onCompleted?: () => void;
  trigger?: React.ReactNode;
}

export function EmbeddingGeneratorDialog({
  projectId,
  onCompleted,
  trigger,
}: EmbeddingGeneratorDialogProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [progress, setProgress] = useState(0);
  const [totalColumns, setTotalColumns] = useState(0);
  const [completedColumns, setCompletedColumns] = useState(0);
  const [currentTable, setCurrentTable] = useState<string | null>(null);
  const [currentColumn, setCurrentColumn] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>(
    "Ready to generate embeddings"
  );
  const [isDone, setIsDone] = useState(false);
  const [logEvents, setLogEvents] = useState<
    Array<{ id: string; time: string; message: string; type: string }>
  >([]);

  const abortRef = useRef<AbortController | null>(null);

  const addLog = (message: string, type: string) => {
    setLogEvents((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(7),
        time: new Date().toLocaleTimeString(),
        message,
        type,
      },
    ]);
  };

  const startGeneration = () => {
    setIsStreaming(true);
    setIsDone(false);
    setProgress(0);
    setCompletedColumns(0);
    setLogEvents([]);
    setStatusMessage("Connecting to embedding stream...");

    const controller = streamEmbeddingGeneration(projectId, {
      onEvent: (event: EmbeddingSSEEvent) => {
        const raw = event as unknown as Record<string, unknown>;
        const eventName = event.event || (raw.event as string);
        const total = event.total_columns || (raw.total as number) || 0;
        const completed =
          event.columns_processed || (raw.completed as number) || 0;
        const percent =
          event.progress_percent ||
          (raw.percentage as number) ||
          Math.round((completed / (total || 1)) * 100);
        const table = event.table_name || (raw.current_table as string) || null;
        const col = event.column_name || (raw.current_column as string) || null;
        const msg = event.message || (raw.message as string) || "";

        if (total) setTotalColumns(total);
        if (completed) setCompletedColumns(completed);
        if (percent) setProgress(percent);
        if (table) setCurrentTable(table);
        if (col) setCurrentColumn(col);
        if (msg) setStatusMessage(msg);

        if (eventName === "start") {
          addLog(msg || "Embedding generation initialized", "start");
        } else if (eventName === "progress") {
          addLog(
            `Embedded ${table}.${col} (${completed}/${total})`,
            "progress"
          );
        } else if (eventName === "complete") {
          setProgress(100);
          setIsDone(true);
          setIsStreaming(false);
          addLog(msg || "Vector embeddings generated and stored!", "complete");
          toast.success("Vector embeddings generated successfully!");
          onCompleted?.();
        } else if (eventName === "error") {
          setIsStreaming(false);
          addLog(`Error: ${event.error || msg}`, "error");
          toast.error(`Embedding generation error: ${event.error || msg}`);
        }
      },
      onError: (err) => {
        setIsStreaming(false);
        addLog(`Stream error: ${err.message}`, "error");
        toast.error(err.message || "Failed to generate embeddings");
      },
      onComplete: () => {
        setIsStreaming(false);
      },
    });

    abortRef.current = controller;
  };

  const stopGeneration = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      setIsStreaming(false);
      setStatusMessage("Embedding generation stopped by user");
      addLog("Stream aborted", "error");
      toast.info("Embedding stream stopped");
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && isStreaming) {
      stopGeneration();
    }
    setOpen(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button
            variant="outline"
            size="sm"
            className="border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 text-xs gap-1.5 font-medium"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            Generate Vector Embeddings
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-w-xl">
        <DialogHeader>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle>Generate Schema Embeddings</DialogTitle>
              <DialogDescription>
                Build 384-dimensional pgvector embeddings using{" "}
                <span className="font-mono text-zinc-300">BAAI/bge-small-en-v1.5</span> for high-accuracy schema retrieval.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Progress Bar & Metric Header */}
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-zinc-400 flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-blue-400" />
                {currentTable && currentColumn
                  ? `Embedding: ${currentTable}.${currentColumn}`
                  : statusMessage}
              </span>
              <span className="text-indigo-400 font-bold">{progress}%</span>
            </div>

            {/* Visual Progress Bar */}
            <div className="w-full h-2.5 rounded-full bg-zinc-900 overflow-hidden border border-zinc-800">
              <div
                className="h-full bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-500 transition-all duration-300 rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 pt-1">
              <span>
                Processed: {completedColumns} / {totalColumns || "—"} columns
              </span>
              {isDone && (
                <Badge variant="success" className="text-[10px] py-0 gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Synced to pgvector
                </Badge>
              )}
            </div>
          </div>

          {/* Real-Time Event Log Terminal */}
          <div className="rounded-xl border border-zinc-800 bg-black/60 overflow-hidden">
            <div className="px-3 py-2 bg-zinc-950/80 border-b border-zinc-800 flex items-center justify-between text-[11px] font-mono text-zinc-400">
              <div className="flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-emerald-400" />
                <span>Live SSE Progress Stream</span>
              </div>
              <span>{logEvents.length} events</span>
            </div>
            <div className="p-3 font-mono text-xs max-h-40 overflow-y-auto space-y-1.5">
              {logEvents.length === 0 ? (
                <div className="text-zinc-600 text-center py-4 text-[11px]">
                  Click &quot;Start Generation Stream&quot; to begin encoding schema columns.
                </div>
              ) : (
                logEvents.map((log) => (
                  <div key={log.id} className="flex items-start gap-2 text-[11px]">
                    <span className="text-zinc-500 shrink-0">{log.time}</span>
                    <span
                      className={`px-1 py-0.2 rounded text-[9px] uppercase font-bold shrink-0 ${
                        log.type === "start"
                          ? "bg-blue-500/20 text-blue-400"
                          : log.type === "progress"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : log.type === "complete"
                          ? "bg-purple-500/20 text-purple-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {log.type}
                    </span>
                    <span className="text-zinc-300 truncate">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-zinc-800 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleOpenChange(false)}
            disabled={isStreaming}
            className="text-zinc-400 hover:text-white text-xs"
          >
            Close
          </Button>

          {isStreaming ? (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={stopGeneration}
              className="bg-red-600 hover:bg-red-500 text-white text-xs gap-1.5"
            >
              <Square className="h-3.5 w-3.5" />
              Stop Stream
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={startGeneration}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs gap-1.5 shadow-md shadow-indigo-600/20 font-medium"
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              {isDone ? "Re-Generate Embeddings" : "Start Generation Stream"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
