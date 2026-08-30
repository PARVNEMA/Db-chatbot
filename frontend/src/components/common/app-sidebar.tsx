"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Database,
  FolderGit2,
  Sparkles,
  LogOut,
  User as UserIcon,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface AppSidebarProps {
  className?: string;
}

export function AppSidebar({ className }: AppSidebarProps): React.JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    try {
      await logout();
      toast.success("Signed out successfully");
      router.push("/login");
    } catch {
      toast.error("Failed to sign out");
    }
  };

  const navItems = [
    {
      label: "Projects Workspace",
      href: "/projects",
      icon: FolderGit2,
      active: pathname === "/projects" || pathname.startsWith("/projects/"),
    },
    {
      label: "Live Vector Stream",
      href: "/embeddings-demo",
      icon: Sparkles,
      active: pathname === "/embeddings-demo",
      badge: "SSE",
    },
  ];

  return (
    <aside
      className={cn(
        "flex flex-col w-64 shrink-0 border-r border-zinc-800/80 bg-zinc-950/95 h-screen sticky top-0 text-zinc-300 select-none z-30",
        className
      )}
    >
      {/* Brand Header */}
      <div className="h-16 px-5 flex items-center justify-between border-b border-zinc-800/80 shrink-0">
        <Link href="/projects" className="flex items-center gap-2.5 group">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-600/20 group-hover:scale-105 transition-transform">
            <Database className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-sm tracking-tight text-white group-hover:text-blue-400 transition-colors">
              AskMyDB
            </span>
            <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
              v1.0
            </span>
          </div>
        </Link>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-2 pb-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
          Platform
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group",
                item.active
                  ? "bg-blue-600/10 text-blue-400 border border-blue-500/20 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/80"
              )}
            >
              <div className="flex items-center gap-2.5">
                <Icon
                  className={cn(
                    "h-4 w-4 transition-colors",
                    item.active
                      ? "text-blue-400"
                      : "text-zinc-500 group-hover:text-zinc-300"
                  )}
                />
                <span>{item.label}</span>
              </div>
              {item.badge ? (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {item.badge}
                </span>
              ) : (
                <ChevronRight
                  className={cn(
                    "h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600",
                    item.active && "opacity-100 text-blue-400"
                  )}
                />
              )}
            </Link>
          );
        })}
      </div>

      {/* User Footer Profile & Logout */}
      <div className="p-3 border-t border-zinc-800/80 shrink-0 bg-zinc-900/30">
        <div className="flex items-center justify-between p-2 rounded-xl bg-zinc-900/80 border border-zinc-800/80">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-8 w-8 rounded-lg bg-zinc-800 flex items-center justify-center text-zinc-300 shrink-0 ring-1 ring-zinc-700">
              <UserIcon className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-zinc-200 truncate">
                {user?.email || "Account"}
              </p>
              <p className="text-[10px] font-mono text-zinc-500 truncate">
                Active Tenant
              </p>
            </div>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={handleLogout}
            className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10 ml-1 shrink-0"
            title="Sign Out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
