"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  TableProperties,
  ChevronDown,
  ChevronRight,
  Search,
  RefreshCw,
  Sparkles,
  Loader2,
} from "lucide-react";
import type { TableDetailResponse } from "@/types/schema";
import type { Annotation } from "@/types/annotation";
import { schemaApi } from "@/lib/api/schema";
import { annotationsApi } from "@/lib/api/annotations";
import { embeddingsApi } from "@/lib/api/embeddings";
import { ColumnTable } from "./column-table";
import { AnnotationEditor } from "./annotation-editor";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { toast } from "sonner";

interface TableListProps {
  projectId: string;
  onRefreshNeeded?: () => void;
}

export function TableList({
  projectId,
}: TableListProps): React.JSX.Element {
  const [tables, setTables] = useState<TableDetailResponse[]>([]);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [suggestingTableId, setSuggestingTableId] = useState<string | null>(null);

  const handleAutoSuggestTable = async (tableId: string, tableName: string) => {
    setSuggestingTableId(tableId);
    try {
      const res = await embeddingsApi.autoSuggest(projectId, tableId);
      if (res.success && res.data) {
        toast.success(
          `Generated description for table "${tableName}" and ${res.data.suggested_columns_count} columns!`
        );
        await fetchData();
      } else {
        throw new Error(res.message || "Auto-suggest failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Auto-suggest failed";
      toast.error(msg);
    } finally {
      setSuggestingTableId(null);
    }
  };

  const fetchData = useCallback(async () => {
    try {
      const [tablesRes, annotRes] = await Promise.allSettled([
        schemaApi.listTables(projectId),
        annotationsApi.list(projectId),
      ]);

      if (tablesRes.status === "fulfilled" && tablesRes.value.success && tablesRes.value.data) {
        setTables(tablesRes.value.data);
        // Expand first 2 tables by default
        const initial = new Set<string>();
        tablesRes.value.data.slice(0, 2).forEach((t) => initial.add(t.table_name));
        setExpandedTables(initial);
      } else {
        setTables([]);
      }

      if (annotRes.status === "fulfilled" && annotRes.value.success && annotRes.value.data) {
        setAnnotations(annotRes.value.data);
      } else {
        setAnnotations([]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load tables";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([
      schemaApi.listTables(projectId),
      annotationsApi.list(projectId),
    ]).then(([tablesRes, annotRes]) => {
      if (!isMounted) return;

      if (tablesRes.status === "fulfilled" && tablesRes.value.success && tablesRes.value.data) {
        setTables(tablesRes.value.data);
        const initial = new Set<string>();
        tablesRes.value.data.slice(0, 2).forEach((t) => initial.add(t.table_name));
        setExpandedTables(initial);
      }

      if (annotRes.status === "fulfilled" && annotRes.value.success && annotRes.value.data) {
        setAnnotations(annotRes.value.data);
      }

      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [projectId]);

  const toggleTable = (tableName: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) {
        next.delete(tableName);
      } else {
        next.add(tableName);
      }
      return next;
    });
  };

  const expandAll = () => {
    const all = new Set(tables.map((t) => t.table_name));
    setExpandedTables(all);
  };

  const collapseAll = () => {
    setExpandedTables(new Set());
  };

  const filteredTables = tables.filter((t) => {
    const q = search.toLowerCase();
    return (
      t.table_name.toLowerCase().includes(q) ||
      (t.schema_name && t.schema_name.toLowerCase().includes(q)) ||
      t.columns.some((c) => c.column_name.toLowerCase().includes(q))
    );
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (tables.length === 0) {
    return (
      <EmptyState
        icon={TableProperties}
        title="No Tables Introspected"
        description="Database introspection has not been executed yet. Click 'Scan Target Database' above to reflect all tables, columns, and foreign keys."
      />
    );
  }

  // Create table annotation map
  const tableAnnotationMap = new Map<string, Annotation>();
  annotations.forEach((ann) => {
    if (ann.schema_table_id) {
      tableAnnotationMap.set(ann.schema_table_id, ann);
    }
  });

  return (
    <div className="space-y-4">
      {/* Search & Collapse Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <Input
            placeholder="Search tables or columns..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-zinc-900/60 border-zinc-800"
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="xs"
            onClick={expandAll}
            className="text-zinc-400 hover:text-white text-xs"
          >
            Expand All
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={collapseAll}
            className="text-zinc-400 hover:text-white text-xs"
          >
            Collapse All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void fetchData()}
            className="border-zinc-800 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Tables Accordion List */}
      <div className="space-y-3">
        {filteredTables.map((table) => {
          const isExpanded = expandedTables.has(table.table_name);
          const tableAnnotation = tableAnnotationMap.get(table.id);

          return (
            <div
              key={table.id}
              className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 overflow-hidden shadow-sm transition-colors hover:border-zinc-700/70"
            >
              {/* Table Header Bar */}
              <div
                onClick={() => toggleTable(table.table_name)}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer bg-zinc-900/60 hover:bg-zinc-900/90 transition select-none"
              >
                <div className="flex items-center gap-3">
                  <div className="text-zinc-500 hover:text-zinc-200 transition">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-blue-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <TableProperties className="h-4 w-4 text-blue-400" />
                    <span className="font-semibold text-sm text-zinc-100 font-mono">
                      {table.schema_name ? `${table.schema_name}.` : ""}
                      {table.table_name}
                    </span>
                    <Badge variant="secondary" className="text-[10px] py-0 font-mono">
                      {table.columns.length} columns
                    </Badge>
                  </div>
                </div>

                {/* Table Level Actions & Annotation Editor (prevent parent accordion toggle) */}
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-2.5 sm:max-w-xl text-left"
                >
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => void handleAutoSuggestTable(table.id, table.table_name)}
                    disabled={suggestingTableId === table.id}
                    className="border-zinc-700 bg-zinc-900/90 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs gap-1.5 shrink-0"
                    title="Auto-generate AI descriptions for this table and its columns"
                  >
                    {suggestingTableId === table.id ? (
                      <Loader2 className="h-3 w-3 animate-spin text-indigo-400" />
                    ) : (
                      <Sparkles className="h-3 w-3 text-indigo-400" />
                    )}
                    {suggestingTableId === table.id ? "Suggesting..." : "Auto-Suggest"}
                  </Button>

                  <div className="flex-1 min-w-[200px]">
                    <AnnotationEditor
                      projectId={projectId}
                      targetType="table"
                      schemaTableId={table.id}
                      initialAnnotation={tableAnnotation}
                      onSaved={fetchData}
                    />
                  </div>
                </div>
              </div>

              {/* Expanded Columns Table */}
              {isExpanded && (
                <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/40 animate-in fade-in-0 duration-150">
                  <ColumnTable
                    projectId={projectId}
                    columns={table.columns}
                    annotations={annotations}
                    onAnnotationUpdated={fetchData}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
