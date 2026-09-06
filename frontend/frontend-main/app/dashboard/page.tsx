
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
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
  Clock3,
  MapPin,
  Leaf,
  Factory,
  CheckCircle2,
  LucideIcon,
  Loader2,
} from "lucide-react";
import { logout, getCurrentSession } from "../../lib/auth";
import { apiClient } from "../../lib/api-client";
import type {
  UserRole,
  HiveResponse,
  HarvestResponse,
  BatchResponse,
} from "../../types/contracts";

/**
 * Navigation menu items with optional role restriction.
 * If allowedRoles is undefined, item is visible to all roles.
 * Source: backend/app/models/enums.py UserRole: ADMIN | BEEKEEPER | PROCESSOR
 */
type MenuItem = readonly [string, string, LucideIcon, UserRole[]?];

const menu: MenuItem[] = [
  ["Dashboard", "/dashboard", LayoutDashboard],
  ["Hives", "/hives", Hexagon],
  ["Telemetry", "/telemetry", Radio],
  ["Risk", "/risk", ShieldAlert],
  ["Harvests", "/harvests", Leaf, ["ADMIN", "BEEKEEPER"]],
  ["Collection Lots", "/collection-lots", GitBranch, ["ADMIN", "PROCESSOR"]],
  ["Batches", "/batches", Package, ["ADMIN", "PROCESSOR"]],
  ["Lab Evidence", "/lab-evidence", FileText],
  ["Blockchain", "/blockchain", Blocks, ["ADMIN"]],
  ["Analytics", "/analytics", BarChart3],
  ["Users", "/users", Users, ["ADMIN"]],
];

function goTo(path: string) {
  window.location.href = path;
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBox,
  iconColor,
  path,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  iconBox: string;
  iconColor: string;
  path: string;
}) {
  return (
    <button
      onClick={() => goTo(path)}
      className="group w-full rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div
          className={`flex h-12 w-12 items-center justify-center rounded-2xl ${iconBox}`}
        >
          <Icon className={`h-6 w-6 ${iconColor}`} />
        </div>

        <div
          className={`flex h-10 w-10 items-center justify-center rounded-full ${iconBox}`}
        >
          <ArrowRight className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>

      <p className="mt-5 text-sm font-semibold text-slate-600">{title}</p>

      <p className="mt-1 text-4xl font-bold tracking-tight text-slate-900">
        {value}
      </p>

      <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
    </button>
  );
}

function WorkflowCard({
  title,
  description,
  icon: Icon,
  path,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  path: string;
}) {
  return (
    <button
      onClick={() => goTo(path)}
      className="flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:shadow-md"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
        <Icon className="h-5 w-5 text-blue-600" />
      </div>

      <div className="min-w-0 flex-1">
        <p className="font-semibold text-slate-800">{title}</p>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>

      <ArrowRight className="h-5 w-5 text-slate-400" />
    </button>
  );
}

export default function DashboardPage() {
  const pathname = usePathname();
  const router = useRouter();
  const [role] = useState<UserRole | null>(() => {
    if (typeof window === "undefined") return null;
    return getCurrentSession()?.role ?? null;
  });

  const [liveHives, setLiveHives] = useState<HiveResponse[]>([]);
  const [liveHarvests, setLiveHarvests] = useState<HarvestResponse[]>([]);
  const [liveBatches, setLiveBatches] = useState<BatchResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter menu items by current user role (UX visibility only — backend enforces auth)
  const visibleMenu = menu.filter(([, , , allowedRoles]) => {
    if (!allowedRoles) return true; // visible to all
    if (!role) return false; // hide restricted items until role is known
    return allowedRoles.includes(role);
  });

  const handleLogout = () => {
    logout(); // clears localStorage and cookie
    router.push("/login");
  };

  useEffect(() => {
    let active = true;

    const loadDashboardData = async () => {
      try {
        const hivesPromise = apiClient
          .get<HiveResponse[]>("/hives")
          .catch(() => []);
        const harvestsPromise =
          role === "ADMIN" || role === "BEEKEEPER"
            ? apiClient.get<HarvestResponse[]>("/harvests").catch(() => [])
            : Promise.resolve([]);
        const batchesPromise =
          role === "ADMIN" || role === "PROCESSOR"
            ? apiClient.get<BatchResponse[]>("/batches").catch(() => [])
            : Promise.resolve([]);

        const [hivesData, harvestsData, batchesData] = await Promise.all([
          hivesPromise,
          harvestsPromise,
          batchesPromise,
        ]);

        if (!active) return;
        setLiveHives(hivesData || []);
        setLiveHarvests(harvestsData || []);
        setLiveBatches(batchesData || []);
      } finally {
        if (active) setLoading(false);
      }
    };

    loadDashboardData();

    return () => {
      active = false;
    };
  }, [role]);

  return (
    <div className="min-h-screen bg-transparent text-slate-900">
      <div className="flex min-h-screen">
        {/* SIDEBAR */}
        <aside className="fixed left-0 top-0 z-20 flex h-screen w-[250px] flex-col overflow-hidden bg-gradient-to-b from-[#061735] via-[#092653] to-[#071b3d] text-white shadow-[8px_0_35px_rgba(7,27,61,0.18)]">
          {/* Logo */}
          <div className="px-7 pt-7">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 shadow-lg">
                <Hexagon className="h-8 w-8 text-white" />
              </div>

              <div>
                <h1 className="text-xl font-bold tracking-tight">
                  Honey Chain
                </h1>
                <p className="text-sm text-blue-200">
                  Traceability Platform
                </p>
              </div>
            </div>
          </div>

          {/* Workspace */}
          <div className="mt-10 px-4">
            <p className="px-3 text-xs font-bold tracking-wider text-blue-200">
              WORKSPACE
            </p>

            <div className="mt-4 space-y-2">
              {visibleMenu.map(([name, path, Icon]) => {
                const active = pathname === path;

                return (
                  <button
                    key={name}
                    onClick={() => goTo(path)}
                    className={`flex w-full items-center gap-4 rounded-xl px-4 py-3.5 text-left transition ${
                      active
                        ? "bg-gradient-to-r from-orange-400 to-amber-500 text-white shadow-lg"
                        : "text-slate-200 hover:bg-white/10"
                    }`}
                  >
                    <Icon className="h-5 w-5 shrink-0" />

                    <span className="flex-1 text-sm font-semibold">
                      {name}
                    </span>

                    {active && <ArrowRight className="h-4 w-4" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Bottom decoration */}
          <div className="pointer-events-none absolute -bottom-10 -left-10 opacity-20">
            <Hexagon className="h-32 w-32 text-orange-400" />
          </div>

          <div className="mt-auto px-7 pb-7">
            {role && (
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-blue-300">
                {role}
              </p>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 text-sm text-slate-300 hover:text-white"
            >
              <LogOut className="h-5 w-5" />
              Logout
            </button>
          </div>
        </aside>

        {/* MAIN */}
        <main className="ml-[250px] min-h-screen flex-1 bg-[radial-gradient(circle_at_85%_8%,rgba(255,193,7,0.45),transparent_35%),radial-gradient(circle_at_15%_90%,rgba(245,158,11,0.30),transparent_35%),linear-gradient(135deg,#fff8dc_0%,#fffaf0_45%,#f4f8ff_100%)]">

          {/* HEADER */}
          <header className="flex items-center justify-between px-12 pb-5 pt-8">
            <div>
              <p className="text-sm font-semibold text-[#c58a24]">
                Honey Chain
              </p>

              <h2 className="mt-1 text-4xl font-bold tracking-tight text-[#092653]">
                Dashboard
              </h2>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="font-semibold text-[#092653]">
                  Honey Chain Admin
                </p>
                <p className="text-sm text-slate-500">
                  Administrator
                </p>
              </div>

              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-400 font-bold text-[#18325d]">
                HC
              </div>
            </div>
          </header>

          <div className="px-12 pb-12">

            {/* WELCOME */}
            <section className="relative overflow-hidden rounded-3xl border border-amber-100 bg-gradient-to-r from-[#edf6ff] via-white to-[#fff8df] px-7 py-8 shadow-[0_8px_30px_rgba(245,158,11,0.12)]">
              <div className="relative z-10 max-w-2xl">
                <h3 className="text-3xl font-bold text-[#092653]">
                  Welcome back <span>👋</span>
                </h3>

                <p className="mt-2 text-base text-[#58749b]">
                  Monitor the honey traceability workflow from one place.
                </p>
              </div>

              {/* Honeycomb decoration */}
              <div className="absolute right-12 top-5 grid grid-cols-2 gap-3 opacity-40">
                <div className="h-16 w-16 rounded-2xl border-2 border-yellow-300" />
                <div className="h-16 w-16 rounded-2xl border-2 border-yellow-200" />
                <div className="h-16 w-16 rounded-2xl border-2 border-yellow-200" />
                <div className="h-16 w-16 rounded-2xl border-2 border-yellow-300" />
              </div>

              <div className="absolute right-20 top-12 text-6xl">
                🐝
              </div>
            </section>

            {/* STATS */}
            <section className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
              <StatCard
                title="Total Hives"
                value={loading ? "..." : String(liveHives.length)}
                subtitle="Registered hives"
                icon={Hexagon}
                iconBox="bg-orange-50"
                iconColor="text-orange-500"
                path="/hives"
              />

              <StatCard
                title="Active Alerts"
                value={
                  loading
                    ? "..."
                    : String(
                        liveHives.filter((h) => h.status !== "ACTIVE").length
                      )
                }
                subtitle="Requires attention"
                icon={AlertTriangle}
                iconBox="bg-red-50"
                iconColor="text-red-500"
                path="/risk"
              />

              <StatCard
                title="Harvests"
                value={loading ? "..." : String(liveHarvests.length)}
                subtitle="Recorded harvests"
                icon={Leaf}
                iconBox="bg-emerald-50"
                iconColor="text-emerald-500"
                path="/harvests"
              />

              <StatCard
                title="Batches"
                value={loading ? "..." : String(liveBatches.length)}
                subtitle="Processing batches"
                icon={Package}
                iconBox="bg-blue-50"
                iconColor="text-blue-600"
                path="/batches"
              />
            </section>

            {/* HIVE HEALTH */}
            <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50">
                    <Activity className="h-6 w-6 text-blue-600" />
                  </div>

                  <div>
                    <h3 className="text-xl font-bold text-[#092653]">
                      Hive Health Overview
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Current hive monitoring status
                    </p>
                  </div>
                </div>

                <div className="rounded-full bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-600">
                  ● ACTIVE
                </div>
              </div>

              {loading && (
                <div className="flex items-center justify-center p-8 text-slate-400">
                  <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
                  <span className="ml-3 text-sm font-medium">Loading hives...</span>
                </div>
              )}

              {!loading && liveHives.length === 0 && (
                <p className="mt-6 p-4 text-center text-sm text-slate-400">
                  No registered hives found.
                </p>
              )}

              {!loading && liveHives.length > 0 && (
                <div className="mt-6 space-y-3">
                  {liveHives.slice(0, 4).map((hive) => (
                    <button
                      key={hive.id}
                      onClick={() => goTo(`/hives`)}
                      className="flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-[#f9fbff] p-4 text-left transition hover:border-blue-200 hover:shadow-sm"
                    >
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-orange-50">
                        <Hexagon className="h-6 w-6 text-orange-500" />
                      </div>

                      <div className="flex-1">
                        <p className="font-bold text-[#092653]">
                          {hive.hive_code}
                        </p>

                        <p className="mt-1 flex items-center gap-1 text-sm text-slate-500">
                          <MapPin className="h-3.5 w-3.5" />
                          {hive.location_region}
                        </p>
                      </div>

                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          hive.status === "ACTIVE"
                            ? "bg-emerald-50 text-emerald-600"
                            : hive.status === "MAINTENANCE"
                            ? "bg-orange-50 text-orange-600"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {hive.status}
                      </span>

                      <ArrowRight className="h-5 w-5 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </section>

            {/* ALERTS + BATCHES */}
            <section className="mt-7 grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* ALERTS */}
              <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-[#092653]">
                      Recent Alerts
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Items requiring attention
                    </p>
                  </div>

                  <ShieldAlert className="h-6 w-6 text-red-500" />
                </div>

                <div className="mt-5 space-y-3">
                  {liveHives.filter((h) => h.status !== "ACTIVE").length === 0 ? (
                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4 text-center">
                      <p className="text-sm font-semibold text-emerald-700">
                        All hives operating within normal parameters.
                      </p>
                    </div>
                  ) : (
                    liveHives
                      .filter((h) => h.status !== "ACTIVE")
                      .map((hive) => (
                        <button
                          key={hive.id}
                          onClick={() => goTo(`/risk?hive_id=${hive.id}`)}
                          className="w-full rounded-2xl border border-red-100 bg-red-50 p-4 text-left hover:shadow-sm"
                        >
                          <div className="flex gap-3">
                            <AlertTriangle className="mt-0.5 h-5 w-5 text-red-500" />

                            <div className="flex-1">
                              <p className="font-semibold text-slate-800">
                                Attention required
                              </p>

                              <p className="mt-1 text-sm text-slate-500">
                                {hive.hive_code} · {hive.location_region} ({hive.status})
                              </p>

                              <p className="mt-2 flex items-center gap-1 text-xs text-slate-400">
                                <Clock3 className="h-3 w-3" />
                                Review telemetry & risk
                              </p>
                            </div>

                            <ArrowRight className="h-5 w-5 text-red-400" />
                          </div>
                        </button>
                      ))
                  )}
                </div>
              </div>

              {/* BATCHES */}
              <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-[#092653]">
                      Recent Processing Batches
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Latest traceability records
                    </p>
                  </div>

                  <Factory className="h-6 w-6 text-blue-600" />
                </div>

                {loading && (
                  <div className="flex items-center justify-center p-8 text-slate-400">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    <span className="ml-3 text-sm font-medium">Loading batches...</span>
                  </div>
                )}

                {!loading && liveBatches.length === 0 && (
                  <p className="mt-5 p-4 text-center text-sm text-slate-400">
                    No processing batches recorded yet.
                  </p>
                )}

                {!loading && liveBatches.length > 0 && (
                  <div className="mt-5 space-y-3">
                    {liveBatches.slice(0, 3).map((batch) => (
                      <button
                        key={batch.id}
                        onClick={() => goTo("/batches")}
                        className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-[#f9fbff] p-4 text-left hover:shadow-sm"
                      >
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
                          <Package className="h-5 w-5 text-blue-600" />
                        </div>

                        <div className="flex-1">
                          <p className="font-semibold text-[#092653]">
                            {batch.batch_code}
                          </p>

                          <p className="mt-1 text-xs text-slate-500">
                            Derived: {batch.derived_quantity_kg.toFixed(1)} kg
                          </p>
                        </div>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            batch.status === "ACTIVE"
                              ? "bg-emerald-50 text-emerald-600"
                              : batch.status === "HOLD"
                              ? "bg-amber-50 text-amber-700"
                              : "bg-red-50 text-red-600"
                          }`}
                        >
                          {batch.status}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </section>

            {/* TRACEABILITY WORKFLOW */}
            <section className="group w-full rounded-2xl border border-slate-200/80 bg-white/90 p-6 text-left shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-sm transition hover:-translate-y-0.5 hover:shadow-[0_12px_35px_rgba(245,158,11,0.14)]">
              <div>
                <h3 className="text-xl font-bold text-[#092653]">
                  Traceability Workflow
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  Follow the complete honey traceability journey.
                </p>
              </div>

              <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <WorkflowCard
                  title="Hives"
                  description="Registered hive sources"
                  icon={Hexagon}
                  path="/hives"
                />

                <WorkflowCard
                  title="Telemetry"
                  description="Temperature & humidity"
                  icon={Radio}
                  path="/telemetry"
                />

                <WorkflowCard
                  title="Risk"
                  description="Health risk assessment"
                  icon={ShieldAlert}
                  path="/risk"
                />

                <WorkflowCard
                  title="Traceability"
                  description="Harvest to batch lineage"
                  icon={GitBranch}
                  path="/dashboard/traceability"
                />
              </div>
            </section>

            {/* FOOTER */}
            <div className="mt-8 flex items-center justify-center gap-2 text-xs text-slate-400">
              <CheckCircle2 className="h-4 w-4" />
              Honey Chain Traceability Platform
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}