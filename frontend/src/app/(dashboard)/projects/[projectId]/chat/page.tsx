"use client";

import React, { use, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Plus,
  Sparkles,
  Database,
  Loader2,
  Plug,
} from "lucide-react";
import { chatApi } from "@/lib/api/chat";
import { useProject } from "@/providers/project-provider";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import Link from "next/link";
import { toast } from "sonner";

export default function ChatLandingPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): React.JSX.Element {
  const resolvedParams = use(params);
  const projectId = resolvedParams.projectId;
  const router = useRouter();
  const { connection, isLoading: isProjectLoading } = useProject();
  const [isCheckingSessions, setIsCheckingSessions] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    let isMounted = true;

    chatApi
      .listSessions(projectId, { limit: 1 })
      .then((res) => {
        if (!isMounted) return;
        if (res.success && res.data && res.data.items && res.data.items.length > 0) {
          const latestSession = res.data.items[0];
          router.replace(`/projects/${projectId}/chat/${latestSession.id}`);
        } else {
          setIsCheckingSessions(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsCheckingSessions(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, router]);

  const handleCreateSession = async () => {
    setIsCreating(true);
    try {
      const res = await chatApi.createSession(projectId, {
        title: "New Query Session",
      });
      if (res.success && res.data) {
        toast.success("Chat workspace initialized");
        router.push(`/projects/${projectId}/chat/${res.data.id}`);
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to create session";
      toast.error(msg);
      setIsCreating(false);
    }
  };

  if (!isProjectLoading && !connection) {
    return (
      <EmptyState
        icon={Plug}
        title="Database Connection Required"
        description="You must connect a database before you can ask natural language queries."
        action={
          <Link href={`/projects/${projectId}/connection`}>
            <Button className="bg-blue-600 hover:bg-blue-500 text-white text-xs gap-1.5">
              Connect Database First
            </Button>
          </Link>
        }
      />
    );
  }

  if (isCheckingSessions) {
    return (
      <div className="flex h-[calc(100vh-8.5rem)] rounded-2xl border border-zinc-800/80 bg-zinc-950/60 overflow-hidden shadow-2xl">
        <SessionSidebar projectId={projectId} className="hidden md:flex" />
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <p className="text-xs font-mono text-zinc-500">
            Loading chat sessions...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8.5rem)] rounded-2xl border border-zinc-800/80 bg-zinc-950/60 overflow-hidden shadow-2xl">
      {/* Sessions Sidebar */}
      <SessionSidebar projectId={projectId} className="hidden md:flex" />

      {/* Main Workspace Landing Area */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 text-center space-y-6 overflow-y-auto bg-zinc-950/40">
        <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-emerald-600 flex items-center justify-center text-white shadow-xl shadow-blue-500/20">
          <MessageSquare className="h-8 w-8" />
        </div>

        <div className="space-y-2 max-w-md">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Natural Language Database Chat
          </h2>
          <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
            Ask conversational questions about your schema. LangGraph Agent classifies intent, retrieves vector context, generates safe dialect SQL, and streams answers in real time.
          </p>
        </div>

        <Button
          size="lg"
          onClick={handleCreateSession}
          disabled={isCreating}
          className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm px-6 h-11 shadow-xl shadow-blue-600/25 gap-2"
        >
          {isCreating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating Session...
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              Start New Chat Session
            </>
          )}
        </Button>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl text-left pt-4">
          <div className="p-3.5 rounded-xl bg-zinc-900/50 border border-zinc-800/80 space-y-1">
            <div className="text-xs font-semibold text-blue-400 font-mono flex items-center gap-1.5">
              <Sparkles className="h-3 w-3" /> Dialect Precision
            </div>
            <p className="text-[11px] text-zinc-400 font-sans">
              Tailored for {connection?.dialect.toUpperCase() || "SQL"} syntax without hallucination.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-zinc-900/50 border border-zinc-800/80 space-y-1">
            <div className="text-xs font-semibold text-emerald-400 font-mono flex items-center gap-1.5">
              <Database className="h-3 w-3" /> 3-Layer Guardrails
            </div>
            <p className="text-[11px] text-zinc-400 font-sans">
              Read-only verification & execution timeout protection.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-zinc-900/50 border border-zinc-800/80 space-y-1">
            <div className="text-xs font-semibold text-indigo-400 font-mono flex items-center gap-1.5">
              <MessageSquare className="h-3 w-3" /> Multi-Turn Memory
            </div>
            <p className="text-[11px] text-zinc-400 font-sans">
              Ask follow-up questions in the same session seamlessly.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
