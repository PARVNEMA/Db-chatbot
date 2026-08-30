"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ChevronRight,
  Database,
  LogOut,
  Activity,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export function Header(): React.JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      toast.success("Signed out successfully");
      router.push("/login");
    } catch {
      toast.error("Failed to sign out");
    }
  };

  // Generate dynamic breadcrumb segments
  const pathSegments = pathname.split("/").filter(Boolean);

  return (
    <header className="h-16 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Left: Mobile Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon-sm"
          className="md:hidden text-zinc-400 hover:text-white"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>

        {/* Breadcrumb Navigation */}
        <nav className="flex items-center gap-1.5 text-xs text-zinc-400 font-mono">
          <Link
            href="/projects"
            className="hover:text-zinc-100 transition-colors flex items-center gap-1"
          >
            <Database className="h-3.5 w-3.5 text-blue-400" />
            <span className="hidden sm:inline">AskMyDB</span>
          </Link>

          {pathSegments.map((segment, index) => {
            const href = `/${pathSegments.slice(0, index + 1).join("/")}`;
            const isLast = index === pathSegments.length - 1;
            const formatted =
              segment.length > 20
                ? `${segment.slice(0, 8)}...`
                : segment.charAt(0).toUpperCase() + segment.slice(1);

            return (
              <React.Fragment key={href}>
                <ChevronRight className="h-3.5 w-3.5 text-zinc-600 shrink-0" />
                {isLast ? (
                  <span className="text-zinc-200 font-semibold truncate max-w-[150px] sm:max-w-none">
                    {formatted}
                  </span>
                ) : (
                  <Link
                    href={href}
                    className="hover:text-zinc-200 transition-colors truncate max-w-[120px] sm:max-w-none"
                  >
                    {formatted}
                  </Link>
                )}
              </React.Fragment>
            );
          })}
        </nav>
      </div>

      {/* Right: Status & User Profile Dropdown */}
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-mono">
          <Activity className="h-3 w-3" />
          <span>System Healthy</span>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-zinc-900 border border-transparent hover:border-zinc-800 transition outline-none">
              <div className="h-7 w-7 rounded-lg bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30 flex items-center justify-center font-bold text-xs">
                {user?.email?.charAt(0).toUpperCase() || "U"}
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>
              <div className="font-sans font-medium text-xs text-zinc-200 truncate">
                {user?.email}
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">
                Project Owner
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-red-400 hover:text-red-300 hover:bg-red-500/10 focus:bg-red-500/10 gap-2"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Mobile Drawer Navigation (when open) */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-x-0 top-16 bg-zinc-950/95 border-b border-zinc-800 p-4 space-y-2 backdrop-blur-xl animate-in slide-in-from-top-2">
          <Link
            href="/projects"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-zinc-200 hover:bg-zinc-900"
          >
            <Database className="h-4 w-4 text-blue-400" />
            Projects Workspace
          </Link>
          <Link
            href="/embeddings-demo"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-zinc-200 hover:bg-zinc-900"
          >
            <Activity className="h-4 w-4 text-emerald-400" />
            Live Vector Stream (SSE)
          </Link>
          <div className="pt-2 border-t border-zinc-800 flex justify-between items-center px-1">
            <span className="text-xs text-zinc-500">{user?.email}</span>
            <Button
              variant="ghost"
              size="xs"
              onClick={handleLogout}
              className="text-red-400 hover:bg-red-500/10"
            >
              <LogOut className="h-3.5 w-3.5 mr-1" />
              Sign Out
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
