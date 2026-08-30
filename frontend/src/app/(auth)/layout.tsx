"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/projects");
    }
  }, [isLoading, isAuthenticated, router]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center p-4 sm:p-8 bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Background ambient glow effects */}
      <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-blue-600/10 blur-[128px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-indigo-600/10 blur-[128px] pointer-events-none" />

      <main className="relative z-10 w-full flex items-center justify-center">
        {children}
      </main>

      <footer className="relative z-10 mt-8 text-center text-xs text-zinc-600 font-mono">
        NL-DB Query Platform &copy; 2026
      </footer>
    </div>
  );
}
