"use client";

import React from "react";
import {
  Bot,
  Code2,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
} from "lucide-react";
import type { StreamState } from "@/hooks/use-sse";
import { cn } from "@/lib/utils";

interface SSEStatusIndicatorProps {
  streamState: StreamState;
}

export function SSEStatusIndicator({
  streamState,
}: SSEStatusIndicatorProps): React.JSX.Element {
  const { currentStep, isStreaming, intentType, errorMessage, retryCount } =
    streamState;

  const steps = [
    {
      id: "intent_classified",
      label: "Intent Classification",
      desc: intentType ? `Intent: ${intentType}` : "Parsing entities & query intent",
      icon: Bot,
    },
    {
      id: "sql_generated",
      label: "SQL Synthesis",
      desc: "Linking pgvector schema & generating dialect SQL",
      icon: Code2,
    },
    {
      id: "sql_executed",
      label: "Guardrailed Execution",
      desc: retryCount && retryCount > 0
        ? `Auto-healing syntax error (Attempt ${retryCount + 1})...`
        : "AST verified read-only execution",
      icon: Play,
    },
    {
      id: "final_result",
      label: "Answer Synthesis",
      desc: "Formatting data results & AI summary",
      icon: CheckCircle2,
    },
  ];

  const getStepStatus = (stepId: string) => {
    if (currentStep === "error") return "error";

    const stepOrder = [
      "idle",
      "intent_classified",
      "sql_generated",
      "sql_executed",
      "result_formatted",
      "final_result",
    ];

    const currentIndex = stepOrder.indexOf(currentStep);
    const stepIndex = stepOrder.indexOf(stepId);

    if (currentStep === "final_result" || currentIndex > stepIndex) {
      return "completed";
    }
    if (currentIndex === stepIndex && isStreaming) {
      return "active";
    }
    return "pending";
  };

  return (
    <div className="p-3.5 rounded-xl border border-zinc-800/80 bg-zinc-950/60 my-2 space-y-2.5">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-zinc-400 flex items-center gap-1.5">
          {isStreaming ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-400" />
          ) : currentStep === "error" ? (
            <AlertCircle className="h-3.5 w-3.5 text-red-400" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          )}
          <span>
            {isStreaming
              ? "LangGraph Agent Executing..."
              : currentStep === "error"
              ? "Execution Failed"
              : "Agent Execution Complete"}
          </span>
        </span>

        {retryCount !== undefined && retryCount > 0 && (
          <span className="text-[11px] text-amber-400 flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Retry {retryCount}
          </span>
        )}
      </div>

      {/* Step Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
        {steps.map((step) => {
          const status = getStepStatus(step.id);
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={cn(
                "p-2.5 rounded-lg border transition-all text-left space-y-1",
                status === "completed" &&
                  "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
                status === "active" &&
                  "border-blue-500/50 bg-blue-500/10 text-blue-400 animate-pulse",
                status === "pending" &&
                  "border-zinc-800/60 bg-zinc-900/30 text-zinc-600",
                status === "error" &&
                  "border-red-500/30 bg-red-500/5 text-red-400"
              )}
            >
              <div className="flex items-center gap-1.5 font-semibold text-[11px]">
                {status === "active" ? (
                  <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
                ) : status === "completed" ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Icon className="h-3 w-3" />
                )}
                <span>{step.label}</span>
              </div>
              <p className="text-[10px] text-zinc-400 font-sans line-clamp-1">
                {step.desc}
              </p>
            </div>
          );
        })}
      </div>

      {errorMessage && (
        <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-mono text-red-300">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
