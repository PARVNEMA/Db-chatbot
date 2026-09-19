"use client";

import React, { useState } from "react";
import { Bot, User as UserIcon, Activity } from "lucide-react";
import type { ChatMessage, MutationPreviewData } from "@/types/chat";
import { SqlViewer } from "./sql-viewer";
import { QueryResultTable } from "./query-result-table";
import { MarkdownRenderer } from "./markdown-renderer";
import { EventStreamModal } from "./event-stream-modal";
import { MutationPreviewCard } from "./mutation-preview-card";
import { MutationActionButtons } from "./mutation-action-buttons";

interface MessageBubbleProps {
  message: ChatMessage;
  dialect?: string;
  isOwner?: boolean;
  onApprove?: (mutationId: string) => void;
  onReject?: (mutationId: string, reason?: string) => void;
  onUndo?: (mutationId: string, reason?: string) => void;
}

export function MessageBubble({
  message,
  dialect = "postgresql",
  isOwner = true,
  onApprove,
  onReject,
  onUndo,
}: MessageBubbleProps): React.JSX.Element {
  const [showModal, setShowModal] = useState(false);
  const isUser = message.role === "user";

  // Extract metadata fields if present
  const meta = message.metadata || message.metadata_json || {};
  const generatedSql = (meta.generated_sql as string) || (meta.sql as string);
  const executionResult = (meta.execution_result as Record<string, unknown>[]) || [];
  const resultRowCount = (meta.result_row_count as number) || executionResult.length;

  // Extract mutation fields if present
  const mutationId = (meta.mutation_id as string) || undefined;
  const mutationStatus = (meta.status as string) || undefined;
  const mutationChangeSet = meta.change_set as MutationPreviewData["change_set"] | undefined;
  const previewRowCounts = meta.preview_row_counts as Record<string, number> | undefined;
  const expiresAt = meta.expires_at as string | undefined;

  // Check if stream_events has a mutation_preview event
  let previewFromEvents: MutationPreviewData | undefined;
  if (message.stream_events) {
    const previewEvt = message.stream_events.find(
      (e) => e.event === "mutation_preview" || (e as unknown as { type: string }).type === "mutation_preview"
    );
    if (previewEvt) {
      previewFromEvents = ((previewEvt as unknown as { data?: MutationPreviewData }).data ||
        previewEvt) as MutationPreviewData;
    }
  }

  const effectivePreview: MutationPreviewData | undefined =
    previewFromEvents ||
    (mutationChangeSet
      ? {
          mutation_id: mutationId,
          change_set: mutationChangeSet,
          preview_row_counts: previewRowCounts,
          expires_at: expiresAt,
          total_rows_affected: meta.total_rows_affected as number | undefined,
        }
      : undefined);

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

          {/* Embedded Mutation Preview Card */}
          {effectivePreview && (
            <MutationPreviewCard
              preview={effectivePreview}
              status={mutationStatus || "PENDING_APPROVAL"}
              expiresAt={expiresAt}
            />
          )}

          {/* Embedded Mutation Action Controls (Approve, Reject, Undo) */}
          {mutationId && (mutationStatus === "PENDING_APPROVAL" || mutationStatus === "EXECUTED" || mutationStatus === "EXECUTING") && (
            <MutationActionButtons
              mutationId={mutationId}
              status={mutationStatus}
              isOwner={isOwner}
              onApprove={() => onApprove?.(mutationId)}
              onReject={(reason) => onReject?.(mutationId, reason)}
              onUndo={(reason) => onUndo?.(mutationId, reason)}
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
