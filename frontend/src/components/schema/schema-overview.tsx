"use client";

import React, { useState } from "react";
import {
  TableProperties,
  Sparkles,
  RefreshCw,
  Layers,
  Calendar,
  Loader2,
} from "lucide-react";
import { schemaApi } from "@/lib/api/schema";
import { embeddingsApi } from "@/lib/api/embeddings";
import type { SchemaOverviewResponse } from "@/types/schema";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmbeddingGeneratorDialog } from "./embedding-generator-dialog";
import { toast } from "sonner";

interface SchemaOverviewProps {
  projectId: string;
  schemaOverview: SchemaOverviewResponse | null;
  onIntrospected?: () => void;
}

export function SchemaOverview({
  projectId,
  schemaOverview,
  onIntrospected,
}: SchemaOverviewProps): React.JSX.Element {
  const [isIntrospecting, setIsIntrospecting] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);

  const handleIntrospect = async () => {
    setIsIntrospecting(true);
    try {
      const res = await schemaApi.introspect(projectId);
      if (res.success && res.data) {
        toast.success(
          `Introspected ${res.data.tables_count} tables & ${res.data.columns_count} columns. Embeddings synced!`
        );
        onIntrospected?.();
      } else {
        throw new Error(res.message || "Introspection failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Introspection failed";
      toast.error(msg);
    } finally {
      setIsIntrospecting(false);
    }
  };

  // const handleAutoSuggest = async () => {
  //   if (tables.length === 0) {
  //     toast.error(
  //       "Please click 'Scan Target DB' first so the AI has introspected tables and columns to describe."
  //     );
  //     return;
  //   }

  //   setIsSuggesting(true);
  //   try {
  //     let totalCols = 0;
  //     let totalTables = 0;
  //     for (const t of tables) {
  //       const res = await embeddingsApi.autoSuggest(projectId, t.id);
  //       if (res.success && res.data) {
  //         totalTables += res.data.suggested_tables_count;
  //         totalCols += res.data.suggested_columns_count;
  //       }
  //     }
  //     toast.success(
  //       `Generated ${totalTables} table and ${totalCols} column descriptions with AI!`
  //     );
  //     onIntrospected?.();
  //   } catch (err) {
  //     const msg = err instanceof Error ? err.message : "Auto-suggest failed";
  //     toast.error(msg);
  //   } finally {
  //     setIsSuggesting(false);
  //   }
  // };

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

  const formattedDate = schemaOverview?.introspected_at
    ? new Date(schemaOverview.introspected_at).toLocaleString()
    : "Never introspected";

  return (
    <Card className="border-zinc-800/80 bg-zinc-900/40 shadow-lg">
      <CardContent className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* Metrics summary */}
          <div className="flex flex-wrap items-center gap-6 sm:gap-8">
            <div className="flex items-center gap-3.5">
              <div className="h-11 w-11 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center shrink-0">
                <TableProperties className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-white font-mono leading-none">
                  {tablesCount}
                </div>
                <div className="text-xs text-zinc-400 mt-1">Database Tables</div>
              </div>
            </div>

            <div className="h-8 w-px bg-zinc-800 hidden sm:block" />

            <div className="flex items-center gap-3.5">
              <div className="h-11 w-11 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center shrink-0">
                <Layers className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-emerald-400 font-mono leading-none">
                  {columnsCount}
                </div>
                <div className="text-xs text-zinc-400 mt-1">Introspected Columns</div>
              </div>
            </div>

            <div className="h-8 w-px bg-zinc-800 hidden sm:block" />

            <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono">
              <Calendar className="h-3.5 w-3.5 text-zinc-400" />
              <span>Last sync: {formattedDate}</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Generate Vector Embeddings Dialog Button */}
            <EmbeddingGeneratorDialog
              projectId={projectId}
              onCompleted={onIntrospected}
            />

            {/* AI Auto-Suggest Descriptions Button */}
            {/* <Button
              variant="outline"
              size="sm"
              onClick={handleAutoSuggest}
              disabled={isSuggesting || isIntrospecting}
              className="border-zinc-700 bg-zinc-900 hover:bg-zinc-800 hover:text-white text-xs gap-1.5"
            >
              {isSuggesting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              )}
              {isSuggesting ? "Generating..." : "AI Auto-Suggest"}
            </Button> */}

            {/* Introspect Database Button */}
            <Button
              size="sm"
              onClick={handleIntrospect}
              disabled={isIntrospecting || isSuggesting}
              className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium gap-1.5 shadow-md shadow-blue-600/20"
            >
              {isIntrospecting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              {isIntrospecting ? "Introspecting..." : "Scan Target DB"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
