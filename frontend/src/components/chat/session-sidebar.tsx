"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  Search,
  Sparkles,
} from "lucide-react";
import type { ChatSession } from "@/types/chat";
import { chatApi } from "@/lib/api/chat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface SessionSidebarProps {
  projectId: string;
  activeSessionId?: string;
  className?: string;
}

export function SessionSidebar({
  projectId,
  activeSessionId,
  className,
}: SessionSidebarProps): React.JSX.Element {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Edit title dialog
  const [editingSession, setEditingSession] = useState<ChatSession | null>(null);
  const [newTitle, setNewTitle] = useState("");

  // Delete dialog
  const [deletingSession, setDeletingSession] = useState<ChatSession | null>(null);

  const router = useRouter();
  const pathname = usePathname();

  const fetchSessions = useCallback(async () => {
    try {
      const res = await chatApi.listSessions(projectId, { limit: 50 });
      if (res.success && res.data) {
        setSessions(res.data.items || []);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load sessions";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    let isMounted = true;
    chatApi
      .listSessions(projectId, { limit: 50 })
      .then((res) => {
        if (!isMounted) return;
        if (res.success && res.data) {
          setSessions(res.data.items || []);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [projectId]);

  const handleCreateSession = async () => {
    try {
      const res = await chatApi.createSession(projectId, {
        title: "New Query Session",
      });
      if (res.success && res.data) {
        toast.success("New chat session created");
        setSessions((prev) => [res.data as ChatSession, ...prev]);
        router.push(`/projects/${projectId}/chat/${res.data.id}`);
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to create session";
      toast.error(msg);
    }
  };

  const handleUpdateTitle = async () => {
    if (!editingSession || !newTitle.trim()) return;
    try {
      const res = await chatApi.updateSession(projectId, editingSession.id, {
        title: newTitle.trim(),
      });
      if (res.success && res.data) {
        setSessions((prev) =>
          prev.map((s) => (s.id === editingSession.id ? (res.data as ChatSession) : s))
        );
        toast.success("Session title updated");
        setEditingSession(null);
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to update title";
      toast.error(msg);
    }
  };

  const handleDeleteSession = async () => {
    if (!deletingSession) return;
    try {
      const res = await chatApi.deleteSession(projectId, deletingSession.id);
      if (res.success) {
        setSessions((prev) => prev.filter((s) => s.id !== deletingSession.id));
        toast.success("Session deleted");
        if (activeSessionId === deletingSession.id) {
          router.push(`/projects/${projectId}/chat`);
        }
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to delete session";
      toast.error(msg);
    } finally {
      setDeletingSession(null);
    }
  };

  const filteredSessions = sessions.filter((s) => {
    const title = (s.title || "Untitled Session").toLowerCase();
    return title.includes(search.toLowerCase());
  });

  return (
    <>
      <div
        className={cn(
          "flex flex-col w-72 shrink-0 border-r border-zinc-800/80 bg-zinc-950/80 text-zinc-300 h-full select-none overflow-hidden",
          className
        )}
      >
        {/* Top Action */}
        <div className="p-3 border-b border-zinc-800/80 space-y-2">
          <Button
            onClick={handleCreateSession}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs gap-1.5 shadow-md shadow-blue-600/20"
          >
            <Plus className="h-4 w-4" />
            New Chat Session
          </Button>

          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-zinc-500" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search chat history..."
              className="h-8 text-xs pl-8 bg-zinc-900 border-zinc-800"
            />
          </div>
        </div>

        {/* Sessions Scroll List */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden no-scrollbar p-2 space-y-1">
          {isLoading ? (
            <div className="space-y-2 p-2">
              <div className="h-10 bg-zinc-900 rounded-xl animate-pulse" />
              <div className="h-10 bg-zinc-900 rounded-xl animate-pulse" />
              <div className="h-10 bg-zinc-900 rounded-xl animate-pulse" />
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="p-6 text-center text-xs text-zinc-500">
              No sessions found. Click &quot;New Chat Session&quot; to begin.
            </div>
          ) : (
            filteredSessions.map((session) => {
              const isActive = session.id === activeSessionId;
              const title = session.title || "Untitled Session";
              const date = new Date(session.created_at).toLocaleDateString(
                undefined,
                { month: "short", day: "numeric" }
              );

              return (
                <div
                  key={session.id}
                  className={cn(
                    "group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-xs transition-colors cursor-pointer",
                    isActive
                      ? "bg-blue-600/10 text-blue-300 border border-blue-500/20 font-medium"
                      : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
                  )}
                >
                  <Link
                    href={`/projects/${projectId}/chat/${session.id}`}
                    className="flex-1 min-w-0 pr-2"
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquare
                        className={cn(
                          "h-3.5 w-3.5 shrink-0",
                          isActive ? "text-blue-400" : "text-zinc-500"
                        )}
                      />
                      <span className="truncate">{title}</span>
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono pl-5.5 mt-0.5">
                      {date}
                    </div>
                  </Link>

                  {/* Actions (Rename / Delete) */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSession(session);
                        setNewTitle(session.title || "");
                      }}
                      className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                      title="Rename Session"
                    >
                      <Edit2 className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeletingSession(session);
                      }}
                      className="p-1 rounded text-zinc-400 hover:text-red-400 hover:bg-red-500/10"
                      title="Delete Session"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Engine Footer Indicator */}
        <div className="p-3 border-t border-zinc-800/80 bg-zinc-950/90 text-xs">
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span className="flex items-center gap-1.5 font-medium text-zinc-300">
              <Sparkles className="h-3 w-3 text-blue-400" />
              <span>Groq AI Engine</span>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-mono border border-blue-500/20">
              gpt-oss-20b
            </span>
          </div>
          <div className="text-[10px] text-zinc-400 mt-0.5 font-mono">
            LangGraph Agentic SQL
          </div>
        </div>
      </div>

      {/* Rename Dialog */}
      <Dialog
        open={!!editingSession}
        onOpenChange={(open) => !open && setEditingSession(null)}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename Chat Session</DialogTitle>
            <DialogDescription>
              Provide a new descriptive title for this conversation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="session-title">Session Title</Label>
            <Input
              id="session-title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="e.g. Q3 Sales Analysis"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setEditingSession(null)}
              className="text-zinc-400"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateTitle}
              className="bg-blue-600 hover:bg-blue-500 text-white"
            >
              Save Title
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <ConfirmDialog
        open={!!deletingSession}
        onOpenChange={(open) => !open && setDeletingSession(null)}
        title="Delete Chat Session?"
        description={`Are you sure you want to delete "${deletingSession?.title || "this session"}"? All messages and generated queries will be permanently removed.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDeleteSession}
      />
    </>
  );
}
