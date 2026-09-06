"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  GitBranch,
  Scale,
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
import type { CollectionLotResponse, CollectionLotDetailResponse } from "../../types/contracts";

export default function CollectionLotsPage() {
  const session = useAppSession();

  const [lots, setLots] = useState<CollectionLotResponse[]>([]);
  const [selectedLot, setSelectedLot] = useState<CollectionLotDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newLotCode, setNewLotCode] = useState("");
  const [newQuantity, setNewQuantity] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const canCreateLot = !session?.role || session.role === "ADMIN" || session.role === "PROCESSOR";

  const loadLots = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      setError(null);
      const data = await apiClient.get<CollectionLotResponse[]>("/collection-lots");
      setLots(data || []);
      return data || [];
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load collection lots from backend.");
      }
      return [];
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .get<CollectionLotResponse[]>("/collection-lots")
      .then((data) => {
        if (!active) return;
        setLots(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load collection lots.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleInspectLot = async (lotId: string) => {
    try {
      const detail = await apiClient.get<CollectionLotDetailResponse>(`/collection-lots/${lotId}`);
      setSelectedLot(detail);
    } catch {
      const fallback = lots.find((l) => l.id === lotId);
      if (fallback) {
        setSelectedLot({
          ...fallback,
          allocated_quantity_kg: 0,
          harvests: [],
        });
      }
    }
  };

  const handleCreateLot = async (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseFloat(newQuantity);
    if (!newLotCode.trim() || isNaN(qty) || qty <= 0) {
      setModalError("Lot code and a valid positive quantity are required.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);
      await apiClient.post<CollectionLotResponse>("/collection-lots", {
        lot_code: newLotCode.trim(),
        quantity_kg: qty,
      });

      setIsAddModalOpen(false);
      setNewLotCode("");
      setNewQuantity("");
      await loadLots(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setModalError(err.message);
      } else {
        setModalError(err instanceof Error ? err.message : "Failed to create collection lot.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const totalLots = lots.length;
  const totalVolumeKg = lots.reduce((acc, l) => acc + (l.quantity_kg || 0), 0);
  const finalizedLotsCount = lots.filter((l) => l.is_finalized).length;

  const filteredLots = useMemo(() => {
    if (!searchQuery.trim()) return lots;
    const q = searchQuery.toLowerCase();
    return lots.filter((l) => l.lot_code.toLowerCase().includes(q));
  }, [lots, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        <AppHeader
          title="Collection Lots"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Processing" },
            { label: "Collection Lots" },
          ]}
          session={session}
          onRefresh={() => loadLots(true)}
          refreshing={loading}
          actions={
            canCreateLot ? (
              <button
                onClick={() => {
                  setModalError(null);
                  setIsAddModalOpen(true);
                }}
                className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              >
                <Plus className="h-4 w-4" />
                <span>Create Lot</span>
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
              onClick={() => loadLots(true)}
              className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-bold transition hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Operational Metrics */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Total Lots"
            value={loading ? "..." : totalLots}
            subtitle="Aggregated intake pools"
            icon={GitBranch}
            testId="metric-total-lots"
          />

          <MetricCard
            title="Aggregated Volume"
            value={loading ? "..." : `${totalVolumeKg.toFixed(1)} kg`}
            subtitle="Raw honey pooled in lots"
            icon={Scale}
            iconBg="bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
            testId="metric-total-volume"
          />

          <MetricCard
            title="Finalized Lots"
            value={loading ? "..." : finalizedLotsCount}
            subtitle="Ready for batch processing"
            icon={CheckCircle2}
            iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
            testId="metric-finalized-lots"
          />
        </div>

        {/* Lots Registry Table */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Collection Lot Aggregations
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Bulk intake lots grouping multiple verified apiary harvests.
              </p>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter lot code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-52 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-3 text-xs font-medium">Loading collection lots from backend...</span>
            </div>
          )}

          {!loading && filteredLots.length === 0 && lots.length === 0 && (
            <EmptyState
              icon={GitBranch}
              title="No collection lots found"
              description="No aggregation lots exist in the database. Create a lot to group apiary harvests for batch processing."
              actionLabel={canCreateLot ? "Create First Lot" : undefined}
              onAction={canCreateLot ? () => setIsAddModalOpen(true) : undefined}
              className="py-12"
            />
          )}

          {!loading && filteredLots.length === 0 && lots.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No collection lots match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredLots.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Lot Code</th>
                    <th className="px-5 py-3">Declared Quantity</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Created</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredLots.map((lot) => {
                    const isSelected = selectedLot?.id === lot.id;
                    return (
                      <tr
                        key={lot.id}
                        className={`transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50 ${
                          isSelected ? "bg-amber-50/60 dark:bg-amber-950/20" : ""
                        }`}
                      >
                        <td className="px-5 py-3.5 font-mono font-bold text-slate-900 dark:text-white">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400">
                              <GitBranch className="h-4 w-4" />
                            </div>
                            <span>{lot.lot_code}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                          <div className="flex items-center gap-1.5">
                            <Scale className="h-3.5 w-3.5 text-blue-500" />
                            <span>{lot.quantity_kg.toFixed(1)} kg</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5">
                          <StatusBadge
                            status={lot.is_finalized ? "VERIFIED" : "PROCESSING"}
                            size="sm"
                          />
                        </td>

                        <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400 font-mono">
                          {new Date(lot.created_at).toLocaleDateString([], {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <button
                            onClick={() =>
                              isSelected ? setSelectedLot(null) : handleInspectLot(lot.id)
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

        {/* Selected Lot Inspection Card */}
        {selectedLot && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/20 p-5 shadow-sm dark:border-blue-900/40 dark:bg-blue-950/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500 text-white shadow-xs">
                  <GitBranch className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-mono text-base font-bold text-slate-900 dark:text-white">
                      {selectedLot.lot_code}
                    </h4>
                    <StatusBadge
                      status={selectedLot.is_finalized ? "FINALIZED" : "INTAKE"}
                      size="sm"
                    />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Collection Lot Aggregation & Contributing Harvests
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedLot(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/50 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Lot Volume</span>
                <p className="mt-0.5 font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                  {selectedLot.quantity_kg.toFixed(1)} kg
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Allocated Quantity</span>
                <p className="mt-0.5 font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {(selectedLot.allocated_quantity_kg || 0).toFixed(1)} kg
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Contributing Harvests</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedLot.harvests && selectedLot.harvests.length > 0
                    ? `${selectedLot.harvests.length} harvest allocations`
                    : "No individual harvest allocations linked"}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Lot Status</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedLot.is_finalized ? "Finalized / Locked" : "Open for Allocations"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Add Lot Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <GitBranch className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Create Collection Lot</h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Pool honey harvests into an aggregate lot.
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

              <form onSubmit={handleCreateLot} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Collection Lot Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. LOT-2026-0001"
                    value={newLotCode}
                    onChange={(e) => setNewLotCode(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Declared Lot Capacity (kg) *
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    required
                    placeholder="e.g. 100.0"
                    value={newQuantity}
                    onChange={(e) => setNewQuantity(e.target.value)}
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
                        <span>Creating...</span>
                      </>
                    ) : (
                      <>
                        <Plus className="h-3.5 w-3.5" />
                        <span>Create Lot</span>
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
