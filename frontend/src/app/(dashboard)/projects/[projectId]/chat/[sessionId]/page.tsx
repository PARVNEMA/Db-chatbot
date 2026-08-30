"use client";

import React, { use, useState, useEffect, useCallback } from "react";
import { useProject } from "@/providers/project-provider";
import { chatApi } from "@/lib/api/chat";
import type { ChatMessage } from "@/types/chat";
import { useChatSSE } from "@/hooks/use-sse";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export default function ChatSessionPage({
  params,
}: {
  params: Promise<{ projectId: string; sessionId: string }>;
}): React.JSX.Element {
  const resolvedParams = use(params);
  const projectId = resolvedParams.projectId;
  const sessionId = resolvedParams.sessionId;

  const { connection } = useProject();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(true);

  const { streamState, startStream, stopStream } = useChatSSE(
    projectId,
    sessionId
  );

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

  const handleSendMessage = (content: string) => {
    // Optimistically append user message to UI
    const optimisticUserMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      project_id: projectId,
      role: "user",
      content,
      token_count: null,
      metadata: null,
      query_run_id: null,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMessage]);

    // Start SSE Stream with callbacks
    startStream(content, {
      onComplete: () => {
        // Refresh full verified messages from database
        void fetchMessages();
      },
      onError: () => {
        void fetchMessages();
      },
    });
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
        {isLoadingMessages ? (
          <div className="flex-1 p-6 space-y-4">
            <Skeleton className="h-16 w-3/4 max-w-xl rounded-2xl" />
            <Skeleton className="h-24 w-3/4 max-w-xl ml-auto rounded-2xl" />
            <Skeleton className="h-32 w-3/4 max-w-xl rounded-2xl" />
          </div>
        ) : (
          <MessageList
            messages={messages}
            streamState={streamState}
            dialect={connection?.dialect || "postgresql"}
          />
        )}

        {/* Input Bar */}
        <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md">
          <ChatInput
            onSendMessage={handleSendMessage}
            onStopStream={stopStream}
            isStreaming={streamState.isStreaming}
            disabled={isLoadingMessages}
          />
        </div>
      </div>
    </div>
  );
}
