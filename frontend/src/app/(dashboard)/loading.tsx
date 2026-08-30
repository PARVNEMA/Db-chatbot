import React from "react";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading(): React.JSX.Element {
  return (
    <div className="space-y-6 animate-in fade-in-0 duration-150">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48 rounded-lg" />
          <Skeleton className="h-4 w-72 rounded-md" />
        </div>
        <Skeleton className="h-9 w-32 rounded-xl" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
      </div>

      <Skeleton className="h-80 w-full rounded-2xl" />
    </div>
  );
}
