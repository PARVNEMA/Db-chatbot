import React from "react";
import { LucideIcon, Database } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon = Database,
  title,
  description,
  action,
  className,
}: EmptyStateProps): React.JSX.Element {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-800/80 text-zinc-400 mb-4 ring-1 ring-zinc-700/50">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold text-zinc-100">{title}</h3>
      <p className="text-xs text-zinc-400 max-w-sm mt-1 mb-6 leading-relaxed">
        {description}
      </p>
      {action && <div className="flex items-center gap-3">{action}</div>}
    </div>
  );
}
