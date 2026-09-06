"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Hexagon,
  CheckCircle2,
  TriangleAlert,
  X,
  Radio,
  ShieldAlert,
  Eye,
  Plus,
  Loader2,
  AlertCircle,
  Search,
  ExternalLink,
  MapPin,
  UserCheck,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import type { HiveResponse } from "../../types/contracts";

export default function HivesPage() {
  const router = useRouter();
  const session = useAppSession();

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHive, setSelectedHive] = useState<HiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "ACTIVE" | "MAINTENANCE">("ALL");

  // Add Hive modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newHiveCode, setNewHiveCode] = useState("");
  const [newRegion, setNewRegion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const canAddHive = !session?.role || session.role === "ADMIN" || session.role === "BEEKEEPER";

  const loadHives = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      setError(null);
      const data = await apiClient.get<HiveResponse[]>("/hives");
      setHives(data || []);
      return data || [];
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load hives from backend.");
      }
      return [];
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .get<HiveResponse[]>("/hives")
      .then((data) => {
        if (!active) return;
        setHives(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load hives from backend.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreateHive = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHiveCode.trim() || !newRegion.trim()) {
      setModalError("Hive code and region are required.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);
      const created = await apiClient.post<HiveResponse>("/hives", {
        hive_code: newHiveCode.trim(),
        location_region: newRegion.trim(),
      });
      setIsAddModalOpen(false);
      setNewHiveCode("");
      setNewRegion("");
      await loadHives(false);
      setSelectedHive(created);
    } catch (err) {
      if (err instanceof ApiError) {
        setModalError(err.message);
      } else {
        setModalError(err instanceof Error ? err.message : "Failed to create hive.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Metrics
  const totalHives = hives.length;
  const activeHives = hives.filter((h) => h.status === "ACTIVE").length;
  const maintenanceHives = hives.filter((h) => h.status === "MAINTENANCE").length;

  // Filtered hives
  const filteredHives = useMemo(() => {
    return hives.filter((hive) => {
      const matchesSearch =
        hive.hive_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        hive.location_region.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (hive.beekeeper?.name && hive.beekeeper.name.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus =
        statusFilter === "ALL" || hive.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [hives, searchQuery, statusFilter]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header with Breadcrumbs, Back, Title, Refresh, Theme Toggle & Add Action */}
        <AppHeader
          title="Hive Registry"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Operations" },
            { label: "Hives" },
          ]}
          session={session}
          onRefresh={() => loadHives(true)}
          refreshing={loading}
          actions={
            canAddHive ? (
              <button
                onClick={() => {
                  setModalError(null);
                  setIsAddModalOpen(true);
                }}
                className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              >
                <Plus className="h-4 w-4" />
                <span>Add Hive</span>
              </button>
            ) : null
          }
        />

        {/* Global Error Banner with Retry */}
        {error && (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p className="text-xs font-medium sm:text-sm">{error}</p>
            </div>
            <button
              onClick={() => loadHives(true)}
              className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-bold transition hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Operational Metrics Cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Total Hives"
            value={loading ? "..." : totalHives}
            subtitle="Registered apiaries"
            icon={Hexagon}
            testId="metric-total-hives"
          />

          <MetricCard
            title="Active Hives"
            value={loading ? "..." : activeHives}
            subtitle="Healthy operational status"
            icon={CheckCircle2}
            iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
            testId="metric-active-hives"
          />

          <MetricCard
            title="Maintenance"
            value={loading ? "..." : maintenanceHives}
            subtitle="Requires inspection"
            icon={TriangleAlert}
            iconBg="bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400"
            testId="metric-maintenance-hives"
          />
        </div>

        {/* Main Hives Container */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          {/* Controls Bar */}
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Registered Apiary Units
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Live backend records from Postgres database.
              </p>
            </div>

            {/* Filter & Search controls */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter hive code or region..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-8.5 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                />
              </div>

              <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-semibold dark:border-slate-700 dark:bg-slate-800">
                <button
                  onClick={() => setStatusFilter("ALL")}
                  className={`rounded-md px-2.5 py-1 transition ${statusFilter === "ALL" ? "bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-white" : "text-slate-500 hover:text-slate-700 dark:text-slate-400"}`}
                >
                  All
                </button>
                <button
                  onClick={() => setStatusFilter("ACTIVE")}
                  className={`rounded-md px-2.5 py-1 transition ${statusFilter === "ACTIVE" ? "bg-white text-emerald-700 shadow-xs dark:bg-slate-700 dark:text-emerald-400" : "text-slate-500 hover:text-slate-700 dark:text-slate-400"}`}
                >
                  Active
                </button>
                <button
                  onClick={() => setStatusFilter("MAINTENANCE")}
                  className={`rounded-md px-2.5 py-1 transition ${statusFilter === "MAINTENANCE" ? "bg-white text-amber-700 shadow-xs dark:bg-slate-700 dark:text-amber-400" : "text-slate-500 hover:text-slate-700 dark:text-slate-400"}`}
                >
                  Maintenance
                </button>
              </div>
            </div>
          </div>

          {/* Table / List Body */}
          {loading && (
            <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-3 text-xs font-medium">Loading live hive records from backend...</span>
            </div>
          )}

          {!loading && filteredHives.length === 0 && hives.length === 0 && (
            <EmptyState
              icon={Hexagon}
              title="No registered hives found"
              description="No apiaries currently exist in the database. Click 'Add Hive' to register your first colony."
              actionLabel={canAddHive ? "Register First Hive" : undefined}
              onAction={canAddHive ? () => setIsAddModalOpen(true) : undefined}
            />
          )}

          {!loading && filteredHives.length === 0 && hives.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No hives match the current search filter &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredHives.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Hive Code</th>
                    <th className="px-5 py-3">Region</th>
                    <th className="px-5 py-3">Beekeeper / Owner</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredHives.map((hive) => {
                    const isSelected = selectedHive?.id === hive.id;
                    const beekeeperDisplay =
                      hive.beekeeper?.name ||
                      (hive.beekeeper_id ? `Beekeeper (${hive.beekeeper_id.slice(0, 8)})` : "Unassigned");

                    return (
                      <tr
                        key={hive.id}
                        className={`transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50 ${isSelected ? "bg-amber-50/60 dark:bg-amber-950/20" : ""}`}
                      >
                        <td className="px-5 py-3.5 font-mono font-bold text-slate-900 dark:text-white">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                              <Hexagon className="h-4 w-4" />
                            </div>
                            <span>{hive.hive_code}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 text-slate-600 dark:text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                            <span>{hive.location_region}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 text-slate-600 dark:text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <UserCheck className="h-3.5 w-3.5 text-slate-400" />
                            <span>{beekeeperDisplay}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5">
                          <StatusBadge status={hive.status} size="sm" />
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => setSelectedHive(isSelected ? null : hive)}
                              title="Inspect hive details"
                              className={`flex h-7 items-center gap-1 rounded-md px-2 text-[11px] font-semibold transition ${isSelected ? "bg-amber-500 text-white" : "border border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"}`}
                            >
                              <Eye className="h-3 w-3" />
                              <span>{isSelected ? "Active" : "Inspect"}</span>
                            </button>

                            <button
                              onClick={() => router.push(`/telemetry?hive_id=${hive.id}`)}
                              title="Jump to Telemetry stream"
                              className="flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-[11px] font-semibold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-amber-700 dark:hover:bg-amber-950/40 dark:hover:text-amber-300"
                            >
                              <Radio className="h-3 w-3" />
                              <span className="hidden sm:inline">Telemetry</span>
                            </button>

                            <button
                              onClick={() => router.push(`/risk?hive_id=${hive.id}`)}
                              title="Jump to Risk Assessment"
                              className="flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-[11px] font-semibold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-amber-700 dark:hover:bg-amber-950/40 dark:hover:text-amber-300"
                            >
                              <ShieldAlert className="h-3 w-3" />
                              <span className="hidden sm:inline">Risk</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Selected Hive Detail Inspection Card */}
        {selectedHive && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/20 p-5 shadow-sm dark:border-amber-800/40 dark:bg-amber-950/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white shadow-xs">
                  <Hexagon className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-mono text-base font-bold text-slate-900 dark:text-white">
                      {selectedHive.hive_code}
                    </h4>
                    <StatusBadge status={selectedHive.status} size="sm" />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Inspection view for registered apiary unit
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedHive(null)}
                aria-label="Close detail panel"
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/50 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Hive ID</span>
                <p className="mt-0.5 truncate font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {selectedHive.id}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Location Region</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {selectedHive.location_region}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Beekeeper Owner</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {selectedHive.beekeeper?.name || selectedHive.beekeeper_id || "Unassigned"}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Status</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {selectedHive.status}
                </p>
              </div>
            </div>

            {/* Jump Actions */}
            <div className="mt-4 flex flex-wrap items-center gap-2.5 pt-1">
              <button
                onClick={() => router.push(`/telemetry?hive_id=${selectedHive.id}`)}
                className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700"
              >
                <Radio className="h-3.5 w-3.5" />
                <span>Live Telemetry Stream</span>
                <ExternalLink className="ml-1 h-3 w-3 text-slate-400" />
              </button>

              <button
                onClick={() => router.push(`/risk?hive_id=${selectedHive.id}`)}
                className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3.5 py-2 text-xs font-bold text-amber-700 shadow-xs transition hover:bg-amber-50 dark:border-amber-700/60 dark:bg-slate-900 dark:text-amber-300 dark:hover:bg-amber-950/40"
              >
                <ShieldAlert className="h-3.5 w-3.5" />
                <span>Assess Colony Risk</span>
                <ExternalLink className="ml-1 h-3 w-3 text-amber-500" />
              </button>
            </div>
          </div>
        )}

        {/* Add Hive Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <Hexagon className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Register New Hive</h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Add a new bee colony unit to the cryptographic registry.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsAddModalOpen(false)}
                  aria-label="Close modal"
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {modalError && (
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs font-semibold text-red-600 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              <form onSubmit={handleCreateHive} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Hive Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. HIVE-0005"
                    value={newHiveCode}
                    onChange={(e) => setNewHiveCode(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                  <p className="mt-1 text-[10px] text-slate-400">
                    Unique identifier for the hive box (e.g. HIVE-0001, HIVE-0002).
                  </p>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Location Region *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Gwalior"
                    value={newRegion}
                    onChange={(e) => setNewRegion(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                  <p className="mt-1 text-[10px] text-slate-400">
                    Geographic region or district where the apiary is situated.
                  </p>
                </div>

                <div className="mt-6 flex justify-end gap-2.5 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddModalOpen(false)}
                    className="rounded-lg border border-slate-200 px-3.5 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Registering...</span>
                      </>
                    ) : (
                      <>
                        <Plus className="h-3.5 w-3.5" />
                        <span>Register Hive</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
