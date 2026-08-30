import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-blue-600 text-white shadow hover:bg-blue-500",
        secondary:
          "border-transparent bg-zinc-800 text-zinc-200 hover:bg-zinc-700",
        destructive:
          "border-transparent bg-red-500/20 text-red-400 border-red-500/30",
        outline: "text-zinc-300 border-zinc-700",
        success:
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 font-mono",
        accent:
          "border-indigo-500/30 bg-indigo-500/10 text-indigo-400 font-mono",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
