"use client";

import React, { useEffect, useRef, useState } from "react";
import { Bot, Activity } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import type { StreamState } from "@/hooks/use-sse";
import { MessageBubble } from "./message-bubble";
import { SSEStatusIndicator } from "./sse-status-indicator";
import { SqlViewer } from "./sql-viewer";
import { QueryResultTable } from "./query-result-table";
import { MarkdownRenderer } from "./markdown-renderer";
import { EventStreamModal } from "./event-stream-modal";

interface MessageListProps {
  messages: ChatMessage[];
  streamState: StreamState;
  dialect?: string;
}

export function MessageList({
  messages,
  streamState,
  dialect = "postgresql",
}: MessageListProps): React.JSX.Element {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showLiveModal, setShowLiveModal] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamState]);

  if (messages.length === 0 && !streamState.isStreaming) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
        <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-blue-600/20 via-indigo-600/20 to-emerald-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shadow-xl">
          <Bot className="h-8 w-8" />
        </div>
        <div className="space-y-1.5 max-w-md">
          <h3 className="text-lg font-bold text-white tracking-tight">
            How can AskMyDB help you today?
          </h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Ask any question about your database in natural language. The agent will retrieve relevant schema vectors, generate dialect SQL, execute with guardrails, and return visual results.
          </p>
        </div>
      </div>
    );
  }

  // Construct in-flight synthetic ChatMessage for the modal if user inspects while streaming
  const inFlightMessage: ChatMessage = {
    id: "in-flight-stream",
    session_id: "",
    project_id: "",
    role: "assistant",
    content: streamState.nlSummary || "Processing query via LangGraph...",
    token_count: null,
    metadata: {
      sql: streamState.generatedSql,
      dialect: dialect,
      status: streamState.stepStatus === "error" ? "failed" : "running",
      row_count: streamState.resultRowCount,
      latency_ms: null,
    },
    query_run_id: null,
    created_at: new Date().toISOString(),
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 no-scrollbar">
      {/* Existing History Messages */}
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} dialect={dialect} />
      ))}

      {/* Real-Time Live Streaming Message */}
      {streamState.isStreaming && (
        <div className="flex items-start gap-3 max-w-4xl mr-auto animate-in fade-in-0 duration-200">
          <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center shrink-0 shadow-md shadow-blue-500/20">
            <Bot className="h-4 w-4" />
          </div>

          <div className="flex-1 space-y-2">
            {/* Pipeline Step Progress Bar */}
            <SSEStatusIndicator streamState={streamState} />

            {/* In-Flight Generated SQL */}
            {streamState.generatedSql && (
              <SqlViewer sql={streamState.generatedSql} dialect={dialect} />
            )}

            {/* In-Flight Execution Result Table */}
            {streamState.executionResult &&
              streamState.executionResult.length > 0 && (
                <QueryResultTable
                  rows={streamState.executionResult}
                  rowCount={streamState.resultRowCount}
                />
              )}

            {/* In-Flight Natural Language Summary */}
            {streamState.nlSummary && (
              <div className="p-4 rounded-2xl rounded-tl-none bg-zinc-900/90 border border-zinc-800 text-zinc-200 text-sm shadow-md leading-relaxed font-sans overflow-hidden">
                <MarkdownRenderer content={streamState.nlSummary} />
              </div>
            )}

            {/* Live stream event inspector button */}
            <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 pl-1 pt-1">
              <span className="flex items-center gap-1.5 text-blue-400">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                </span>
                Streaming active...
              </span>

              <button
                onClick={() => setShowLiveModal(true)}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md text-zinc-400 hover:text-blue-400 hover:bg-zinc-800/70 border border-zinc-800 transition-all font-sans text-xs"
                title="View live event stream log"
              >
                <Activity className="h-3 w-3 text-blue-400" />
                <span>Live Events ({streamState.events.length})</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* In-flight Event Stream Modal */}
      {showLiveModal && (
        <EventStreamModal
          isOpen={showLiveModal}
          onClose={() => setShowLiveModal(false)}
          message={inFlightMessage}
          events={streamState.events}
          dialect={dialect}
        />
      )}

      <div ref={bottomRef} />
    </div>
  );
}
