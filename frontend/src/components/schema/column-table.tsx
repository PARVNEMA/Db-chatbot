"use client";

import React from "react";
import { Key, Link as LinkIcon } from "lucide-react";
import type { ColumnDetail } from "@/types/schema";
import type { Annotation } from "@/types/annotation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AnnotationEditor } from "./annotation-editor";

interface ColumnTableProps {
  projectId: string;
  columns: ColumnDetail[];
  annotations?: Annotation[];
  onAnnotationUpdated?: () => void;
}

export function ColumnTable({
  projectId,
  columns,
  annotations = [],
  onAnnotationUpdated,
}: ColumnTableProps): React.JSX.Element {
  // Map column id to its annotation
  const annotationMap = new Map<string, Annotation>();
  annotations.forEach((ann) => {
    if (ann.schema_column_id) {
      annotationMap.set(ann.schema_column_id, ann);
    }
  });

  return (
    <div className="rounded-xl border border-zinc-800/80 overflow-hidden bg-zinc-950/60">
      <Table>
        <TableHeader>
          <TableRow className="border-b border-zinc-800/80 bg-zinc-900/80">
            <TableHead className="w-[200px]">Column Name</TableHead>
            <TableHead className="w-[140px]">Data Type</TableHead>
            <TableHead className="w-[180px]">Constraints & Keys</TableHead>
            <TableHead>Semantic Description (pgvector context)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {columns.map((col) => {
            const annotation = annotationMap.get(col.id);

            return (
              <TableRow
                key={col.id}
                className="hover:bg-zinc-900/50 transition-colors border-zinc-800/50"
              >
                {/* Column Name */}
                <TableCell className="font-mono text-xs font-semibold text-zinc-100">
                  {col.column_name}
                </TableCell>

                {/* Data Type */}
                <TableCell className="font-mono text-[11px] text-zinc-400">
                  <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800">
                    {col.data_type}
                  </span>
                </TableCell>

                {/* Constraints & Keys */}
                <TableCell>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {col.is_primary_key && (
                      <Badge
                        variant="default"
                        className="bg-amber-500/15 text-amber-300 border-amber-500/30 gap-1 text-[10px] py-0"
                      >
                        <Key className="h-2.5 w-2.5" />
                        PK
                      </Badge>
                    )}
                    {col.is_foreign_key && (
                      <Badge
                        variant="secondary"
                        className="bg-blue-500/10 text-blue-400 border-blue-500/20 gap-1 text-[10px] py-0"
                        title={
                          col.fk_target_table
                            ? `References ${col.fk_target_table}.${col.fk_target_column}`
                            : "Foreign Key"
                        }
                      >
                        <LinkIcon className="h-2.5 w-2.5" />
                        FK {col.fk_target_table ? `→ ${col.fk_target_table}` : ""}
                      </Badge>
                    )}
                    {!col.is_nullable && !col.is_primary_key && (
                      <span className="text-[10px] font-mono text-zinc-500">
                        NOT NULL
                      </span>
                    )}
                  </div>
                </TableCell>

                {/* Semantic Description */}
                <TableCell>
                  <AnnotationEditor
                    projectId={projectId}
                    targetType="column"
                    schemaColumnId={col.id}
                    initialAnnotation={annotation}
                    onSaved={onAnnotationUpdated}
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
