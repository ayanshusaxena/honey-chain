"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Sun,
  Moon,
  ChevronDown,
  LogOut,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { logout } from "../../lib/auth";
import { useTheme } from "../ThemeProvider";
import { BackNavigation } from "../ui/BackNavigation";
import type { UserRole } from "../../types/contracts";
import type { SessionData } from "../../lib/session-store";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface AppHeaderProps {
  title: string;
  breadcrumbs?: BreadcrumbItem[];
  showBack?: boolean;
  backFallbackUrl?: string;
  session: SessionData | null;
  onRefresh?: () => void;
  refreshing?: boolean;
  actions?: React.ReactNode;
}

function getRoleLabel(role: UserRole | null): string {
  switch (role) {
    case "ADMIN":
      return "Administrator";
    case "BEEKEEPER":
      return "Beekeeper";
    case "PROCESSOR":
      return "Processor";
    default:
      return "Operator";
  }
}

function getRoleBadgeStyle(role: UserRole | null): string {
  switch (role) {
    case "ADMIN":
      return "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
    case "BEEKEEPER":
      return "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";
    case "PROCESSOR":
      return "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/60";
    default:
      return "bg-slate-100 text-slate-800 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";
  }
}

export function AppHeader({
  title,
  breadcrumbs = [{ label: "Honey Chain" }, { label: "Operations" }],
  showBack = true,
  backFallbackUrl = "/dashboard",
  session,
  onRefresh,
  refreshing = false,
  actions,
}: AppHeaderProps) {
  const router = useRouter();
  const { isDark, toggleTheme } = useTheme();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  const role = session?.role ?? null;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        accountMenuRef.current &&
        !accountMenuRef.current.contains(event.target as Node)
      ) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      {/* Left: Back + Breadcrumbs + Title */}
      <div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
          {showBack && <BackNavigation fallbackUrl={backFallbackUrl} className="mr-1" />}
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <span>/</span>}
              {crumb.href ? (
                <button
                  onClick={() => router.push(crumb.href!)}
                  className="hover:text-amber-600 dark:hover:text-amber-400 transition"
                >
                  {crumb.label}
                </button>
              ) : (
                <span className={idx === breadcrumbs.length - 1 ? "text-slate-700 dark:text-slate-300 font-semibold" : ""}>
                  {crumb.label}
                </span>
              )}
            </React.Fragment>
          ))}
        </div>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {title}
        </h2>
      </div>

      {/* Right Controls: Actions + Refresh + Theme + Account */}
      <div className="flex items-center gap-2.5">
        {actions}

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            title="Refresh data"
            className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-amber-500" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          type="button"
          aria-label={isDark ? "Switch to Honey Chain Light theme" : "Switch to Dark theme"}
          title={isDark ? "Switch to Honey Chain Light" : "Switch to Dark theme"}
          className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {isDark ? (
            <>
              <Sun className="h-3.5 w-3.5 text-amber-400" />
              <span className="hidden sm:inline">Light</span>
            </>
          ) : (
            <>
              <Moon className="h-3.5 w-3.5 text-slate-600 dark:text-slate-400" />
              <span className="hidden sm:inline">Dark</span>
            </>
          )}
        </button>

        {/* Dynamic Account Control */}
        <div className="relative" ref={accountMenuRef}>
          <button
            onClick={() => setAccountMenuOpen(!accountMenuOpen)}
            aria-expanded={accountMenuOpen}
            aria-haspopup="true"
            className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white p-1.5 pr-3 shadow-sm transition hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-slate-800 dark:bg-slate-900/90 dark:hover:border-slate-700"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-amber-600 text-xs font-bold text-white shadow-sm">
              {role ? role.slice(0, 2) : "HC"}
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 leading-tight">
                {getRoleLabel(role)}
              </p>
              <p className="text-[10px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                Honey Chain
              </p>
            </div>
            <ChevronDown className={`h-4 w-4 text-slate-400 transition ${accountMenuOpen ? "rotate-180" : ""}`} />
          </button>

          {/* Account Popover Menu */}
          {accountMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-lg ring-1 ring-black/5 z-50 dark:border-slate-800 dark:bg-slate-900 dark:ring-white/10">
              <div className="border-b border-slate-100 dark:border-slate-800 px-3 py-2.5">
                <p className="text-xs font-bold text-slate-800 dark:text-white">
                  {getRoleLabel(role)} Session
                </p>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono mt-0.5 truncate">
                  ID: {session?.userId || "anonymous"}
                </p>
                <div className="mt-2 flex items-center gap-1.5">
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${getRoleBadgeStyle(role)}`}>
                    Role: {role || "NONE"}
                  </span>
                </div>
              </div>

              <div className="px-3 py-2 text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                <span>Cryptographically Authenticated</span>
              </div>

              <div className="border-t border-slate-100 dark:border-slate-800 pt-1">
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-red-600 hover:bg-red-50 transition dark:text-red-400 dark:hover:bg-red-950/30"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Sign out of session</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
