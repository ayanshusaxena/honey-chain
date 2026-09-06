"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Leaf,
  Scale,
  Calendar,
  CheckCircle2,
  Plus,
  X,
  Eye,
  Loader2,
  AlertCircle,
  Search,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import type { HarvestResponse, HarvestDetailResponse } from "../../types/contracts";

export default function HarvestsPage() {
  const session = useAppSession();

  const [harvests, setHarvests] = useState<HarvestResponse[]>([]);
  const [selectedHarvest, setSelectedHarvest] = useState<HarvestDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newHarvestCode, setNewHarvestCode] = useState("");
  const [newHarvestDate, setNewHarvestDate] = useState(new Date().toISOString().split("T")[0]);
  const [newQuantity, setNewQuantity] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const canAddHarvest = !session?.role || session.role === "ADMIN" || session.role === "BEEKEEPER";

  const loadHarvests = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      setError(null);
      const data = await apiClient.get<HarvestResponse[]>("/harvests");
      setHarvests(data || []);
      return data || [];
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load harvest records from backend.");
      }
      return [];
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .get<HarvestResponse[]>("/harvests")
      .then((data) => {
        if (!active) return;
        setHarvests(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load harvest records.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleInspectHarvest = async (harvestId: string) => {
    try {
      const detail = await apiClient.get<HarvestDetailResponse>(`/harvests/${harvestId}`);
      setSelectedHarvest(detail);
    } catch {
      const fallback = harvests.find((h) => h.id === harvestId);
      if (fallback) {
        setSelectedHarvest({
          ...fallback,
          allocated_quantity_kg: 0,
          hives: [],
        });
      }
    }
  };

  const handleCreateHarvest = async (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseFloat(newQuantity);
    if (!newHarvestCode.trim() || isNaN(qty) || qty <= 0) {
      setModalError("Harvest code and a valid positive quantity are required.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);
      await apiClient.post<HarvestResponse>("/harvests", {
        harvest_code: newHarvestCode.trim(),
        harvest_date: newHarvestDate,
        quantity_kg: qty,
        notes: newNotes.trim() || undefined,
      });

      setIsAddModalOpen(false);
      setNewHarvestCode("");
      setNewQuantity("");
      setNewNotes("");
      await loadHarvests(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setModalError(err.message);
      } else {
        setModalError(err instanceof Error ? err.message : "Failed to record harvest.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const totalHarvests = harvests.length;
  const totalYieldKg = harvests.reduce((acc, h) => acc + (h.quantity_kg || 0), 0);
  const finalizedCount = harvests.filter((h) => h.is_finalized).length;

  const filteredHarvests = useMemo(() => {
    if (!searchQuery.trim()) return harvests;
    const q = searchQuery.toLowerCase();
    return harvests.filter(
      (h) =>
        h.harvest_code.toLowerCase().includes(q) ||
        (h.notes && h.notes.toLowerCase().includes(q))
    );
  }, [harvests, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        <AppHeader
          title="Harvest Registry"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Processing" },
            { label: "Harvests" },
          ]}
          session={session}
          onRefresh={() => loadHarvests(true)}
          refreshing={loading}
          actions={
            canAddHarvest ? (
              <button
                onClick={() => {
                  setModalError(null);
                  setIsAddModalOpen(true);
                }}
                className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              >
                <Plus className="h-4 w-4" />
                <span>Log Harvest</span>
              </button>
            ) : null
          }
        />

        {error && (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p className="text-xs font-medium sm:text-sm">{error}</p>
            </div>
            <button
              onClick={() => loadHarvests(true)}
              className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-bold transition hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Operational Metrics */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Total Harvests"
            value={loading ? "..." : totalHarvests}
            subtitle="Registered collection events"
            icon={Leaf}
            testId="metric-total-harvests"
          />

          <MetricCard
            title="Total Yield"
            value={loading ? "..." : `${totalYieldKg.toFixed(1)} kg`}
            subtitle="Gross raw honey gathered"
            icon={Scale}
            iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
            testId="metric-total-yield"
          />

          <MetricCard
            title="Finalized Collections"
            value={loading ? "..." : finalizedCount}
            subtitle="Locked for lot aggregation"
            icon={CheckCircle2}
            iconBg="bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
            testId="metric-finalized-harvests"
          />
        </div>

        {/* Harvest List Container */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Apiary Harvest Records
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Verified extraction batches collected by registered beekeepers.
              </p>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter harvest code or notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-56 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-3 text-xs font-medium">Loading harvest events from backend...</span>
            </div>
          )}

          {!loading && filteredHarvests.length === 0 && harvests.length === 0 && (
            <EmptyState
              icon={Leaf}
              title="No harvest records found"
              description="No apiary collection events exist in the database. Log your first harvest to initialize batch lineage."
              actionLabel={canAddHarvest ? "Log First Harvest" : undefined}
              onAction={canAddHarvest ? () => setIsAddModalOpen(true) : undefined}
              className="py-12"
            />
          )}

          {!loading && filteredHarvests.length === 0 && harvests.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No harvests match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredHarvests.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Harvest Code</th>
                    <th className="px-5 py-3">Harvest Date</th>
                    <th className="px-5 py-3">Quantity</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredHarvests.map((harvest) => {
                    const isSelected = selectedHarvest?.id === harvest.id;
                    return (
                      <tr
                        key={harvest.id}
                        className={`transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50 ${
                          isSelected ? "bg-amber-50/60 dark:bg-amber-950/20" : ""
                        }`}
                      >
                        <td className="px-5 py-3.5 font-mono font-bold text-slate-900 dark:text-white">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                              <Leaf className="h-4 w-4" />
                            </div>
                            <span>{harvest.harvest_code}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 text-slate-600 dark:text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-slate-400" />
                            <span>{harvest.harvest_date}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                          <div className="flex items-center gap-1.5">
                            <Scale className="h-3.5 w-3.5 text-amber-500" />
                            <span>{harvest.quantity_kg.toFixed(1)} kg</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5">
                          <StatusBadge
                            status={harvest.is_finalized ? "VERIFIED" : "COLLECTED"}
                            size="sm"
                          />
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <button
                            onClick={() =>
                              isSelected
                                ? setSelectedHarvest(null)
                                : handleInspectHarvest(harvest.id)
                            }
                            className={`inline-flex h-7 items-center gap-1 rounded-md px-2.5 text-[11px] font-semibold transition ${
                              isSelected
                                ? "bg-amber-500 text-white"
                                : "border border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            }`}
                          >
                            <Eye className="h-3 w-3" />
                            <span>{isSelected ? "Active" : "Inspect"}</span>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Selected Harvest Inspection Card */}
        {selectedHarvest && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/20 p-5 shadow-sm dark:border-amber-800/40 dark:bg-amber-950/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white shadow-xs">
                  <Leaf className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-mono text-base font-bold text-slate-900 dark:text-white">
                      {selectedHarvest.harvest_code}
                    </h4>
                    <StatusBadge
                      status={selectedHarvest.is_finalized ? "FINALIZED" : "DRAFT"}
                      size="sm"
                    />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Harvest Provenance & Traceability Details
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedHarvest(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/50 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Quantity</span>
                <p className="mt-0.5 font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                  {selectedHarvest.quantity_kg.toFixed(1)} kg
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Harvest Date</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedHarvest.harvest_date}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Allocated to Lots</span>
                <p className="mt-0.5 font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {(selectedHarvest.allocated_quantity_kg || 0).toFixed(1)} kg
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Contributing Hives</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedHarvest.hives && selectedHarvest.hives.length > 0
                    ? `${selectedHarvest.hives.length} apiary units`
                    : "No individual hive allocations recorded"}
                </p>
              </div>
            </div>

            {selectedHarvest.notes && (
              <div className="mt-3 rounded-lg border border-slate-200/60 bg-white p-3 text-xs text-slate-600 dark:border-slate-800/80 dark:bg-slate-900 dark:text-slate-300">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Field Notes:</span>
                <p className="mt-0.5">{selectedHarvest.notes}</p>
              </div>
            )}
          </div>
        )}

        {/* Add Harvest Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <Leaf className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Log New Harvest</h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Record raw honey collection from registered apiaries.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsAddModalOpen(false)}
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

              <form onSubmit={handleCreateHarvest} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Harvest Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. HARV-2026-0001"
                    value={newHarvestCode}
                    onChange={(e) => setNewHarvestCode(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Harvest Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={newHarvestDate}
                    onChange={(e) => setNewHarvestDate(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Yield Quantity (kg) *
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    required
                    placeholder="e.g. 24.5"
                    value={newQuantity}
                    onChange={(e) => setNewQuantity(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Field Notes (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Early spring extraction, floral aroma"
                    value={newNotes}
                    onChange={(e) => setNewNotes(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
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
                        <span>Logging...</span>
                      </>
                    ) : (
                      <>
                        <Plus className="h-3.5 w-3.5" />
                        <span>Log Harvest</span>
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
