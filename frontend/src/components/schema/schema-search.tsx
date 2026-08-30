"use client";

import React, { useState } from "react";
import {
  Search,
  Sparkles,
  Loader2,
  TableProperties,
  Key,
  Link as LinkIcon,
  Percent,
} from "lucide-react";
import { embeddingsApi } from "@/lib/api/embeddings";
import type { SchemaSearchResult } from "@/types/embedding";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { toast } from "sonner";

interface SchemaSearchProps {
  projectId: string;
}

export function SchemaSearch({ projectId }: SchemaSearchProps): React.JSX.Element {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<SchemaSearchResult[]>([]);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearched(true);
    try {
      const res = await embeddingsApi.search(projectId, {
        query: query.trim(),
        top_k: 6,
      });

      if (res.success && res.data) {
        setResults(res.data);
      } else {
        setResults([]);
        toast.info("No matching schema elements found");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Schema search failed";
      toast.error(msg);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const sampleQueries = [
    "customer order revenue",
    "payment amount and date",
    "product inventory stock",
    "user account email and status",
  ];

  return (
    <Card className="border-zinc-800/80 bg-zinc-900/40 shadow-lg">
      <CardHeader className="p-6 pb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-lg">
              pgvector Schema Similarity Search
            </CardTitle>
            <CardDescription className="text-xs">
              Test real-time 384-dimensional vector retrieval used by the Intent Node during NL query generation.
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 pt-0 space-y-5">
        {/* Search Form */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
            <Input
              placeholder="Ask a concept: e.g. 'total customer spending', 'invoice due date'..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9 bg-zinc-900 border-zinc-700 text-sm"
              disabled={isSearching}
            />
          </div>
          <Button
            type="submit"
            disabled={isSearching || !query.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-5 shadow-md shadow-indigo-600/20"
          >
            {isSearching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              "Search Schema"
            )}
          </Button>
        </form>

        {/* Preset Query Chips */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
          <span className="text-[11px] font-mono mr-1">Suggestions:</span>
          {sampleQueries.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => {
                setQuery(sample);
              }}
              className="px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-colors text-[11px] font-mono"
            >
              {sample}
            </button>
          ))}
        </div>

        {/* Results Stream / Grid */}
        {isSearching ? (
          <div className="py-8 flex flex-col items-center justify-center gap-2 text-zinc-500">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
            <span className="text-xs font-mono">
              Computing cosine distance in pgvector...
            </span>
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3 pt-2">
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-400 flex items-center justify-between">
              <span>Top {results.length} Ranked Matches</span>
              <span className="text-[11px] text-zinc-500">
                BAAI/bge-small-en-v1.5 (384 dims)
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {results.map((result) => {
                const scorePercent = Math.round(
                  Math.max(0, Math.min(100, result.similarity_score * 100))
                );

                return (
                  <div
                    key={result.column_id}
                    className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/70 space-y-2 hover:border-indigo-500/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-zinc-100">
                          <TableProperties className="h-3.5 w-3.5 text-indigo-400" />
                          <span>
                            {result.schema_name ? `${result.schema_name}.` : ""}
                            {result.table_name}.{result.column_name}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono text-zinc-500">
                          Type: {result.data_type}
                        </span>
                      </div>

                      <Badge
                        variant="accent"
                        className="font-mono text-[10px] py-0.5 px-2 shrink-0 gap-1 bg-indigo-500/15 text-indigo-300 border-indigo-500/30"
                      >
                        <Percent className="h-2.5 w-2.5" />
                        {scorePercent}% match
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1.5 pt-1">
                      {result.is_primary_key && (
                        <Badge
                          variant="default"
                          className="bg-amber-500/15 text-amber-300 border-amber-500/30 text-[9px] py-0"
                        >
                          <Key className="h-2 w-2 mr-1" />
                          PK
                        </Badge>
                      )}
                      {result.is_foreign_key && (
                        <Badge
                          variant="secondary"
                          className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-[9px] py-0"
                        >
                          <LinkIcon className="h-2 w-2 mr-1" />
                          FK → {result.fk_target_table}
                        </Badge>
                      )}
                    </div>

                    {result.embed_text && (
                      <p className="text-[11px] text-zinc-400 line-clamp-2 bg-zinc-900/60 p-2 rounded border border-zinc-850 font-mono">
                        {result.embed_text}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          searched && (
            <div className="py-8 text-center text-xs text-zinc-500 font-mono">
              No matching columns found. Ensure you have introspected the database.
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}
