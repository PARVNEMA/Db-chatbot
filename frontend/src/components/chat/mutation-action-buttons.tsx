"use client";

import React, { useState } from "react";
import {
  CheckCircle2,
  XCircle,
  RotateCcw,
  Loader2,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface MutationActionButtonsProps {
  mutationId: string;
  status: string;
  isOwner: boolean;
  isExpired?: boolean;
  onApprove: () => void;
  onReject: (reason?: string) => void;
  onUndo?: (reason?: string) => void;
  disabled?: boolean;
}

export function MutationActionButtons({
  mutationId,
  status,
  isOwner,
  isExpired = false,
  onApprove,
  onReject,
  onUndo,
  disabled = false,
}: MutationActionButtonsProps): React.JSX.Element {
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [undoing, setUndoing] = useState(false);
  const [undoReason, setUndoReason] = useState("");

  const isPending = status === "PENDING_APPROVAL";
  const isExecuted = status === "EXECUTED";
  const isExecuting = status === "EXECUTING";

  if (!isPending && !isExecuted && !isExecuting) {
    return <></>;
  }

  return (
    <div className="my-2 p-3 rounded-xl border border-zinc-800 bg-zinc-950/60 shadow-md space-y-3 font-sans">
      {!isOwner && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-400" />
          <span>
            <strong>Read-Only Mode:</strong> Only the Project Owner can approve, reject, or revert database write operations.
          </span>
        </div>
      )}

      {/* PENDING APPROVAL CONTROLS */}
      {isPending && !rejecting && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <HelpCircle className="h-3.5 w-3.5 text-blue-400" />
            <span>Review proposed changes above before proceeding.</span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRejecting(true)}
              disabled={disabled || !isOwner || isExpired}
              className="h-8 px-3 border-zinc-700 text-zinc-300 hover:text-red-400 hover:bg-red-500/10 text-xs gap-1.5"
            >
              <XCircle className="h-3.5 w-3.5" />
              <span>Reject</span>
            </Button>

            <Button
              type="button"
              size="sm"
              onClick={onApprove}
              disabled={disabled || !isOwner || isExpired}
              className="h-8 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs gap-1.5 shadow-md shadow-emerald-600/20 disabled:opacity-40"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{isExpired ? "Expired" : "Approve & Execute"}</span>
            </Button>
          </div>
        </div>
      )}

      {/* REJECT WITH REASON FORM */}
      {isPending && rejecting && (
        <div className="space-y-2 animate-in fade-in-0 duration-150">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-red-300">Reject Mutation Proposal</span>
            <button
              type="button"
              onClick={() => setRejecting(false)}
              className="text-zinc-500 hover:text-zinc-300 text-[11px]"
            >
              Cancel
            </button>
          </div>
          <div className="flex gap-2">
            <Input
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection (optional)..."
              className="h-8 text-xs bg-zinc-900 border-zinc-800"
            />
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={() => {
                onReject(rejectReason || undefined);
                setRejecting(false);
              }}
              className="h-8 px-3 text-xs shrink-0"
            >
              Confirm Reject
            </Button>
          </div>
        </div>
      )}

      {/* EXECUTING STATE */}
      {isExecuting && (
        <div className="flex items-center gap-2 text-xs text-purple-300">
          <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
          <span>Acquiring target connection engine, row locks, and executing atomic transaction...</span>
        </div>
      )}

      {/* EXECUTED STATE WITH SOFT-UNDO ACTION */}
      {isExecuted && onUndo && !undoing && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-emerald-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>Transaction committed and audit snapshot recorded.</span>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setUndoing(true)}
            disabled={disabled || !isOwner}
            className="h-8 px-3 border-amber-500/30 text-amber-300 hover:bg-amber-500/10 text-xs gap-1.5"
            title="Revert inserted rows and restore patched rows to pre-update snapshot"
          >
            <RotateCcw className="h-3.5 w-3.5 text-amber-400" />
            <span>Soft-Undo Transaction</span>
          </Button>
        </div>
      )}

      {/* UNDO CONFIRMATION FORM */}
      {isExecuted && onUndo && undoing && (
        <div className="space-y-2 animate-in fade-in-0 duration-150">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-amber-300">Revert Executed Mutation (Soft-Undo)</span>
            <button
              type="button"
              onClick={() => setUndoing(false)}
              className="text-zinc-500 hover:text-zinc-300 text-[11px]"
            >
              Cancel
            </button>
          </div>
          <div className="flex gap-2">
            <Input
              value={undoReason}
              onChange={(e) => setUndoReason(e.target.value)}
              placeholder="Reason for reverting transaction (optional)..."
              className="h-8 text-xs bg-zinc-900 border-zinc-800"
            />
            <Button
              type="button"
              size="sm"
              onClick={() => {
                onUndo(undoReason || undefined);
                setUndoing(false);
              }}
              className="h-8 px-3 bg-amber-600 hover:bg-amber-500 text-white text-xs shrink-0"
            >
              Confirm Undo
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
