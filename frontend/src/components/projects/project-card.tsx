"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Database,
  ArrowRight,
  Trash2,
  Calendar,
  Layers,
} from "lucide-react";
import type { Project } from "@/types/project";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { projectsApi } from "@/lib/api/projects";
import { toast } from "sonner";

interface ProjectCardProps {
  project: Project;
  onDeleted?: () => void;
}

export function ProjectCard({
  project,
  onDeleted,
}: ProjectCardProps): React.JSX.Element {
  const [deleteOpen, setDeleteOpen] = useState(false);

  const handleDelete = async () => {
    try {
      const res = await projectsApi.delete(project.id);
      if (res.success) {
        toast.success(`Deleted project "${project.name}"`);
        onDeleted?.();
      } else {
        throw new Error(res.message || "Failed to delete project");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete project";
      toast.error(msg);
    }
  };

  const formattedDate = new Date(project.created_at).toLocaleDateString(
    undefined,
    {
      month: "short",
      day: "numeric",
      year: "numeric",
    }
  );

  return (
    <>
      <Card className="group relative flex flex-col justify-between overflow-hidden border-zinc-800/80 bg-zinc-900/50 hover:bg-zinc-900/90 hover:border-blue-500/40 transition-all duration-200 shadow-lg">
        <div>
          <CardHeader className="p-5 pb-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Database className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base text-zinc-100 group-hover:text-blue-400 transition-colors line-clamp-1">
                    {project.name}
                  </h3>
                  <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 font-mono mt-0.5">
                    <Calendar className="h-3 w-3" />
                    <span>{formattedDate}</span>
                  </div>
                </div>
              </div>

              <Button
                variant="ghost"
                size="icon-sm"
                onClick={(e) => {
                  e.preventDefault();
                  setDeleteOpen(true);
                }}
                className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Delete Project"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>

          <CardContent className="p-5 pt-0">
            <p className="text-xs text-zinc-400 line-clamp-2 min-h-[32px] leading-relaxed">
              {project.description || "No description provided."}
            </p>
          </CardContent>
        </div>

        <CardFooter className="p-5 pt-3 border-t border-zinc-800/60 bg-zinc-950/30 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-zinc-500">
            <Layers className="h-3.5 w-3.5 text-zinc-400" />
            <span>Workspace</span>
          </div>

          <Link href={`/projects/${project.id}`}>
            <Button
              size="sm"
              className="bg-zinc-800 hover:bg-blue-600 hover:text-white text-zinc-200 text-xs font-medium gap-1.5 transition-colors"
            >
              Open
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </CardFooter>
      </Card>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Project?"
        description={`Are you sure you want to delete "${project.name}"? This action cannot be undone and will permanently remove all associated database connections, introspected schemas, vector embeddings, and chat history.`}
        confirmLabel="Delete Project"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </>
  );
}
