"use client";

import { useState, useRef, useCallback } from "react";
import { streamChatMessage } from "@/lib/api/chat";
import type { ChatSSEEvent, ChatMessage } from "@/types/chat";
import { toast } from "sonner";

export interface StreamState {
  isStreaming: boolean;
  currentStep:
    | "idle"
    | "intent_classified"
    | "sql_generated"
    | "sql_executed"
    | "result_formatted"
    | "final_result"
    | "error";
  intentType?: string;
  generatedSql?: string;
  executionResult?: Record<string, unknown>[];
  resultRowCount?: number;
  nlSummary?: string;
  errorMessage?: string;
  retryCount?: number;
  partialMessage?: Partial<ChatMessage>;
}

export function useChatSSE(projectId: string, sessionId: string) {
  const [streamState, setStreamState] = useState<StreamState>({
    isStreaming: false,
    currentStep: "idle",
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
        generatedSql: undefined,
        executionResult: undefined,
        resultRowCount: undefined,
        nlSummary: undefined,
        errorMessage: undefined,
        retryCount: 0,
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
              intentType: event.intent_type ?? prev.intentType,
              generatedSql: event.generated_sql ?? prev.generatedSql,
              executionResult: event.execution_result ?? prev.executionResult,
              resultRowCount: event.result_row_count ?? prev.resultRowCount,
              nlSummary: event.nl_summary ?? prev.nlSummary,
              errorMessage: event.error_message ?? prev.errorMessage,
              retryCount: event.retry_count ?? prev.retryCount,
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
                toast.error(event.error_message || "Agent execution failed");
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
