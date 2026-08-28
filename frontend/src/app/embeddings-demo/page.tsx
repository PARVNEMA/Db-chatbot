"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Play,
  Square,
  Sparkles,
  Search,
  Database,
  Terminal,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  ArrowLeft,
  Key,
  FolderKey,
  Globe,
  RefreshCw,
} from "lucide-react";

interface SSEEvent {
  id: string;
  time: string;
  type: "start" | "progress" | "complete" | "error" | "info";
  data: any;
}

interface SearchResult {
  column_id: string;
  table_name: string;
  schema_name: string;
  column_name: string;
  data_type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  fk_target_table?: string;
  fk_target_column?: string;
  similarity_score: number;
  embed_text?: string;
}

export default function EmbeddingsDemoPage() {
  const [apiUrl, setApiUrl] = useState("http://localhost:8000");
  const [projectId, setProjectId] = useState("");
  const [token, setToken] = useState("");
  
  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("Ready to stream");
  const [currentTable, setCurrentTable] = useState<string | null>(null);
  const [currentColumn, setCurrentColumn] = useState<string | null>(null);
  const [totalColumns, setTotalColumns] = useState(0);
  const [completedColumns, setCompletedColumns] = useState(0);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);

  // Search state
  const [searchQuery, setSearchQuery] = useState("Show me customer orders and revenue");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const addEventLog = (type: SSEEvent["type"], data: any) => {
    setEvents((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(7),
        time: new Date().toLocaleTimeString(),
        type,
        data,
      },
    ]);
  };

  const startStreaming = async () => {
    if (!projectId.trim()) {
      alert("Please enter a valid Project UUID.");
      return;
    }

    setIsStreaming(true);
    setProgress(0);
    setCompletedColumns(0);
    setTotalColumns(0);
    setCurrentTable(null);
    setCurrentColumn(null);
    setEvents([]);
    setStatusMessage("Connecting to SSE stream...");

    addEventLog("info", { message: "Opening SSE stream to /schema/embeddings/generate?stream=true" });

    abortControllerRef.current = new AbortController();

    try {
      const endpoint = `${apiUrl.replace(/\/$/, "")}/api/v1/projects/${projectId}/schema/embeddings/generate?stream=true`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          Accept: "text/event-stream",
        },
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("ReadableStream not supported on this browser.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;

          let eventType = "message";
          let dataStr = "";

          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) {
              eventType = line.replace("event:", "").trim();
            } else if (line.startsWith("data:")) {
              dataStr = line.replace("data:", "").trim();
            }
          }

          if (dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              handleSSEMessage(eventType, parsed);
            } catch (err) {
              console.warn("Failed to parse SSE JSON:", dataStr, err);
            }
          }
        }
      }

      setStatusMessage("Stream completed successfully");
    } catch (err: any) {
      if (err.name === "AbortError") {
        setStatusMessage("Stream stopped by user");
        addEventLog("info", { message: "Stream manually aborted" });
      } else {
        setStatusMessage(`Error: ${err.message}`);
        addEventLog("error", { error: err.message });
      }
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSSEMessage = (eventType: string, data: any) => {
    if (eventType === "start" || data.event === "start") {
      setTotalColumns(data.total || 0);
      setActiveModel(data.model || null);
      setStatusMessage(data.message || "Embedding generation started");
      addEventLog("start", data);
    } else if (eventType === "progress" || data.event === "progress") {
      setCompletedColumns(data.completed || 0);
      setTotalColumns(data.total || totalColumns);
      setCurrentTable(data.current_table || null);
      setCurrentColumn(data.current_column || null);
      setProgress(data.percentage || Math.round(((data.completed || 0) / (data.total || 1)) * 100));
      setStatusMessage(data.message || `Processing ${data.completed}/${data.total}`);
      addEventLog("progress", data);
    } else if (eventType === "complete" || data.event === "complete") {
      setProgress(100);
      setCompletedColumns(data.total || completedColumns);
      setStatusMessage(data.message || "Embedding generation complete!");
      addEventLog("complete", data);
    } else if (eventType === "error" || data.event === "error") {
      setStatusMessage(`Error: ${data.message}`);
      addEventLog("error", data);
    } else {
      addEventLog("info", data);
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const runSchemaSearch = async () => {
    if (!projectId.trim()) {
      alert("Please enter a Project ID.");
      return;
    }
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    setSearchResults([]);

    try {
      const endpoint = `${apiUrl.replace(/\/$/, "")}/api/v1/projects/${projectId}/schema/search`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: searchQuery,
          top_k: 5,
        }),
      });

      const json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.message || json.error?.message || "Search failed");
      }

      setSearchResults(json.data || []);
    } catch (err: any) {
      setSearchError(err.message);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Navigation & Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 mb-2 transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Home
            </Link>
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-blue-600/20 text-blue-400 rounded-xl border border-blue-500/30">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Schema Embeddings SSE Demo
                  <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Live Stream
                  </span>
                </h1>
                <p className="text-sm text-zinc-400">
                  Real-time Server-Sent Events (SSE) progress streaming for database vector indexing.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setEvents([]);
                setProgress(0);
                setCompletedColumns(0);
                setTotalColumns(0);
              }}
              className="px-3 py-2 text-xs text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-1.5 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Clear Logs
            </button>
          </div>
        </div>

        {/* Configuration Bar */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-zinc-900/60 p-4 rounded-xl border border-zinc-800">
          <div>
            <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5 mb-1.5">
              <Globe className="w-3.5 h-3.5 text-zinc-500" /> Backend API Base URL
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
              placeholder="http://localhost:8000"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5 mb-1.5">
              <FolderKey className="w-3.5 h-3.5 text-zinc-500" /> Project UUID
            </label>
            <input
              type="text"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
              placeholder="e.g. 7c324e62-9011-4043-a6fe-4f113a303657"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5 mb-1.5">
              <Key className="w-3.5 h-3.5 text-zinc-500" /> Bearer Token (Optional)
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-blue-500"
              placeholder="JWT Token if auth enabled"
            />
          </div>
        </div>

        {/* Live SSE Progress Dashboard */}
        <div className="bg-zinc-900/80 rounded-2xl border border-zinc-800 p-6 space-y-6 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-blue-400" /> Real-Time Generation Stream
              </h2>
              <p className="text-xs text-zinc-400 flex items-center gap-2">
                Status:{" "}
                <span
                  className={`font-medium ${
                    isStreaming
                      ? "text-blue-400 animate-pulse"
                      : progress === 100
                      ? "text-emerald-400"
                      : "text-zinc-400"
                  }`}
                >
                  {statusMessage}
                </span>
              </p>
            </div>

            <div className="flex items-center gap-3">
              {!isStreaming ? (
                <button
                  onClick={startStreaming}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm rounded-xl flex items-center gap-2 shadow-lg shadow-blue-600/20 transition cursor-pointer"
                >
                  <Play className="w-4 h-4 fill-white" /> Start SSE Stream
                </button>
              ) : (
                <button
                  onClick={stopStreaming}
                  className="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-medium text-sm rounded-xl flex items-center gap-2 shadow-lg shadow-rose-600/20 transition cursor-pointer"
                >
                  <Square className="w-4 h-4 fill-white" /> Stop Stream
                </button>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
              <span>PROGRESS</span>
              <span className="text-white font-semibold">{progress}%</span>
            </div>
            <div className="w-full bg-zinc-950 h-3.5 rounded-full overflow-hidden border border-zinc-800 p-0.5">
              <div
                className="h-full bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
            <div className="bg-zinc-950 p-3.5 rounded-xl border border-zinc-800/80">
              <span className="text-xs text-zinc-500 font-medium">Columns Processed</span>
              <p className="text-xl font-bold text-white font-mono mt-1">
                {completedColumns} <span className="text-xs text-zinc-500">/ {totalColumns}</span>
              </p>
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-xl border border-zinc-800/80">
              <span className="text-xs text-zinc-500 font-medium">Current Table</span>
              <p className="text-sm font-semibold text-zinc-200 font-mono truncate mt-1">
                {currentTable || "—"}
              </p>
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-xl border border-zinc-800/80">
              <span className="text-xs text-zinc-500 font-medium">Current Column</span>
              <p className="text-sm font-semibold text-zinc-200 font-mono truncate mt-1">
                {currentColumn || "—"}
              </p>
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-xl border border-zinc-800/80">
              <span className="text-xs text-zinc-500 font-medium">Embedding Model</span>
              <p className="text-xs font-semibold text-zinc-300 font-mono truncate mt-1">
                {activeModel || "BAAI/bge-small-en-v1.5"}
              </p>
            </div>
          </div>
        </div>

        {/* Live SSE Event Log Terminal */}
        <div className="bg-zinc-900/80 rounded-2xl border border-zinc-800 overflow-hidden shadow-xl">
          <div className="bg-zinc-950/80 px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <Terminal className="w-4 h-4 text-emerald-400" /> SSE Live Event Stream
            </div>
            <span className="text-[11px] font-mono text-zinc-500">
              {events.length} events received
            </span>
          </div>

          <div className="p-4 bg-black/50 font-mono text-xs max-h-72 overflow-y-auto space-y-2">
            {events.length === 0 ? (
              <div className="text-zinc-600 py-8 text-center">
                No events streamed yet. Click "Start SSE Stream" to begin receiving live progress updates.
              </div>
            ) : (
              events.map((evt) => (
                <div
                  key={evt.id}
                  className="flex items-start gap-3 p-2 rounded bg-zinc-900/40 hover:bg-zinc-900/80 transition"
                >
                  <span className="text-zinc-500 text-[11px] shrink-0 mt-0.5">{evt.time}</span>
                  <span
                    className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase shrink-0 ${
                      evt.type === "start"
                        ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                        : evt.type === "progress"
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : evt.type === "complete"
                        ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                        : evt.type === "error"
                        ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {evt.type}
                  </span>
                  <pre className="text-zinc-300 whitespace-pre-wrap break-all flex-1">
                    {JSON.stringify(evt.data)}
                  </pre>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* Instant Schema Vector Search Tester */}
        <div className="bg-zinc-900/80 rounded-2xl border border-zinc-800 p-6 space-y-4 shadow-xl">
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-white">Test Vector Search Over Schema</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Verify that your newly generated embeddings return ranked columns for natural language queries.
          </p>

          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSchemaSearch()}
              placeholder="Ask a question (e.g. Which table stores sales totals and customer accounts?)"
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={runSchemaSearch}
              disabled={isSearching}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-xl flex items-center justify-center gap-2 transition cursor-pointer"
            >
              {isSearching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Search Schema
            </button>
          </div>

          {searchError && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {searchError}
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="space-y-2.5 pt-2">
              <span className="text-xs font-mono text-zinc-400">
                Top Matches Ranked by Cosine Similarity:
              </span>
              <div className="grid grid-cols-1 gap-2">
                {searchResults.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 bg-zinc-950 rounded-xl border border-zinc-800/80 flex flex-col md:flex-row md:items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-bold">
                          #{idx + 1}
                        </span>
                        <span className="text-sm font-semibold text-white font-mono">
                          {item.schema_name}.{item.table_name}.
                          <span className="text-indigo-400">{item.column_name}</span>
                        </span>
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                          {item.data_type}
                        </span>
                        {item.is_primary_key && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            PK
                          </span>
                        )}
                        {item.is_foreign_key && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                            FK → {item.fk_target_table}.{item.fk_target_column}
                          </span>
                        )}
                      </div>
                      {item.embed_text && (
                        <p className="text-xs text-zinc-400 line-clamp-1 italic font-sans">
                          {item.embed_text.replace(/\n/g, " | ")}
                        </p>
                      )}
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <span className="text-xs text-zinc-500 font-mono">Score:</span>
                      <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {typeof item.similarity_score === "number"
                          ? item.similarity_score.toFixed(4)
                          : item.similarity_score}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
