"use client";

import React from "react";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AppSidebar } from "@/components/common/app-sidebar";
import { Header } from "@/components/common/header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-zinc-950 text-zinc-100 antialiased font-sans">
        {/* Desktop Sidebar */}
        <AppSidebar className="hidden md:flex" />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <Header />
          <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
            <div className="max-w-7xl mx-auto space-y-6">{children}</div>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
