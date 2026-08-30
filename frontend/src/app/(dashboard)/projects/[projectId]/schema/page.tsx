"use client";

import React from "react";
import { useProject } from "@/providers/project-provider";
import { SchemaOverview } from "@/components/schema/schema-overview";
import { TableList } from "@/components/schema/table-list";
import { SchemaSearch } from "@/components/schema/schema-search";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TableProperties, Sparkles, AlertCircle, Plug } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ProjectSchemaPage(): React.JSX.Element {
  const { projectId, connection, schemaOverview, isLoading, refreshAll } =
    useProject();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-10 w-64 rounded-xl" />
        <div className="space-y-3">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!connection) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Database Connection Required"
        description="You must configure and test your target database connection credentials before introspecting tables and columns."
        action={
          <Link href={`/projects/${projectId}/connection`}>
            <Button className="bg-blue-600 hover:bg-blue-500 text-white text-xs gap-1.5">
              <Plug className="h-3.5 w-3.5" />
              Configure Connection
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview & Scan Controls Header */}
      <SchemaOverview
        projectId={projectId}
        schemaOverview={schemaOverview}
        onIntrospected={refreshAll}
      />

      {/* Tabs for Schema Tree vs Vector Search */}
      <Tabs defaultValue="tables" className="space-y-6">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="tables" className="gap-2">
              <TableProperties className="h-3.5 w-3.5" />
              <span>Tables & Columns</span>
            </TabsTrigger>
            <TabsTrigger value="search" className="gap-2">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span>Vector Similarity Search</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab 1: Browsable Tables & Columns */}
        <TabsContent value="tables">
          <TableList projectId={projectId} onRefreshNeeded={refreshAll} />
        </TabsContent>

        {/* Tab 2: Vector Search */}
        <TabsContent value="search">
          <SchemaSearch projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
