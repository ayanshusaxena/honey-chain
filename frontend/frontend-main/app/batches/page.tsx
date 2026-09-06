"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Package,
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
import type { BatchResponse, BatchDetailResponse, BatchStatus } from "../../types/contracts";

export default function BatchesPage() {
  const router = useRouter();
  const session = useAppSession();

  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<BatchDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBatchCode, setNewBatchCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Status transition state
  const [statusUpdating, setStatusUpdating] = useState(false);

  const canCreateBatch = !session?.role || session.role === "ADMIN" || session.role === "PROCESSOR";
  const canUpdateStatus = session?.role === "ADMIN";

  const loadBatches = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      setError(null);
      const data = await apiClient.get<BatchResponse[]>("/batches");
      setBatches(data || []);
      return data || [];
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load processing batches from backend.");
      }
      return [];
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .get<BatchResponse[]>("/batches")
      .then((data) => {
        if (!active) return;
        setBatches(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load batches.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleInspectBatch = async (batchId: string) => {
    try {
      const detail = await apiClient.get<BatchDetailResponse>(`/batches/${batchId}`);
      setSelectedBatch(detail);
    } catch {
      const fallback = batches.find((b) => b.id === batchId);
      if (fallback) {
        setSelectedBatch({
          ...fallback,
          collection_lots: [],
        });
      }
    }
  };

  const handleCreateBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBatchCode.trim()) {
      setModalError("Batch code is required.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);
      await apiClient.post<BatchResponse>("/batches", {
        batch_code: newBatchCode.trim(),
      });

      setIsAddModalOpen(false);
      setNewBatchCode("");
      await loadBatches(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setModalError(err.message);
      } else {
        setModalError(err instanceof Error ? err.message : "Failed to create processing batch.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (batchId: string, newStatus: BatchStatus) => {
    try {
      setStatusUpdating(true);
      const updated = await apiClient.patch<BatchResponse>(`/batches/${batchId}/status`, {
        status: newStatus,
      });
      setBatches((prev) => prev.map((b) => (b.id === batchId ? updated : b)));
      if (selectedBatch && selectedBatch.id === batchId) {
        setSelectedBatch((prev) => (prev ? { ...prev, status: newStatus } : null));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update batch status.");
    } finally {
      setStatusUpdating(false);
    }
  };

  const totalBatches = batches.length;
  const activeBatches = batches.filter((b) => b.status === "ACTIVE").length;
  const derivedVolumeKg = batches.reduce((acc, b) => acc + (b.derived_quantity_kg || 0), 0);

  const filteredBatches = useMemo(() => {
    if (!searchQuery.trim()) return batches;
    const q = searchQuery.toLowerCase();
    return batches.filter(
      (b) =>
        b.batch_code.toLowerCase().includes(q) ||
        b.status.toLowerCase().includes(q)
    );
  }, [batches, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        <AppHeader
          title="Processing Batches"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Processing" },
            { label: "Batches" },
          ]}
          session={session}
          onRefresh={() => loadBatches(true)}
          refreshing={loading}
          actions={
            canCreateBatch ? (
              <button
                onClick={() => {
                  setModalError(null);
                  setIsAddModalOpen(true);
                }}
                className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              >
                <Plus className="h-4 w-4" />
                <span>Create Batch</span>
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
              onClick={() => loadBatches(true)}
              className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-bold transition hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Operational Metrics */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Total Batches"
            value={loading ? "..." : totalBatches}
            subtitle="Processing lifecycle units"
            icon={Package}
            testId="metric-total-batches"
          />

          <MetricCard
            title="Active Batches"
            value={loading ? "..." : activeBatches}
            subtitle="In processing pipeline"
            icon={CheckCircle2}
            iconBg="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
            testId="metric-active-batches"
          />

          <MetricCard
            title="Derived Honey Volume"
            value={loading ? "..." : `${derivedVolumeKg.toFixed(1)} kg`}
            subtitle="Multi-source derived yield"
            icon={Scale}
            iconBg="bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400"
            testId="metric-derived-volume"
          />
        </div>

        {/* Batch Operations Table */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Processing Batch Registry
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                End-to-end commercial batches combining collection lots for bottling and distribution.
              </p>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter batch code or status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-52 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-3 text-xs font-medium">Loading batches from backend...</span>
            </div>
          )}

          {!loading && filteredBatches.length === 0 && batches.length === 0 && (
            <EmptyState
              icon={Package}
              title="No processing batches found"
              description="No batches currently exist in the database. Create a batch to aggregate collection lots for distribution."
              actionLabel={canCreateBatch ? "Create First Batch" : undefined}
              onAction={canCreateBatch ? () => setIsAddModalOpen(true) : undefined}
              className="py-12"
            />
          )}

          {!loading && filteredBatches.length === 0 && batches.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No batches match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredBatches.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Batch Code</th>
                    <th className="px-5 py-3">Derived Yield</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Created Date</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredBatches.map((batch) => {
                    const isSelected = selectedBatch?.id === batch.id;
                    return (
                      <tr
                        key={batch.id}
                        className={`transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50 ${
                          isSelected ? "bg-amber-50/60 dark:bg-amber-950/20" : ""
                        }`}
                      >
                        <td className="px-5 py-3.5 font-mono font-bold text-slate-900 dark:text-white">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                              <Package className="h-4 w-4" />
                            </div>
                            <span>{batch.batch_code}</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                          <div className="flex items-center gap-1.5">
                            <Scale className="h-3.5 w-3.5 text-amber-500" />
                            <span>{(batch.derived_quantity_kg || 0).toFixed(1)} kg</span>
                          </div>
                        </td>

                        <td className="px-5 py-3.5">
                          <StatusBadge status={batch.status} size="sm" />
                        </td>

                        <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400 font-mono">
                          {new Date(batch.created_at).toLocaleDateString([], {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() =>
                                isSelected ? setSelectedBatch(null) : handleInspectBatch(batch.id)
                              }
                              className={`inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11px] font-semibold transition ${
                                isSelected
                                  ? "bg-amber-500 text-white"
                                  : "border border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                              }`}
                            >
                              <Eye className="h-3 w-3" />
                              <span>{isSelected ? "Active" : "Inspect"}</span>
                            </button>

                            <button
                              onClick={() => router.push(`/dashboard/traceability?batch_id=${batch.id}`)}
                              title="Inspect full provenance lineage"
                              className="inline-flex h-7 items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 text-[11px] font-semibold text-amber-700 transition hover:bg-amber-100 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-300"
                            >
                              <span>Trace Lineage ↗</span>
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

        {/* Selected Batch Inspection Card */}
        {selectedBatch && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/20 p-5 shadow-sm dark:border-amber-800/40 dark:bg-amber-950/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white shadow-xs">
                  <Package className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-mono text-base font-bold text-slate-900 dark:text-white">
                      {selectedBatch.batch_code}
                    </h4>
                    <StatusBadge status={selectedBatch.status} size="sm" />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Processing Batch Specifications & Upstream Lineage
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedBatch(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/50 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Derived Volume</span>
                <p className="mt-0.5 font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                  {(selectedBatch.derived_quantity_kg || 0).toFixed(1)} kg
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Processor ID</span>
                <p className="mt-0.5 font-mono text-xs truncate text-slate-700 dark:text-slate-300">
                  {selectedBatch.processor_id}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Upstream Lots</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedBatch.collection_lots && selectedBatch.collection_lots.length > 0
                    ? `${selectedBatch.collection_lots.length} allocated lots`
                    : "No lots allocated yet"}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/60 bg-white p-3 dark:border-slate-800/80 dark:bg-slate-900">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Finalization</span>
                <p className="mt-0.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {selectedBatch.is_finalized ? "Finalized Batch" : "Open for Processing"}
                </p>
              </div>
            </div>

            {/* Admin status update controls */}
            {canUpdateStatus && (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-amber-200/60 pt-3 dark:border-amber-800/40">
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                  Admin Transition:
                </span>
                <button
                  disabled={statusUpdating || selectedBatch.status === "ACTIVE"}
                  onClick={() => handleStatusChange(selectedBatch.id, "ACTIVE")}
                  className="rounded-md border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-bold text-emerald-700 hover:bg-emerald-50 disabled:opacity-40 dark:border-emerald-700 dark:bg-slate-800 dark:text-emerald-300"
                >
                  Set ACTIVE
                </button>
                <button
                  disabled={statusUpdating || selectedBatch.status === "HOLD"}
                  onClick={() => handleStatusChange(selectedBatch.id, "HOLD")}
                  className="rounded-md border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-bold text-amber-700 hover:bg-amber-50 disabled:opacity-40 dark:border-amber-700 dark:bg-slate-800 dark:text-amber-300"
                >
                  Place on HOLD
                </button>
                <button
                  disabled={statusUpdating || selectedBatch.status === "RECALL"}
                  onClick={() => handleStatusChange(selectedBatch.id, "RECALL")}
                  className="rounded-md border border-rose-300 bg-white px-2.5 py-1 text-[11px] font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-40 dark:border-rose-700 dark:bg-slate-800 dark:text-rose-300"
                >
                  Trigger RECALL
                </button>
              </div>
            )}
          </div>
        )}

        {/* Add Batch Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <Package className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Create Processing Batch</h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Initialize a batch for multi-source honey processing.
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

              <form onSubmit={handleCreateBatch} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Processing Batch Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. BATCH-2026-0001"
                    value={newBatchCode}
                    onChange={(e) => setNewBatchCode(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                  <p className="mt-1 text-[10px] text-slate-400">
                    Unique identification code for this processing batch.
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
                        <span>Creating...</span>
                      </>
                    ) : (
                      <>
                        <Plus className="h-3.5 w-3.5" />
                        <span>Create Batch</span>
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
