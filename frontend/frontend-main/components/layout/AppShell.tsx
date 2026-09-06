"use client";

import React from "react";
import { AppSidebar } from "./AppSidebar";
import { useAppSession } from "../../lib/session-store";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const session = useAppSession();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-[#070e1e] dark:text-slate-100">
      <div className="flex min-h-screen">
        {/* Shared Navy Sidebar */}
        <AppSidebar session={session} />

        {/* Main Workspace Area */}
        <div className="flex flex-1 flex-col pl-0 lg:pl-64">
          <main className="flex-1 p-5 sm:p-8">
            {children}
          </main>

          {/* Consistent Application Footer */}
          <footer className="mt-auto border-t border-slate-200/80 bg-white/60 px-6 py-4 text-center text-xs text-slate-400 dark:border-slate-800/80 dark:bg-slate-900/40 dark:text-slate-500">
            Honey Chain Traceability Platform • SIH 2026 PS 26021 • Cryptographically Secured
          </footer>
        </div>
      </div>
    </div>
  );
}
