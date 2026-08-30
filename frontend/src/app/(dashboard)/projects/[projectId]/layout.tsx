"use client";

import React, { use } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Plug,
  TableProperties,
  MessageSquare,
} from "lucide-react";
import { ProjectProvider, useProject } from "@/providers/project-provider";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function ProjectNavigationTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const { project, connection, isLoading } = useProject();

  const tabs = [
    {
      label: "Overview",
      href: `/projects/${projectId}`,
      icon: LayoutDashboard,
      active: pathname === `/projects/${projectId}`,
    },
    {
      label: "Connection",
      href: `/projects/${projectId}/connection`,
      icon: Plug,
      active: pathname.startsWith(`/projects/${projectId}/connection`),
      badge: connection ? connection.dialect : "Not Connected",
      badgeVariant: connection ? ("success" as const) : ("secondary" as const),
    },
    {
      label: "Schema Explorer",
      href: `/projects/${projectId}/schema`,
      icon: TableProperties,
      active: pathname.startsWith(`/projects/${projectId}/schema`),
    },
    {
      label: "AI Chat Workspace",
      href: `/projects/${projectId}/chat`,
      icon: MessageSquare,
      active: pathname.startsWith(`/projects/${projectId}/chat`),
      highlight: true,
    },
  ];

  return (
    <div className="space-y-4">
      {/* Project Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div className="space-y-1">
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-7 w-48" />
              <Skeleton className="h-4 w-72" />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                  {project?.name || "Project"}
                </h1>
                {connection && (
                  <Badge variant="accent" className="uppercase text-[10px]">
                    {connection.dialect}
                  </Badge>
                )}
              </div>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-2xl leading-relaxed">
                {project?.description || "Database project workspace."}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-px overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex items-center gap-2 px-3.5 py-2.5 rounded-t-xl text-xs font-medium border-b-2 transition-all whitespace-nowrap",
                tab.active
                  ? "border-blue-500 text-blue-400 bg-blue-500/5 font-semibold"
                  : "border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
              {tab.badge && (
                <Badge variant={tab.badgeVariant} className="text-[10px] py-0 px-1.5 ml-1">
                  {tab.badge}
                </Badge>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function ProjectScopedLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}): React.JSX.Element {
  const resolvedParams = use(params);

  return (
    <ProjectProvider projectId={resolvedParams.projectId}>
      <div className="space-y-6">
        <ProjectNavigationTabs projectId={resolvedParams.projectId} />
        <div>{children}</div>
      </div>
    </ProjectProvider>
  );
}
