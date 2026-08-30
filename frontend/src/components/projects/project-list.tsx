"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Search, FolderGit2, RefreshCw } from "lucide-react";
import type { Project } from "@/types/project";
import { projectsApi } from "@/lib/api/projects";
import { ProjectCard } from "./project-card";
import { CreateProjectDialog } from "./create-project-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export function ProjectList(): React.JSX.Element {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");

  const fetchProjects = useCallback(async () => {
    try {
      const res = await projectsApi.list();
      if (res.success && res.data) {
        setProjects(res.data.items || []);
      } else {
        setProjects([]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load projects";
      toast.error(msg);
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    projectsApi
      .list()
      .then((res) => {
        if (!isMounted) return;
        if (res.success && res.data) {
          setProjects(res.data.items || []);
        } else {
          setProjects([]);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        const msg =
          err instanceof Error ? err.message : "Failed to load projects";
        toast.error(msg);
        setProjects([]);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleManualRefresh = () => {
    setIsLoading(true);
    void fetchProjects();
  };

  const filteredProjects = projects.filter((p) => {
    const q = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      (p.description && p.description.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Controls Bar: Search & Refresh */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <Input
            placeholder="Search projects by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-zinc-900/60 border-zinc-800"
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleManualRefresh}
            disabled={isLoading}
            className="border-zinc-800 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <CreateProjectDialog onSuccess={fetchProjects} />
        </div>
      </div>

      {/* Grid State */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="p-5 rounded-2xl border border-zinc-800/80 bg-zinc-900/30 space-y-4"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-xl" />
                <div className="space-y-1.5 flex-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              </div>
              <Skeleton className="h-8 w-full" />
              <div className="flex justify-between pt-2">
                <Skeleton className="h-4 w-1/4" />
                <Skeleton className="h-7 w-16" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredProjects.length === 0 ? (
        search ? (
          <EmptyState
            icon={Search}
            title="No matching projects"
            description={`No projects found matching "${search}". Try searching with a different keyword.`}
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSearch("")}
                className="border-zinc-700"
              >
                Clear Search
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={FolderGit2}
            title="No Projects Yet"
            description="Create your first database project to connect a target SQL engine, introspect schema, and start querying in natural language."
            action={<CreateProjectDialog onSuccess={fetchProjects} />}
          />
        )
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDeleted={fetchProjects}
            />
          ))}
        </div>
      )}
    </div>
  );
}
