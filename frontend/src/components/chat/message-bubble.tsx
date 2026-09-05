"use client";

import React, { useState } from "react";
import { Bot, User as UserIcon, Activity } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import { SqlViewer } from "./sql-viewer";
import { QueryResultTable } from "./query-result-table";
import { MarkdownRenderer } from "./markdown-renderer";
import { EventStreamModal } from "./event-stream-modal";

interface MessageBubbleProps {
  message: ChatMessage;
  dialect?: string;
}

export function MessageBubble({
  message,
  dialect = "postgresql",
}: MessageBubbleProps): React.JSX.Element {
  const [showModal, setShowModal] = useState(false);
  const isUser = message.role === "user";

  // Extract metadata fields if present
  const meta = message.metadata || message.metadata_json || {};
  const generatedSql = (meta.generated_sql as string) || (meta.sql as string);
  const executionResult = (meta.execution_result as Record<string, unknown>[]) || [];
  const resultRowCount = (meta.result_row_count as number) || executionResult.length;

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 max-w-3xl ml-auto">
        <div className="flex flex-col items-end space-y-1">
          <div className="p-4 rounded-2xl rounded-tr-none bg-blue-600 text-white text-sm shadow-md font-sans leading-relaxed">
            {message.content}
          </div>
          <span className="text-[10px] font-mono text-zinc-500 pr-1">
            {new Date(message.created_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
        <div className="h-8 w-8 rounded-xl bg-blue-600/30 text-blue-400 border border-blue-500/30 flex items-center justify-center shrink-0">
          <UserIcon className="h-4 w-4" />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-start gap-3 max-w-4xl mr-auto group">
        <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center shrink-0 shadow-md shadow-blue-500/20">
          <Bot className="h-4 w-4" />
        </div>

        <div className="flex-1 space-y-2">
          {/* Main Text Content */}
          <div className="p-4 rounded-2xl rounded-tl-none bg-zinc-900/90 border border-zinc-800 text-zinc-200 text-sm shadow-md leading-relaxed font-sans overflow-hidden">
            <MarkdownRenderer content={message.content} />
          </div>

          {/* Embedded Generated SQL */}
          {generatedSql && (
            <SqlViewer sql={generatedSql} dialect={dialect} />
          )}

          {/* Embedded Execution Result Table */}
          {executionResult && executionResult.length > 0 && (
            <QueryResultTable
              rows={executionResult}
              rowCount={resultRowCount}
            />
          )}

          {/* Message Meta & Action Bar */}
          <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 pl-1">
            <div className="flex items-center gap-2">
              <span>
                {new Date(message.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              {message.token_count && (
                <span>• {message.token_count} tokens</span>
              )}
            </div>

            {/* View Details / Event Stream Action Button */}
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-md text-zinc-400 hover:text-blue-400 hover:bg-zinc-800/70 border border-zinc-800 transition-all font-sans text-xs"
              title="View message execution metadata and stream events"
            >
              <Activity className="h-3 w-3 text-blue-400" />
              <span>Details</span>
            </button>
          </div>
        </div>
      </div>

      {/* Execution Details & Event Stream Modal */}
      <EventStreamModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        message={message}
        events={message.stream_events}
        dialect={dialect}
      />
    </>
  );
}
