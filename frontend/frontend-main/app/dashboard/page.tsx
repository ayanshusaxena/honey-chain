
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useRef, useSyncExternalStore } from "react";
import {
  LayoutDashboard,
  Package,
  Hexagon,
  GitBranch,
  Radio,
  Blocks,
  BarChart3,
  Users,
  FileText,
  LogOut,
  Activity,
  ShieldAlert,
  ArrowRight,
  AlertTriangle,
  MapPin,
  Leaf,
  Factory,
  CheckCircle2,
  LucideIcon,
  Loader2,
  ChevronDown,
  RefreshCw,
  ShieldCheck,
  ExternalLink,
  Sun,
  Moon,
} from "lucide-react";
import { logout, getCurrentSession, getAccessToken } from "../../lib/auth";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useTheme } from "../../components/ThemeProvider";
import type {
  UserRole,
  HiveResponse,
  HarvestResponse,
  BatchResponse,
} from "../../types/contracts";

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

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBg,
  iconColor,
  onClick,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-5 text-left shadow-sm transition hover:border-amber-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-slate-800/90 dark:bg-slate-900/90 dark:hover:border-amber-500/40"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {title}
        </span>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${iconBg}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>

      <div className="mt-4">
        <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</p>
        <div className="mt-1 flex items-center justify-between">
          <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
          <ArrowRight className="h-4 w-4 text-slate-400 opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100 dark:text-slate-500" />
        </div>
      </div>
    </button>
  );
}

let cachedSession: { userId: string; role: UserRole } | null = null;
let lastToken: string | null = null;

function getSessionSnapshot(): { userId: string; role: UserRole } | null {
  if (typeof window === "undefined") return null;
  const token = getAccessToken();
  if (token !== lastToken) {
    lastToken = token;
    cachedSession = getCurrentSession();
  }
  return cachedSession;
}

const sessionStore = {
  subscribe(listener: () => void) {
    if (typeof window === "undefined") return () => {};
    const onAuth = () => {
      lastToken = null; // invalidate cache
      listener();
    };
    window.addEventListener("storage", onAuth);
    window.addEventListener("auth-state-changed", onAuth);
    return () => {
      window.removeEventListener("storage", onAuth);
      window.removeEventListener("auth-state-changed", onAuth);
    };
  },
  getSnapshot(): { userId: string; role: UserRole } | null {
    return getSessionSnapshot();
  },
  getServerSnapshot(): { userId: string; role: UserRole } | null {
    return null;
  },
};

export default function DashboardPage() {
  const pathname = usePathname();
  const router = useRouter();
  const { isDark, toggleTheme } = useTheme();

  const session = useSyncExternalStore(
    sessionStore.subscribe,
    sessionStore.getSnapshot,
    sessionStore.getServerSnapshot
  );

  const [liveHives, setLiveHives] = useState<HiveResponse[]>([]);
  const [liveHarvests, setLiveHarvests] = useState<HarvestResponse[]>([]);
  const [liveBatches, setLiveBatches] = useState<BatchResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const accountMenuRef = useRef<HTMLDivElement>(null);

  const role = session?.role ?? null;

  // Filter menu items by current role
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

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const hivesPromise = apiClient.get<HiveResponse[]>("/hives");
      const harvestsPromise =
        role === "ADMIN" || role === "BEEKEEPER"
          ? apiClient.get<HarvestResponse[]>("/harvests")
          : Promise.resolve([] as HarvestResponse[]);
      const batchesPromise =
        role === "ADMIN" || role === "PROCESSOR"
          ? apiClient.get<BatchResponse[]>("/batches")
          : Promise.resolve([] as BatchResponse[]);

      const [hivesData, harvestsData, batchesData] = await Promise.all([
        hivesPromise,
        harvestsPromise,
        batchesPromise,
      ]);

      setLiveHives(hivesData || []);
      setLiveHarvests(harvestsData || []);
      setLiveBatches(batchesData || []);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.displayMessage);
      } else {
        setError("Unable to connect to Honey Chain services. Check backend status.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        const hivesPromise = apiClient.get<HiveResponse[]>("/hives");
        const harvestsPromise =
          role === "ADMIN" || role === "BEEKEEPER"
            ? apiClient.get<HarvestResponse[]>("/harvests")
            : Promise.resolve([] as HarvestResponse[]);
        const batchesPromise =
          role === "ADMIN" || role === "PROCESSOR"
            ? apiClient.get<BatchResponse[]>("/batches")
            : Promise.resolve([] as BatchResponse[]);

        const [hivesData, harvestsData, batchesData] = await Promise.all([
          hivesPromise,
          harvestsPromise,
          batchesPromise,
        ]);

        if (!active) return;
        setLiveHives(hivesData || []);
        setLiveHarvests(harvestsData || []);
        setLiveBatches(batchesData || []);
        setError(null);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiError) {
          setError(err.displayMessage);
        } else {
          setError("Unable to connect to Honey Chain services. Check backend status.");
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchData();

    return () => {
      active = false;
    };
  }, [role]);

  // Close account menu on outside click
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

  const alertsCount = liveHives.filter((h) => h.status !== "ACTIVE").length;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#070e1e] text-slate-900 dark:text-slate-100">
      <div className="flex min-h-screen">
        {/* ================================================================ */}
        {/* SIDEBAR */}
        {/* ================================================================ */}
        <aside className="fixed left-0 top-0 z-30 flex h-screen w-64 flex-col overflow-y-auto bg-gradient-to-b from-[#061735] via-[#092653] to-[#071b3d] dark:from-[#030b1a] dark:via-[#051329] dark:to-[#020814] text-white shadow-xl dark:border-r dark:border-slate-800">
          {/* Logo Branding */}
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

          {/* Navigation Items Grouped */}
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

          {/* Sidebar Footer */}
          <div className="border-t border-white/10 p-4">
            <div className="mb-3 flex items-center justify-between rounded-lg bg-white/5 p-2.5">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/20 text-xs font-bold text-amber-300">
                  {role ? role.slice(0, 2) : "OP"}
                </div>
                <div>
                  <p className="text-xs font-semibold text-white">
                    {getRoleLabel(role)}
                  </p>
                  <p className="text-[10px] text-blue-200/60">
                    Active Session
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
              <span>Sign out</span>
            </button>
          </div>
        </aside>

        {/* ================================================================ */}
        {/* MAIN WORKSPACE */}
        {/* ================================================================ */}
        <main className="ml-64 flex-1 overflow-x-hidden bg-slate-50/70 dark:bg-[#070e1e] p-6 lg:p-8 transition-colors duration-150">
          {/* TOP BAR */}
          <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                <span>Honey Chain</span>
                <span>/</span>
                <span className="text-slate-700 dark:text-slate-300 font-semibold">Operations</span>
              </div>
              <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                Operational Dashboard
              </h2>
            </div>

            {/* Top Right Controls: [ Refresh ] [ Theme ] [ Administrator ▼ ] */}
            <div className="flex items-center gap-2.5">
              {/* Refresh Control */}
              <button
                onClick={handleRefresh}
                disabled={loading}
                title="Refresh dashboard data"
                className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-amber-500" : ""}`} />
                <span className="hidden sm:inline">Refresh</span>
              </button>

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
                      <p className="text-xs font-bold text-slate-900 dark:text-white">
                        {getRoleLabel(role)} Session
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 truncate">
                        ID: {session?.userId || "Active Session"}
                      </p>
                      <div className="mt-2">
                        <span className={`inline-block rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${getRoleBadgeStyle(role)}`}>
                          Role: {role || "AUTHENTICATED"}
                        </span>
                      </div>
                    </div>

                    <div className="px-1 py-1.5">
                      <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-slate-600 dark:text-slate-300">
                        <ShieldCheck className="h-4 w-4 text-emerald-600" />
                        <span>Cryptographically Authenticated</span>
                      </div>
                    </div>

                    <div className="border-t border-slate-100 dark:border-slate-800 pt-1">
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-semibold text-red-600 dark:text-red-400 transition hover:bg-red-50 dark:hover:bg-red-950/40"
                      >
                        <LogOut className="h-4 w-4" />
                        <span>Sign out of session</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* API Error Notification */}
          {error && (
            <div className="mb-6 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/30 p-4 text-sm font-medium text-red-700 dark:text-red-300 shadow-sm">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="h-5 w-5 shrink-0 text-red-500" />
                <span>{error}</span>
              </div>
              <button
                onClick={handleRefresh}
                className="rounded-lg bg-red-100 dark:bg-red-900/50 px-3 py-1.5 text-xs font-bold text-red-800 dark:text-red-200 transition hover:bg-red-200 dark:hover:bg-red-900/80"
              >
                Retry
              </button>
            </div>
          )}

          {/* STATS METRIC GRID */}
          <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Active Hives"
              value={loading ? "..." : String(liveHives.length)}
              subtitle="Registered apiary units"
              icon={Hexagon}
              iconBg="bg-amber-50 dark:bg-amber-950/40"
              iconColor="text-amber-600 dark:text-amber-400"
              onClick={() => router.push("/hives")}
            />
            <StatCard
              title="Operational Alerts"
              value={loading ? "..." : String(alertsCount)}
              subtitle={alertsCount === 0 ? "All hives nominal" : "Requires attention"}
              icon={AlertTriangle}
              iconBg={alertsCount > 0 ? "bg-red-50 dark:bg-red-950/40" : "bg-emerald-50 dark:bg-emerald-950/40"}
              iconColor={alertsCount > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}
              onClick={() => router.push("/risk")}
            />
            <StatCard
              title="Harvest Records"
              value={loading ? "..." : String(liveHarvests.length)}
              subtitle="Logged collections"
              icon={Leaf}
              iconBg="bg-emerald-50 dark:bg-emerald-950/40"
              iconColor="text-emerald-600 dark:text-emerald-400"
              onClick={() => router.push("/harvests")}
            />
            <StatCard
              title="Active Batches"
              value={loading ? "..." : String(liveBatches.length)}
              subtitle="In processing pipeline"
              icon={Package}
              iconBg="bg-blue-50 dark:bg-blue-950/40"
              iconColor="text-blue-600 dark:text-blue-400"
              onClick={() => router.push("/batches")}
            />
          </section>

          {/* TRACEABILITY OPERATIONAL WORKFLOW LAUNCHER */}
          <section className="mb-6 rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Traceability Demo Pipeline
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Follow honey from source apiary through IoT telemetry, risk evaluation, and batch lineage.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <button
                onClick={() => router.push("/hives")}
                className="group flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-left transition hover:border-amber-300 hover:bg-amber-50/50 dark:border-slate-800 dark:bg-slate-800/60 dark:hover:border-amber-500/40 dark:hover:bg-slate-800/90"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
                    <Hexagon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800 group-hover:text-amber-900 dark:text-slate-200 dark:group-hover:text-amber-300">
                      1. Hives
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">Source apiary registry</p>
                  </div>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-amber-600 dark:text-slate-500 dark:group-hover:text-amber-400" />
              </button>

              <button
                onClick={() => router.push("/telemetry")}
                className="group flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-left transition hover:border-amber-300 hover:bg-amber-50/50 dark:border-slate-800 dark:bg-slate-800/60 dark:hover:border-amber-500/40 dark:hover:bg-slate-800/90"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
                    <Radio className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800 group-hover:text-blue-900 dark:text-slate-200 dark:group-hover:text-blue-300">
                      2. Telemetry
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">IoT sensor monitoring</p>
                  </div>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-blue-600 dark:text-slate-500 dark:group-hover:text-blue-400" />
              </button>

              <button
                onClick={() => router.push("/risk")}
                className="group flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-left transition hover:border-amber-300 hover:bg-amber-50/50 dark:border-slate-800 dark:bg-slate-800/60 dark:hover:border-amber-500/40 dark:hover:bg-slate-800/90"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300">
                    <ShieldAlert className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800 group-hover:text-red-900 dark:text-slate-200 dark:group-hover:text-red-300">
                      3. Risk Analysis
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">Rule engine verification</p>
                  </div>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-red-600 dark:text-slate-500 dark:group-hover:text-red-400" />
              </button>

              <button
                onClick={() => router.push("/dashboard/traceability")}
                className="group flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-left transition hover:border-amber-300 hover:bg-amber-50/50 dark:border-slate-800 dark:bg-slate-800/60 dark:hover:border-amber-500/40 dark:hover:bg-slate-800/90"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                    <GitBranch className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800 group-hover:text-emerald-900 dark:text-slate-200 dark:group-hover:text-emerald-300">
                      4. Traceability
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">Batch lineage check</p>
                  </div>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-emerald-600 dark:text-slate-500 dark:group-hover:text-emerald-400" />
              </button>
            </div>
          </section>

          {/* TWO-COLUMN OPERATIONAL DATA SECTIONS */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
            {/* LEFT COLUMN: Hive Monitoring (7 cols) */}
            <div className="xl:col-span-7 space-y-6">
              <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-4">
                  <div className="flex items-center gap-2.5">
                    <Activity className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-white">
                        Hive Monitoring Registry
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Live IoT connected hives and field status
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => router.push("/hives")}
                    className="flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-300"
                  >
                    <span>View all</span>
                    <ArrowRight className="h-3 w-3" />
                  </button>
                </div>

                {loading && (
                  <div className="flex items-center justify-center p-8 text-slate-400">
                    <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
                    <span className="ml-2.5 text-xs font-medium">Loading live hive records...</span>
                  </div>
                )}

                {!loading && liveHives.length === 0 && (
                  <p className="p-8 text-center text-xs text-slate-400">
                    No registered hives found in backend database.
                  </p>
                )}

                {!loading && liveHives.length > 0 && (
                  <div className="mt-4 divide-y divide-slate-100 dark:divide-slate-800/80">
                    {liveHives.slice(0, 4).map((hive) => (
                      <div
                        key={hive.id}
                        className="flex items-center justify-between py-3 transition hover:bg-slate-50/60 dark:hover:bg-slate-800/50 rounded-lg px-2"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
                            <Hexagon className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                              {hive.hive_code}
                            </p>
                            <p className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 truncate">
                              <MapPin className="h-3 w-3 shrink-0" />
                              {hive.location_region}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                              hive.status === "ACTIVE"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60"
                                : "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60"
                            }`}
                          >
                            {hive.status}
                          </span>
                          <button
                            onClick={() => router.push(`/telemetry?hive_id=${hive.id}`)}
                            title="Inspect live telemetry"
                            className="flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                          >
                            <span>Telemetry</span>
                            <ExternalLink className="h-2.5 w-2.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {/* RIGHT COLUMN: Alerts & Batches (5 cols) */}
            <div className="xl:col-span-5 space-y-6">
              {/* SYSTEM ALERTS CARD */}
              <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-red-500" />
                    <h3 className="text-sm font-bold text-slate-800 dark:text-white">
                      Operational Alerts
                    </h3>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${alertsCount > 0 ? "bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"}`}>
                    {alertsCount} {alertsCount === 1 ? "Issue" : "Issues"}
                  </span>
                </div>

                <div className="mt-3">
                  {alertsCount === 0 ? (
                    <div className="flex items-center gap-3 rounded-lg border border-emerald-200/80 bg-emerald-50/60 p-3.5 dark:border-emerald-900/50 dark:bg-emerald-950/30">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                      <p className="text-xs font-medium text-emerald-800 dark:text-emerald-300">
                        All hives operating within nominal thresholds.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {liveHives
                        .filter((h) => h.status !== "ACTIVE")
                        .map((hive) => (
                          <button
                            key={hive.id}
                            onClick={() => router.push(`/risk?hive_id=${hive.id}`)}
                            className="flex w-full items-center justify-between rounded-lg border border-red-200 bg-red-50/80 p-3 text-left transition hover:bg-red-100/60 dark:border-red-900/50 dark:bg-red-950/30 dark:hover:bg-red-900/50"
                          >
                            <div className="flex items-center gap-2.5">
                              <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
                              <div>
                                <p className="text-xs font-bold text-red-900 dark:text-red-200">
                                  {hive.hive_code} Requires Review
                                </p>
                                <p className="text-[11px] text-red-700 dark:text-red-400">
                                  Status: {hive.status} · {hive.location_region}
                                </p>
                              </div>
                            </div>
                            <ArrowRight className="h-3.5 w-3.5 text-red-500" />
                          </button>
                        ))}
                    </div>
                  )}
                </div>
              </section>

              {/* RECENT PROCESSING BATCHES */}
              <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2">
                    <Factory className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <h3 className="text-sm font-bold text-slate-800 dark:text-white">
                      Recent Batches
                    </h3>
                  </div>
                  <button
                    onClick={() => router.push("/batches")}
                    className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    <span>View all</span>
                    <ArrowRight className="h-3 w-3" />
                  </button>
                </div>

                {loading && (
                  <div className="flex items-center justify-center p-6 text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                    <span className="ml-2 text-xs">Loading batches...</span>
                  </div>
                )}

                {!loading && liveBatches.length === 0 && (
                  <p className="p-6 text-center text-xs text-slate-400">
                    No processing batches logged.
                  </p>
                )}

                {!loading && liveBatches.length > 0 && (
                  <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800/80">
                    {liveBatches.slice(0, 3).map((batch) => (
                      <button
                        key={batch.id}
                        onClick={() => router.push("/batches")}
                        className="flex w-full items-center justify-between py-2.5 text-left transition hover:bg-slate-50/80 dark:hover:bg-slate-800/60 rounded px-1.5"
                      >
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400">
                            <Package className="h-3.5 w-3.5" />
                          </div>
                          <div>
                            <p className="text-xs font-bold text-slate-900 dark:text-white leading-tight">
                              {batch.batch_code}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                              Quantity: {batch.derived_quantity_kg.toFixed(1)} kg
                            </p>
                          </div>
                        </div>

                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            batch.status === "ACTIVE"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60"
                              : "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60"
                          }`}
                        >
                          {batch.status}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>

          {/* FOOTER */}
          <footer className="mt-8 flex items-center justify-center gap-2 border-t border-slate-200 dark:border-slate-800 pt-6 text-xs text-slate-400 dark:text-slate-500">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span>Honey Chain Platform · Real-time cryptographic traceability & IoT monitoring</span>
          </footer>
        </main>
      </div>
    </div>
  );
}