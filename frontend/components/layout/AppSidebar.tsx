"use client";

import React from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Hexagon,
  Radio,
  ShieldAlert,
  Leaf,
  GitBranch,
  Package,
  FileText,
  Blocks,
  BarChart3,
  Users,
  Cpu,
  LogOut,
  ArrowRight,
  LucideIcon,
} from "lucide-react";
import { logout } from "../../lib/auth";
import type { UserRole } from "../../types/contracts";
import type { SessionData } from "../../lib/session-store";

interface MenuItem {
  name: string;
  path: string;
  icon: LucideIcon;
  allowedRoles?: UserRole[];
  group: "OPERATIONS" | "PROCESSING" | "VERIFICATION" | "MANAGEMENT";
}

const MENU_ITEMS: MenuItem[] = [
  { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard, group: "OPERATIONS" },
  { name: "Hives", path: "/hives", icon: Hexagon, group: "OPERATIONS" },
  { name: "Telemetry", path: "/telemetry", icon: Radio, group: "OPERATIONS" },
  { name: "Risk Assessment", path: "/risk", icon: ShieldAlert, group: "OPERATIONS" },
  { name: "Harvests", path: "/harvests", icon: Leaf, group: "PROCESSING", allowedRoles: ["ADMIN", "BEEKEEPER"] },
  { name: "Collection Lots", path: "/collection-lots", icon: GitBranch, group: "PROCESSING", allowedRoles: ["ADMIN", "PROCESSOR"] },
  { name: "Batches", path: "/batches", icon: Package, group: "PROCESSING", allowedRoles: ["ADMIN", "PROCESSOR"] },
  { name: "Lab Evidence", path: "/lab-evidence", icon: FileText, group: "VERIFICATION" },
  { name: "Blockchain", path: "/blockchain", icon: Blocks, group: "VERIFICATION", allowedRoles: ["ADMIN"] },
  { name: "Analytics", path: "/analytics", icon: BarChart3, group: "MANAGEMENT" },
  { name: "IoT Simulator", path: "/simulator", icon: Cpu, group: "MANAGEMENT", allowedRoles: ["ADMIN"] },
  { name: "Users", path: "/users", icon: Users, group: "MANAGEMENT", allowedRoles: ["ADMIN"] },
];

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

interface AppSidebarProps {
  session: SessionData | null;
}

export function AppSidebar({ session }: AppSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const role = session?.role ?? null;

  const visibleMenu = MENU_ITEMS.filter((item) => {
    if (!item.allowedRoles) return true;
    if (!role) return false;
    return item.allowedRoles.includes(role);
  });

  const menuGroups = Array.from(new Set(visibleMenu.map((m) => m.group)));

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <aside className="fixed left-0 top-0 z-30 flex h-screen w-64 flex-col overflow-y-auto bg-gradient-to-b from-[#061735] via-[#092653] to-[#071b3d] text-white shadow-xl dark:border-r dark:border-slate-800 dark:from-[#030b1a] dark:via-[#051329] dark:to-[#020814]">
      {/* Brand Logo */}
      <div className="flex items-center gap-3 border-b border-white/10 px-6 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-amber-500 shadow-md">
          <Hexagon className="h-6 w-6 text-slate-900" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-white">
            Honey Chain
          </h1>
          <p className="text-xs text-blue-200/80">
            Traceability Platform
          </p>
        </div>
      </div>

      {/* Nav Menu */}
      <nav className="flex-1 space-y-6 px-3 py-5">
        {menuGroups.map((group) => {
          const items = visibleMenu.filter((m) => m.group === group);
          return (
            <div key={group}>
              <p className="px-3 text-[10px] font-bold tracking-wider text-blue-300/70">
                {group}
              </p>
              <div className="mt-2 space-y-1">
                {items.map((item) => {
                  const active = pathname === item.path;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.name}
                      onClick={() => router.push(item.path)}
                      className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs font-semibold transition ${
                        active
                          ? "bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-sm"
                          : "text-slate-300 hover:bg-white/10 hover:text-white"
                      }`}
                    >
                      <Icon
                        className={`h-4 w-4 shrink-0 ${
                          active ? "text-white" : "text-slate-400 group-hover:text-white"
                        }`}
                      />
                      <span className="flex-1">{item.name}</span>
                      {active && <ArrowRight className="h-3 w-3 opacity-80" />}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Bottom Session Info */}
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center justify-between rounded-xl bg-white/5 p-3 dark:bg-black/20">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-xs font-bold text-slate-900">
              {role ? role.slice(0, 2) : "HC"}
            </div>
            <div className="text-left">
              <p className="text-xs font-bold text-white">
                {getRoleLabel(role)}
              </p>
              <p className="text-[10px] text-blue-200/70">
                Active Session
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out of session"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
