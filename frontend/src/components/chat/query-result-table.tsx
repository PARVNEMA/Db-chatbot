"use client";

import React, { useState } from "react";
import { TableProperties, Download, ChevronDown, ChevronRight, Check } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface QueryResultTableProps {
  rows: Record<string, unknown>[];
  rowCount?: number;
  defaultExpanded?: boolean;
}

export function QueryResultTable({
  rows,
  rowCount,
  defaultExpanded = true,
}: QueryResultTableProps): React.JSX.Element {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [downloaded, setDownloaded] = useState(false);

  if (!rows || rows.length === 0) {
    return (
      <div className="p-3 rounded-xl border border-zinc-800/80 bg-zinc-950/60 text-xs font-mono text-zinc-500 my-2">
        0 rows returned by database.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);
  const totalRows = rowCount ?? rows.length;

  const exportCsv = () => {
    const header = columns.join(",");
    const csvRows = rows.map((row) =>
      columns
        .map((col) => {
          const val = row[col];
          if (val === null || val === undefined) return "";
          const str = String(val);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    );

    const csvContent = "data:text/csv;charset=utf-8," + [header, ...csvRows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `query_results_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloaded(true);
    setTimeout(() => setDownloaded(false), 2000);
  };

  return (
    <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/80 overflow-hidden shadow-md my-2">
      {/* Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="px-3.5 py-2 bg-zinc-900/80 border-b border-zinc-800/80 flex items-center justify-between cursor-pointer hover:bg-zinc-900 transition select-none"
      >
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-300">
          <span className="text-zinc-500">
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
            )}
          </span>
          <TableProperties className="h-3.5 w-3.5 text-emerald-400" />
          <span>Execution Results</span>
          <Badge
            variant="success"
            className="text-[9px] py-0 px-1 font-mono"
          >
            {totalRows} {totalRows === 1 ? "row" : "rows"}
          </Badge>
        </div>

        <Button
          size="xs"
          variant="ghost"
          onClick={(e) => {
            e.stopPropagation();
            exportCsv();
          }}
          className="text-zinc-400 hover:text-white h-6 text-[11px] gap-1"
          title="Export as CSV"
        >
          {downloaded ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Exported</span>
            </>
          ) : (
            <>
              <Download className="h-3 w-3" />
              <span>Export CSV</span>
            </>
          )}
        </Button>
      </div>

      {/* Table Content */}
      {expanded && (
        <div className="max-h-72 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-zinc-800 bg-zinc-900/60 sticky top-0 z-10">
                {columns.map((col) => (
                  <TableHead
                    key={col}
                    className="font-mono text-[11px] text-zinc-300 whitespace-nowrap bg-zinc-900/90"
                  >
                    {col}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, rowIdx) => (
                <TableRow
                  key={rowIdx}
                  className="hover:bg-zinc-900/50 border-zinc-800/40"
                >
                  {columns.map((col) => {
                    const val = row[col];
                    const isNull = val === null || val === undefined;
                    return (
                      <TableCell
                        key={col}
                        className="font-mono text-xs text-zinc-200 whitespace-nowrap p-3"
                      >
                        {isNull ? (
                          <span className="text-zinc-600 italic">null</span>
                        ) : typeof val === "object" ? (
                          JSON.stringify(val)
                        ) : (
                          String(val)
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
