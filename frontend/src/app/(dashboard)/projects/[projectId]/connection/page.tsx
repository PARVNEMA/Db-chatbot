"use client";

import React from "react";
import { useProject } from "@/providers/project-provider";
import { ConnectionStatus } from "@/components/connections/connection-status";
import { ConnectionForm } from "@/components/connections/connection-form";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectConnectionPage(): React.JSX.Element {
  const { projectId, connection, isLoading, refreshAll } = useProject();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Live Status Header */}
      <ConnectionStatus
        projectId={projectId}
        connection={connection}
        onTested={refreshAll}
      />

      {/* Connection Configuration Form */}
      <ConnectionForm
        projectId={projectId}
        connection={connection}
        onSaved={refreshAll}
        onDeleted={refreshAll}
      />
    </div>
  );
}
