"use client";

import React from "react";
import Link from "next/link";
import {
  Plug,
  TableProperties,
  MessageSquare,
  ArrowRight,
  Sparkles,
  Layers,
} from "lucide-react";
import { useProject } from "@/providers/project-provider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectOverviewPage(): React.JSX.Element {
  const { project, connection, schemaOverview, isLoading, projectId } =
    useProject();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <Skeleton className="h-36 rounded-2xl" />
          <Skeleton className="h-36 rounded-2xl" />
          <Skeleton className="h-36 rounded-2xl" />
        </div>
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }

  const hasConnection = !!connection;
  const tables = schemaOverview?.tables || [];
  const tablesCount =
    schemaOverview?.table_count ??
    schemaOverview?.tables_count ??
    tables.length;

  const columnsCount =
    schemaOverview?.column_count ??
    schemaOverview?.columns_count ??
    tables.reduce(
      (acc, t) => acc + (t.column_count ?? t.columns_count ?? 0),
      0
    );

  const hasSchema = tablesCount > 0;

  return (
    <div className="space-y-8">
      {/* Top Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Connection Status */}
        <Card className="border-zinc-800/80 bg-zinc-900/50">
          <CardHeader className="p-5 pb-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-zinc-400">Database Engine</span>
              <Badge
                variant={hasConnection ? "success" : "secondary"}
                className="text-[10px]"
              >
                {hasConnection ? "Connected" : "Disconnected"}
              </Badge>
            </div>
            <CardTitle className="text-xl font-bold text-white pt-2">
              {hasConnection ? connection.name : "No Connection"}
            </CardTitle>
            <CardDescription className="text-xs font-mono">
              {hasConnection ? `Dialect: ${connection.dialect.toUpperCase()}` : "Target database not linked"}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <Link href={`/projects/${projectId}/connection`}>
              <Button
                variant="outline"
                size="sm"
                className="w-full mt-2 text-xs border-zinc-800 hover:bg-zinc-800 hover:text-white"
              >
                <Plug className="mr-1.5 h-3.5 w-3.5 text-blue-400" />
                {hasConnection ? "Manage Connection" : "Set Up Connection"}
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Schema Status */}
        <Card className="border-zinc-800/80 bg-zinc-900/50">
          <CardHeader className="p-5 pb-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-zinc-400">Introspected Schema</span>
              <Badge
                variant={hasSchema ? "accent" : "secondary"}
                className="text-[10px]"
              >
                {hasSchema ? `${tablesCount} Tables` : "Not Scanned"}
              </Badge>
            </div>
            <CardTitle className="text-xl font-bold text-white pt-2">
              {hasSchema ? `${columnsCount} Columns` : "Schema Empty"}
            </CardTitle>
            <CardDescription className="text-xs font-mono">
              {hasSchema
                ? `Last sync: ${new Date(schemaOverview?.introspected_at || "").toLocaleDateString()}`
                : "Run introspection to reflect tables"}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <Link href={`/projects/${projectId}/schema`}>
              <Button
                variant="outline"
                size="sm"
                className="w-full mt-2 text-xs border-zinc-800 hover:bg-zinc-800 hover:text-white"
              >
                <TableProperties className="mr-1.5 h-3.5 w-3.5 text-emerald-400" />
                {hasSchema ? "Explore Tables" : "Scan Schema"}
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* AI Agent Status */}
        <Card className="border-zinc-800/80 bg-zinc-900/50">
          <CardHeader className="p-5 pb-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-zinc-400">NL Agent Pipeline</span>
              <Badge variant="default" className="text-[10px] bg-blue-600">
                Ready
              </Badge>
            </div>
            <CardTitle className="text-xl font-bold text-white pt-2">
              LangGraph NL-to-SQL
            </CardTitle>
            <CardDescription className="text-xs font-mono">
              Self-correction & 3-layer guardrails
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <Link href={`/projects/${projectId}/chat`}>
              <Button
                size="sm"
                className="w-full mt-2 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium"
              >
                <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
                Open AI Chat
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Quick Launchpad Action Cards */}
      <div className="space-y-4">
        <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-400" />
          Workspace Launchpad
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <Link
            href={`/projects/${projectId}/chat`}
            className="group p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800 hover:border-blue-500/50 hover:bg-zinc-900/80 transition-all duration-200 shadow-md space-y-3"
          >
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center group-hover:scale-105 transition-transform">
              <MessageSquare className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base group-hover:text-blue-400 transition-colors flex items-center justify-between">
                Ask Questions in Natural Language
                <ArrowRight className="h-4 w-4 text-zinc-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
              </h3>
              <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                Start a multi-turn chat session to convert questions into dialect-safe SQL with live SSE event streaming.
              </p>
            </div>
          </Link>

          <Link
            href={`/projects/${projectId}/schema`}
            className="group p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800 hover:border-emerald-500/50 hover:bg-zinc-900/80 transition-all duration-200 shadow-md space-y-3"
          >
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center group-hover:scale-105 transition-transform">
              <TableProperties className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base group-hover:text-emerald-400 transition-colors flex items-center justify-between">
                Schema Explorer & Annotations
                <ArrowRight className="h-4 w-4 text-zinc-500 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
              </h3>
              <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                Browse introspected tables, inspect data types, add semantic notes, and test pgvector similarity search.
              </p>
            </div>
          </Link>

          <Link
            href={`/projects/${projectId}/connection`}
            className="group p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800 hover:border-indigo-500/50 hover:bg-zinc-900/80 transition-all duration-200 shadow-md space-y-3"
          >
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Plug className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base group-hover:text-indigo-400 transition-colors flex items-center justify-between">
                Database Credentials & Security
                <ArrowRight className="h-4 w-4 text-zinc-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
              </h3>
              <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                Manage Fernet encrypted database connection strings, test network latency, and configure pooling.
              </p>
            </div>
          </Link>
        </div>
      </div>

      {/* Project Metadata Card */}
      <Card className="border-zinc-800/80 bg-zinc-900/30">
        <CardHeader className="p-5 pb-3">
          <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
            <Layers className="h-4 w-4 text-zinc-400" />
            Project Details
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 pt-0 space-y-3 text-xs font-mono">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800">
              <span className="text-zinc-500">Project UUID</span>
              <p className="text-zinc-200 truncate mt-0.5">{project?.id}</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800">
              <span className="text-zinc-500">Created At</span>
              <p className="text-zinc-200 mt-0.5">
                {project ? new Date(project.created_at).toLocaleString() : "—"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
