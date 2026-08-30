import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  text?: string;
}

export function LoadingSpinner({
  className,
  size = "md",
  text,
}: LoadingSpinnerProps): React.JSX.Element {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-6 w-6",
    lg: "h-10 w-10",
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 text-zinc-400",
        className
      )}
    >
      <Loader2
        className={cn(
          "animate-spin text-blue-500",
          sizeClasses[size]
        )}
      />
      {text && (
        <span className="text-xs font-mono text-zinc-500">{text}</span>
      )}
    </div>
  );
}
