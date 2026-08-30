"use client";

import React, { useState } from "react";
import {
  Plug,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  RefreshCw,
  Server,
} from "lucide-react";
import type { Connection } from "@/types/connection";
import { connectionsApi } from "@/lib/api/connections";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";

interface ConnectionStatusProps {
  projectId: string;
  connection: Connection | null;
  onTested?: () => void;
}

export function ConnectionStatus({
  projectId,
  connection,
  onTested,
}: ConnectionStatusProps): React.JSX.Element {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    latency_ms: number | null;
  } | null>(null);

  const handleTest = async () => {
    if (!connection) return;
    setTesting(true);
    try {
      const res = await connectionsApi.test(projectId);
      if (res.success && res.data) {
        setTestResult(res.data);
        if (res.data.success) {
          toast.success(
            `Connection verified! Response time: ${res.data.latency_ms ?? 0}ms`
          );
        } else {
          toast.error(res.data.message || "Connection failed");
        }
        onTested?.();
      } else {
        throw new Error(res.message || "Test failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setTestResult({
        success: false,
        message: msg,
        latency_ms: null,
      });
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  };

  if (!connection) {
    return (
      <Card className="border-zinc-800/80 bg-zinc-900/40">
        <CardContent className="p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-zinc-800 text-zinc-400 flex items-center justify-center ring-1 ring-zinc-700">
              <Plug className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-sm text-zinc-200">
                  No Database Connected
                </h3>
                <Badge variant="secondary">Disconnected</Badge>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Configure connection credentials below to begin introspecting schema and querying.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-zinc-800/80 bg-zinc-900/50 shadow-md">
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Left Info */}
          <div className="flex items-center gap-3.5">
            <div className="h-11 w-11 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center shrink-0">
              <Server className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-base text-zinc-100">
                  {connection.name}
                </h3>
                <Badge variant="success" className="gap-1 uppercase text-[10px]">
                  <CheckCircle2 className="h-3 w-3" />
                  {connection.dialect}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400 mt-1 font-mono">
                <span className="flex items-center gap-1 text-emerald-400">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Fernet Encrypted At Rest
                </span>
                {testResult?.latency_ms !== undefined && testResult.latency_ms !== null && (
                  <span className="flex items-center gap-1 text-blue-400">
                    <Clock className="h-3.5 w-3.5" />
                    {testResult.latency_ms}ms latency
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Right Action */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testing}
            className="border-zinc-700 bg-zinc-900 hover:bg-zinc-800 hover:text-white shrink-0 text-xs"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1.5 ${testing ? "animate-spin" : ""}`}
            />
            {testing ? "Testing..." : "Test Connection"}
          </Button>
        </div>

        {/* Test Result Banner if present */}
        {testResult && (
          <div
            className={`p-3 rounded-xl text-xs flex items-center gap-2.5 font-mono ${
              testResult.success
                ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
                : "bg-red-500/10 border border-red-500/20 text-red-300"
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0 text-red-400" />
            )}
            <span className="truncate">{testResult.message}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
