"use client";

import React, { use, useState, useEffect, useCallback } from "react";
import { useAuth } from "@/providers/auth-provider";
import { useProject } from "@/providers/project-provider";
import { chatApi } from "@/lib/api/chat";
import type { ChatMessage } from "@/types/chat";
import { useChatSSE } from "@/hooks/use-sse";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Wifi, WifiOff } from "lucide-react";

export default function ChatSessionPage({
  params,
}: {
  params: Promise<{ projectId: string; sessionId: string }>;
}): React.JSX.Element {
  const resolvedParams = use(params);
  const projectId = resolvedParams.projectId;
  const sessionId = resolvedParams.sessionId;

  const { user } = useAuth();
  const { project, connection } = useProject();
  const isOwner = !project || user?.id === project.owner_id || !!user?.is_superuser;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(true);

  // SSE Fallback hook
  const {
    streamState: sseStreamState,
    startStream: startSSEStream,
    stopStream: stopSSEStream,
  } = useChatSSE(projectId, sessionId);

  const fetchMessages = useCallback(async () => {
    try {
      const res = await chatApi.listMessages(projectId, sessionId, {
        limit: 100,
      });
      if (res.success && res.data) {
        setMessages(res.data.items || []);
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to load chat history";
      toast.error(msg);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [projectId, sessionId]);

  const handleFinalResult = useCallback(() => {
    // Re-fetch messages from DB to get verified persistence records
    void fetchMessages();
  }, [fetchMessages]);

  const handleResyncRequired = useCallback(() => {
    void fetchMessages();
  }, [fetchMessages]);

  // Primary WebSocket hook
  const {
    connectionStatus,
    streamState: wsStreamState,
    activeMutation,
    sendMessage: wsSendMessage,
    sendFieldResponse,
    sendApprove,
    sendReject,
    sendUndo,
  } = useChatWebSocket({
    projectId,
    sessionId,
    onFinalResult: handleFinalResult,
    onResyncRequired: handleResyncRequired,
  });

  const isWsConnected = connectionStatus === "connected";
  const activeStreamState = isWsConnected ? wsStreamState : sseStreamState;

  useEffect(() => {
    let isMounted = true;
    chatApi
      .listMessages(projectId, sessionId, { limit: 100 })
      .then((res) => {
        if (!isMounted) return;
        if (res.success && res.data) {
          setMessages(res.data.items || []);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setIsLoadingMessages(false);
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, sessionId]);

  // Message submission handler supporting Dry-Run and WS / SSE fallback
  const handleSendMessage = (content: string, dryRun: boolean = false) => {
    const optimisticUserMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      project_id: projectId,
      role: "user",
      content,
      token_count: null,
      metadata: dryRun ? { dry_run: true } : null,
      query_run_id: null,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMessage]);

    if (isWsConnected) {
      wsSendMessage(content, dryRun);
    } else {
      // Fallback to HTTP SSE
      startSSEStream(content, {
        onComplete: () => {
          void fetchMessages();
        },
        onError: () => {
          void fetchMessages();
        },
      });
    }
  };

  // Field response submission for missing required columns
  const handleProvideFields = (fields: Record<string, unknown>) => {
    if (isWsConnected) {
      sendFieldResponse(fields);
    } else {
      // If WS disconnected, submit as a follow-up natural language text
      const formatted = Object.entries(fields)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      handleSendMessage(`Provided missing fields: ${formatted}`);
    }
  };

  // Mutation approval handler (WS with REST fallback)
  const handleApprove = async (mutationId: string) => {
    if (isWsConnected) {
      sendApprove(mutationId);
    } else {
      try {
        const idemp = `idemp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        const res = await chatApi.approveMutation(projectId, sessionId, mutationId, {
          idempotency_key: idemp,
        });
        if (res.success) {
          toast.success("Mutation approved and execution queued.");
          await chatApi.executeMutation(projectId, sessionId, mutationId);
          void fetchMessages();
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Approval failed");
      }
    }
  };

  // Mutation rejection handler (WS with REST fallback)
  const handleReject = async (mutationId: string, reason?: string) => {
    if (isWsConnected) {
      sendReject(mutationId, reason);
    } else {
      try {
        await chatApi.rejectMutation(projectId, sessionId, mutationId, {
          reason,
        });
        toast.info("Mutation proposal rejected.");
        void fetchMessages();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Rejection failed");
      }
    }
  };

  // Soft-Undo handler (WS with REST fallback)
  const handleUndo = async (mutationId: string, reason?: string) => {
    if (isWsConnected) {
      sendUndo(mutationId, reason);
    } else {
      try {
        const res = await chatApi.undoMutation(projectId, sessionId, mutationId, {
          reason,
        });
        if (res.success) {
          toast.success("Transaction reverted successfully (soft-undo).");
          void fetchMessages();
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Soft-undo failed");
      }
    }
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] rounded-2xl border border-zinc-800/80 bg-zinc-950/60 overflow-hidden shadow-2xl">
      {/* Sessions Navigation Sidebar */}
      <SessionSidebar
        projectId={projectId}
        activeSessionId={sessionId}
        className="hidden md:flex"
      />

      {/* Main Chat Thread Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-zinc-950/40">
        {/* Real-time Connection Status Banner */}
        <div className="px-4 py-1.5 border-b border-zinc-800/60 bg-zinc-950/80 flex items-center justify-between text-[11px] font-mono text-zinc-400">
          <div className="flex items-center gap-2">
            {isWsConnected ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <Wifi className="h-3 w-3" />
                <span>WebSocket Connected (Interactive HITL Active)</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-zinc-500">
                <WifiOff className="h-3 w-3" />
                <span>SSE Stream Fallback</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {connection?.writes_enabled ? (
              <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">
                Writes Enabled
              </span>
            ) : (
              <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                Read-Only
              </span>
            )}
            <span>Dialect: <strong>{connection?.dialect || "postgresql"}</strong></span>
          </div>
        </div>

        {isLoadingMessages ? (
          <div className="flex-1 p-6 space-y-4">
            <Skeleton className="h-16 w-3/4 max-w-xl rounded-2xl" />
            <Skeleton className="h-24 w-3/4 max-w-xl ml-auto rounded-2xl" />
            <Skeleton className="h-32 w-3/4 max-w-xl rounded-2xl" />
          </div>
        ) : (
          <MessageList
            messages={messages}
            streamState={activeStreamState}
            dialect={connection?.dialect || "postgresql"}
            isOwner={isOwner}
            activeMutation={activeMutation}
            onProvideFields={handleProvideFields}
            onApprove={handleApprove}
            onReject={handleReject}
            onUndo={handleUndo}
          />
        )}

        {/* Input Bar */}
        <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md">
          <ChatInput
            onSendMessage={handleSendMessage}
            onStopStream={isWsConnected ? undefined : stopSSEStream}
            isStreaming={activeStreamState.isStreaming}
            disabled={isLoadingMessages}
          />
        </div>
      </div>
    </div>
  );
}
