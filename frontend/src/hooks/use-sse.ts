"use client";

import { useState, useRef, useCallback } from "react";
import { streamChatMessage } from "@/lib/api/chat";
import type { ChatSSEEvent, ChatMessage } from "@/types/chat";
import { toast } from "sonner";

export interface StreamState {
  isStreaming: boolean;
  currentStep:
    | "idle"
    | "message_received"
    | "intent_classified"
    | "sql_generated"
    | "sql_executed"
    | "summary_ready"
    | "result_formatted"
    | "final_result"
    | "error";
  intentType?: string;
  extractedEntities?: string[];
  generatedSql?: string;
  sqlDialect?: string;
  executionResult?: Record<string, unknown>[];
  resultRowCount?: number;
  sampleRows?: Record<string, unknown>[];
  nlSummary?: string;
  errorMessage?: string;
  retryCount?: number;
  latencyMs?: number;
  status?: string;
  events: ChatSSEEvent[];
  partialMessage?: Partial<ChatMessage>;
}

export function useChatSSE(projectId: string, sessionId: string) {
  const [streamState, setStreamState] = useState<StreamState>({
    isStreaming: false,
    currentStep: "idle",
    events: [],
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    (
      content: string,
      callbacks?: {
        onEvent?: (event: ChatSSEEvent) => void;
        onComplete?: (finalEvent: ChatSSEEvent) => void;
        onError?: (error: Error) => void;
      }
    ) => {
      // Reset state for new stream
      setStreamState({
        isStreaming: true,
        currentStep: "idle",
        intentType: undefined,
        extractedEntities: undefined,
        generatedSql: undefined,
        sqlDialect: undefined,
        executionResult: undefined,
        resultRowCount: undefined,
        sampleRows: undefined,
        nlSummary: undefined,
        errorMessage: undefined,
        retryCount: 0,
        latencyMs: undefined,
        status: undefined,
        events: [],
      });

      let lastEvent: ChatSSEEvent | null = null;

      const controller = streamChatMessage(
        projectId,
        sessionId,
        { content },
        {
          onEvent: (event: ChatSSEEvent) => {
            lastEvent = event;
            callbacks?.onEvent?.(event);

            setStreamState((prev) => ({
              ...prev,
              currentStep: event.event as StreamState["currentStep"],
              events: [...prev.events, event],
              intentType: event.intent_type ?? prev.intentType,
              extractedEntities: event.extracted_entities ?? prev.extractedEntities,
              generatedSql: event.generated_sql ?? prev.generatedSql,
              sqlDialect: event.sql_dialect ?? prev.sqlDialect,
              executionResult: event.execution_result ?? prev.executionResult,
              resultRowCount: event.result_row_count ?? event.row_count ?? prev.resultRowCount,
              sampleRows: event.sample_rows ?? prev.sampleRows,
              nlSummary: event.nl_summary ?? event.content ?? prev.nlSummary,
              errorMessage: event.error ?? event.error_message ?? event.message_text ?? prev.errorMessage,
              retryCount: event.retry_count ?? prev.retryCount,
              latencyMs: event.latency_ms ?? prev.latencyMs,
              status: event.status ?? prev.status,
              partialMessage: event.message ?? prev.partialMessage,
            }));

            if (event.event === "final_result") {
              setStreamState((prev) => ({
                ...prev,
                isStreaming: false,
                currentStep: "final_result",
              }));
              if (lastEvent) {
                callbacks?.onComplete?.(lastEvent);
              }
            } else if (event.event === "error" || event.event === "sql_error") {
              if (event.event === "error") {
                setStreamState((prev) => ({
                  ...prev,
                  isStreaming: false,
                  currentStep: "error",
                }));
                toast.error(event.error_message || event.error || event.message_text || "Agent execution failed");
              }
            }
          },
          onError: (err) => {
            setStreamState((prev) => ({
              ...prev,
              isStreaming: false,
              currentStep: "error",
              errorMessage: err.message,
            }));
            callbacks?.onError?.(err);
            toast.error(err.message || "Chat stream connection failed");
          },
          onComplete: () => {
            setStreamState((prev) => ({
              ...prev,
              isStreaming: false,
            }));
            if (lastEvent) {
              callbacks?.onComplete?.(lastEvent);
            }
          },
        }
      );

      abortControllerRef.current = controller;
    },
    [projectId, sessionId]
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setStreamState((prev) => ({
        ...prev,
        isStreaming: false,
      }));
      toast.info("Agent query execution stopped");
    }
  }, []);

  return {
    streamState,
    startStream,
    stopStream,
  };
}
