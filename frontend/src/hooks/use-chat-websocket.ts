"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { API_BASE_URL } from "@/lib/constants";
import { getStoredToken } from "@/lib/api/client";
import type {
  WebSocketInboundMessage,
  WebSocketOutboundFrame,
  MissingFieldItem,
  MutationPreviewData,
  MutationApprovalRequiredData,
  MutationExecutedData,
} from "@/types/chat";

export type WebSocketConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export interface ActiveMutationState {
  status:
    | "IDLE"
    | "COLLECTING_INPUT"
    | "PENDING_APPROVAL"
    | "APPROVED"
    | "EXECUTING"
    | "EXECUTED"
    | "FAILED"
    | "EXPIRED"
    | "UNDONE"
    | "DRY_RUN";
  mutationId?: string | null;
  changeSetHash?: string;
  missingFields?: MissingFieldItem[];
  preview?: MutationPreviewData;
  approval?: MutationApprovalRequiredData;
  executed?: MutationExecutedData;
  error?: string;
}

export interface ChatWebSocketStreamState {
  isStreaming: boolean;
  currentStep: string;
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
  events: WebSocketOutboundFrame[];
}

interface UseChatWebSocketOptions {
  projectId: string;
  sessionId: string;
  onFinalResult?: (data: Record<string, unknown>) => void;
  onResyncRequired?: () => void;
  onError?: (err: Error) => void;
}

export function useChatWebSocket({
  projectId,
  sessionId,
  onFinalResult,
  onResyncRequired,
  onError,
}: UseChatWebSocketOptions) {
  const [connectionStatus, setConnectionStatus] =
    useState<WebSocketConnectionStatus>("disconnected");

  const [streamState, setStreamState] = useState<ChatWebSocketStreamState>({
    isStreaming: false,
    currentStep: "idle",
    events: [],
  });

  const [activeMutation, setActiveMutation] = useState<ActiveMutationState>({
    status: "IDLE",
  });

  const onFinalResultRef = useRef(onFinalResult);
  onFinalResultRef.current = onFinalResult;

  const onResyncRequiredRef = useRef(onResyncRequired);
  onResyncRequiredRef.current = onResyncRequired;

  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSeqRef = useRef<number | null>(null);
  const isIntentionalCloseRef = useRef<boolean>(false);

  // Helper to build ws URL from API_BASE_URL and credentials
  const getWebSocketUrl = useCallback(() => {
    let base = API_BASE_URL;
    if (base.startsWith("http://")) {
      base = base.replace("http://", "ws://");
    } else if (base.startsWith("https://")) {
      base = base.replace("https://", "wss://");
    } else if (typeof window !== "undefined") {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      base = `${protocol}//${window.location.host}${base}`;
    }

    const token = getStoredToken() || "";
    let url = `${base}/projects/${projectId}/chat/sessions/${sessionId}/ws?token=${encodeURIComponent(token)}`;
    if (lastSeqRef.current !== null && lastSeqRef.current > 0) {
      url += `&last_seq=${lastSeqRef.current}`;
    }
    return url;
  }, [projectId, sessionId]);

  // Send raw frame
  const sendRaw = useCallback((payload: WebSocketInboundMessage): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false;
    }
    try {
      wsRef.current.send(JSON.stringify(payload));
      return true;
    } catch (err) {
      loggerError("Failed to send WebSocket frame:", err);
      return false;
    }
  }, []);

  const handleFrame = useCallback(
    (frame: WebSocketOutboundFrame) => {
      // Record monotonic sequence for replay
      if (typeof frame.sequence === "number") {
        lastSeqRef.current = frame.sequence;
      }

      const type = frame.type;
      const data = frame.data || {};

      setStreamState((prev) => ({
        ...prev,
        currentStep: type,
        events: [...prev.events, frame],
      }));

      // Handle standard agent events
      switch (type) {
        case "pong":
          break;

        case "resync_required":
          toast.warning("Reconnection sequence gap detected. Refreshing messages.");
          onResyncRequiredRef.current?.();
          break;

        case "intent_classified":
          setStreamState((prev) => ({
            ...prev,
            intentType: data.intent_type as string | undefined,
            extractedEntities: data.extracted_entities as string[] | undefined,
          }));
          break;

        case "sql_generated":
          setStreamState((prev) => ({
            ...prev,
            generatedSql: data.generated_sql as string | undefined,
            sqlDialect: data.sql_dialect as string | undefined,
          }));
          break;

        case "sql_executed":
          setStreamState((prev) => ({
            ...prev,
            resultRowCount: (data.row_count as number) || 0,
            sampleRows: data.sample_rows as Record<string, unknown>[] | undefined,
            executionResult: data.sample_rows as Record<string, unknown>[] | undefined,
          }));
          break;

        case "sql_error":
          setStreamState((prev) => ({
            ...prev,
            errorMessage: data.error as string | undefined,
            retryCount: (data.retry_count as number) || prev.retryCount,
          }));
          break;

        case "summary_ready":
          setStreamState((prev) => ({
            ...prev,
            nlSummary: data.nl_summary as string | undefined,
          }));
          break;

        case "final_result":
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            nlSummary: (data.content as string) || prev.nlSummary,
            generatedSql: (data.generated_sql as string) || prev.generatedSql,
            executionResult: (data.execution_result as Record<string, unknown>[]) || prev.executionResult,
            latencyMs: (data.latency_ms as number) || prev.latencyMs,
            status: (data.status as string) || "success",
          }));
          onFinalResultRef.current?.(data);
          break;

        case "done":
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
          }));
          break;

        case "error":
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            errorMessage: (data.message as string) || "Agent execution error",
          }));
          toast.error((data.message as string) || "Agent encountered an error.");
          break;

        // ==========================================
        // Safe Write Pipeline HITL Frames
        // ==========================================
        case "mutation_field_required": {
          const fields = (data.missing_fields as MissingFieldItem[]) || [];
          setActiveMutation({
            status: "COLLECTING_INPUT",
            missingFields: fields,
            error: undefined,
          });
          break;
        }

        case "mutation_preview": {
          const isDryRun = !!data.dry_run;
          setActiveMutation((prev) => ({
            ...prev,
            status: isDryRun ? "DRY_RUN" : "PENDING_APPROVAL",
            mutationId: (data.mutation_id as string) || null,
            preview: data as unknown as MutationPreviewData,
          }));
          break;
        }

        case "mutation_approval_required": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "PENDING_APPROVAL",
            mutationId: (data.mutation_id as string) || prev.mutationId,
            approval: data as unknown as MutationApprovalRequiredData,
          }));
          break;
        }

        case "mutation_approved": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "APPROVED",
            mutationId: (data.mutation_id as string) || prev.mutationId,
          }));
          break;
        }

        case "mutation_executing": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "EXECUTING",
            mutationId: (data.mutation_id as string) || prev.mutationId,
          }));
          break;
        }

        case "mutation_executed": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "EXECUTED",
            mutationId: (data.mutation_id as string) || prev.mutationId,
            executed: data as unknown as MutationExecutedData,
          }));
          toast.success(
            `Mutation executed: ${data.total_rows_affected ?? 0} row(s) updated.`
          );
          onFinalResultRef.current?.(data);
          break;
        }

        case "mutation_rejected": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "FAILED",
            error: (data.reason as string) || "Mutation proposal rejected.",
          }));
          toast.info("Mutation proposal was rejected.");
          break;
        }

        case "mutation_failed": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "FAILED",
            error: (data.error as string) || "Mutation execution failed.",
          }));
          toast.error((data.error as string) || "Database mutation execution failed.");
          break;
        }

        case "mutation_undone": {
          setActiveMutation((prev) => ({
            ...prev,
            status: "UNDONE",
            error: undefined,
          }));
          toast.success("Executed mutation successfully reverted (soft-undo).");
          onFinalResultRef.current?.(data);
          break;
        }

        case "mutation_undo_failed": {
          toast.error((data.error as string) || "Failed to revert mutation.");
          break;
        }

        default:
          break;
      }
    },
    []
  );

  // Helper to safely detach all event listeners and close a websocket instance
  const cleanupSocket = useCallback((ws: WebSocket | null, reason = "Closing socket") => {
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    try {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, reason);
      }
    } catch {
      // Ignore close exceptions on already closing/closed socket
    }
  }, []);

  // Connect WebSocket
  const connect = useCallback(() => {
    if (typeof window === "undefined") return;
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const token = getStoredToken();
    if (!token) {
      setConnectionStatus("disconnected");
      return;
    }

    // Clean up any existing stale socket before opening a new one
    if (wsRef.current) {
      cleanupSocket(wsRef.current, "Replacing existing socket");
      wsRef.current = null;
    }

    setConnectionStatus("connecting");
    const url = getWebSocketUrl();

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (ws !== wsRef.current) return;
        setConnectionStatus("connected");
        reconnectAttemptsRef.current = 0;

        // Start heartbeat ping every 30s
        if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 30000);
      };

      ws.onmessage = (event: MessageEvent) => {
        if (ws !== wsRef.current) return;
        try {
          const raw = JSON.parse(event.data as string);
          handleFrame(raw as WebSocketOutboundFrame);
        } catch {
          // Ignore unparseable frame
        }
      };

      ws.onerror = (evt) => {
        if (ws !== wsRef.current) return;
        if (isIntentionalCloseRef.current) return;
        loggerError("WebSocket connection error:", evt);
        setConnectionStatus("error");
        onErrorRef.current?.(new Error("WebSocket error"));
      };

      ws.onclose = (event: CloseEvent) => {
        if (ws !== wsRef.current) return;
        setConnectionStatus("disconnected");
        if (heartbeatTimerRef.current) {
          clearInterval(heartbeatTimerRef.current);
          heartbeatTimerRef.current = null;
        }

        if (isIntentionalCloseRef.current) return;

        // Handle specific close codes
        if (event.code === 4001) {
          toast.error("Session authentication expired or invalid.");
          return;
        }
        if (event.code === 4003) {
          toast.error("Access denied to this project chat.");
          return;
        }
        if (event.code === 4004) {
          toast.error("Chat session not found.");
          return;
        }

        // Attempt reconnection if not intentional close
        if (reconnectAttemptsRef.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
          reconnectAttemptsRef.current += 1;
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (err) {
      setConnectionStatus("error");
      loggerError("Failed to instantiate WebSocket:", err);
    }
  }, [cleanupSocket, getWebSocketUrl, handleFrame]);

  // Lifecycle
  useEffect(() => {
    isIntentionalCloseRef.current = false;
    connect();

    return () => {
      isIntentionalCloseRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
      const ws = wsRef.current;
      wsRef.current = null;
      cleanupSocket(ws, "Component unmounted");
    };
  }, [projectId, sessionId, connect, cleanupSocket]);

  // ==========================================
  // Public Action Dispatchers
  // ==========================================

  const sendMessage = useCallback(
    (content: string, dryRun: boolean = false) => {
      setStreamState({
        isStreaming: true,
        currentStep: "message_received",
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

      setActiveMutation({ status: "IDLE" });

      const sent = sendRaw({
        type: "message",
        content,
        dry_run: dryRun,
      });

      if (!sent) {
        toast.error("WebSocket not connected. Please wait or refresh.");
        setStreamState((prev) => ({ ...prev, isStreaming: false }));
      }
    },
    [sendRaw]
  );

  const sendFieldResponse = useCallback(
    (fields: Record<string, unknown>) => {
      const sent = sendRaw({
        type: "field_response",
        session_id: sessionId,
        fields,
      });
      if (sent) {
        setActiveMutation((prev) => ({
          ...prev,
          status: "PENDING_APPROVAL",
          missingFields: undefined,
        }));
      } else {
        toast.error("Failed to send field values over WebSocket.");
      }
    },
    [sendRaw, sessionId]
  );

  const sendApprove = useCallback(
    (mutationId: string, idempotencyKey?: string) => {
      const key = idempotencyKey || `idemp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const sent = sendRaw({
        type: "approve",
        mutation_id: mutationId,
        idempotency_key: key,
      });
      if (sent) {
        setActiveMutation((prev) => ({
          ...prev,
          status: "APPROVED",
        }));
      } else {
        toast.error("Failed to send approval over WebSocket.");
      }
    },
    [sendRaw]
  );

  const sendReject = useCallback(
    (mutationId: string, reason?: string) => {
      const sent = sendRaw({
        type: "reject",
        mutation_id: mutationId,
        reason: reason || "Rejected by user.",
      });
      if (sent) {
        setActiveMutation((prev) => ({
          ...prev,
          status: "FAILED",
          error: reason || "Proposal rejected.",
        }));
      } else {
        toast.error("Failed to send rejection over WebSocket.");
      }
    },
    [sendRaw]
  );

  const sendUndo = useCallback(
    (mutationId: string, reason?: string) => {
      const sent = sendRaw({
        type: "undo",
        mutation_id: mutationId,
        reason: reason || "Undone by user.",
      });
      if (sent) {
        setActiveMutation((prev) => ({
          ...prev,
          status: "EXECUTING",
        }));
      } else {
        toast.error("Failed to send undo request over WebSocket.");
      }
    },
    [sendRaw]
  );

  const clearActiveMutation = useCallback(() => {
    setActiveMutation({ status: "IDLE" });
  }, []);

  return {
    connectionStatus,
    streamState,
    activeMutation,
    sendMessage,
    sendFieldResponse,
    sendApprove,
    sendReject,
    sendUndo,
    clearActiveMutation,
    reconnect: connect,
  };
}

function loggerError(...args: unknown[]) {
  if (process.env.NODE_ENV !== "production") {
    console.error("[useChatWebSocket]", ...args);
  }
}
