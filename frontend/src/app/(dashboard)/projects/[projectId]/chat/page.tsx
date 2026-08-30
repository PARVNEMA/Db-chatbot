"use client";

import React, { use, useState } from "react";
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
  const [isCreating, setIsCreating] = useState(false);

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

  return (
    <div className="flex flex-col items-center justify-center min-h-[500px] text-center space-y-6 max-w-xl mx-auto py-10">
      <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-emerald-600 flex items-center justify-center text-white shadow-xl shadow-blue-500/20">
        <MessageSquare className="h-8 w-8" />
      </div>

      <div className="space-y-2">
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
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left pt-4">
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
            Read-only verification & query execution timeout protection.
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
  );
}
