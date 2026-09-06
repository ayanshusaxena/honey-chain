"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Package,
  GitBranch,
  Leaf,
  Hexagon,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "../../../lib/api-client";
import { ApiError } from "../../../lib/errors";
import { useAppSession } from "../../../lib/session-store";
import { AppShell } from "../../../components/layout/AppShell";
import { AppHeader } from "../../../components/layout/AppHeader";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { EmptyState } from "../../../components/ui/EmptyState";
import type { BatchResponse, BatchDetailResponse } from "../../../types/contracts";

function TraceabilityContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const session = useAppSession();
  const initialBatchId = searchParams.get("batch_id") || "";

  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string>(initialBatchId);
  const [batchDetail, setBatchDetail] = useState<BatchDetailResponse | null>(null);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available batches on mount
  useEffect(() => {
    let active = true;
    apiClient
      .get<BatchResponse[]>("/batches")
      .then((data) => {
        if (!active) return;
        const list = data || [];
        setBatches(list);
        if (list.length > 0) {
          const matching = initialBatchId && list.some((b) => b.id === initialBatchId);
          if (matching) {
            setSelectedBatchId(initialBatchId);
          } else {
            setSelectedBatchId((prev) => (prev ? prev : list[0].id));
          }
        }
        setLoadingBatches(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load batches.");
        setLoadingBatches(false);
      });
    return () => {
      active = false;
    };
  }, [initialBatchId]);

  useEffect(() => {
    if (!selectedBatchId) return;
    let active = true;
    apiClient
      .get<BatchDetailResponse>(`/batches/${selectedBatchId}`)
      .then((detail) => {
        if (!active) return;
        setBatchDetail(detail);
        setLoadingDetail(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load batch lineage.");
        setLoadingDetail(false);
      });
    return () => {
      active = false;
    };
  }, [selectedBatchId]);

  const reloadData = useCallback(async () => {
    try {
      setError(null);
      setLoadingBatches(true);
      const data = await apiClient.get<BatchResponse[]>("/batches");
      const list = data || [];
      setBatches(list);
      setLoadingBatches(false);

      const targetId = selectedBatchId || (list.length > 0 ? list[0].id : "");
      if (targetId) {
        setLoadingDetail(true);
        const detail = await apiClient.get<BatchDetailResponse>(`/batches/${targetId}`);
        setBatchDetail(detail);
        setLoadingDetail(false);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to reload traceability lineage.");
      }
      setLoadingBatches(false);
      setLoadingDetail(false);
    }
  }, [selectedBatchId]);

  return (
    <AppShell>
      <div className="space-y-6">
        <AppHeader
          title="Traceability & Lineage Verification"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Verification" },
            { label: "Traceability" },
          ]}
          session={session}
          onRefresh={reloadData}
          refreshing={loadingBatches || loadingDetail}
        />

        {error && (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p className="text-xs font-medium sm:text-sm">{error}</p>
            </div>
            <button
              onClick={reloadData}
              className="rounded-lg bg-red-100 px-3 py-1.5 text-xs font-bold transition hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Batch Selector Bar */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Target Commercial Batch
                </span>
                <p className="text-sm font-bold text-slate-800 dark:text-white">
                  {batchDetail ? batchDetail.batch_code : "Select a batch to verify lineage"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {loadingBatches ? (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                  <span>Loading batches...</span>
                </div>
              ) : batches.length === 0 ? (
                <p className="text-xs text-slate-400">No batches recorded in registry.</p>
              ) : (
                <select
                  value={selectedBatchId}
                  onChange={(e) => {
                    const nextId = e.target.value;
                    setSelectedBatchId(nextId);
                    setLoadingDetail(true);
                    router.replace(`/dashboard/traceability?batch_id=${nextId}`);
                  }}
                  className="h-9 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs font-semibold text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                >
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.batch_code} ({b.status})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>

        {/* Lineage Loading Indicator */}
        {loadingDetail && (
          <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
            <span className="ml-3 text-xs font-medium">Tracing upstream provenance across tiers...</span>
          </div>
        )}

        {/* Empty State */}
        {!loadingDetail && !batchDetail && (
          <div className="rounded-xl border border-slate-200/80 bg-white p-8 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
            <EmptyState
              icon={Package}
              title="No Batch Selected for Traceability"
              description="Select a commercial batch above to inspect full multi-tier provenance from apiaries to bottling."
            />
          </div>
        )}

        {/* Real Upstream Lineage Hierarchy */}
        {!loadingDetail && batchDetail && (
          <div className="space-y-6">
            {/* Tier 1: Commercial Batch Root */}
            <div className="rounded-xl border border-amber-200 bg-amber-50/30 p-5 shadow-sm dark:border-amber-800/50 dark:bg-amber-950/15">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500 text-white shadow-xs">
                    <Package className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                        Tier 1 • Commercial Batch Root
                      </span>
                      <StatusBadge status={batchDetail.status} size="sm" />
                    </div>
                    <h3 className="font-mono text-lg font-bold text-slate-900 dark:text-white">
                      {batchDetail.batch_code}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-slate-400">Derived Volume</span>
                    <p className="font-mono font-bold text-slate-800 dark:text-slate-200">
                      {(batchDetail.derived_quantity_kg || 0).toFixed(1)} kg
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-slate-400">Lifecycle</span>
                    <p className="font-bold text-slate-800 dark:text-slate-200">
                      {batchDetail.is_finalized ? "Finalized" : "Active In-Process"}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Upstream Provenance Tree */}
            <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
              <div className="border-b border-slate-100 pb-3 dark:border-slate-800">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Upstream Lineage Chain (Multi-Tier)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Cryptographically linked chain of custody from regional collection lots to apiaries.
                </p>
              </div>

              {(!batchDetail.collection_lots || batchDetail.collection_lots.length === 0) ? (
                <div className="py-8 text-center text-xs text-slate-500 dark:text-slate-400">
                  <GitBranch className="mx-auto mb-2 h-8 w-8 text-slate-300 dark:text-slate-600" />
                  <p className="font-semibold text-slate-700 dark:text-slate-300">
                    No Upstream Collection Lots Allocated
                  </p>
                  <p className="mt-1">
                    This batch has not yet ingested honey from collection lots. Upstream nodes will populate automatically as allocation events occur.
                  </p>
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  {batchDetail.collection_lots.map((lot) => (
                    <div
                      key={lot.collection_lot_id}
                      className="rounded-lg border border-blue-200/80 bg-blue-50/20 p-4 dark:border-blue-900/40 dark:bg-blue-950/10"
                    >
                      {/* Tier 2: Collection Lot */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <GitBranch className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                          <span className="font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                            Lot: {lot.lot_code}
                          </span>
                          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                            Tier 2
                          </span>
                        </div>
                        <span className="font-mono text-xs font-semibold text-slate-600 dark:text-slate-300">
                          {lot.quantity_used_kg.toFixed(1)} kg allocated
                        </span>
                      </div>

                      {/* Tier 3: Harvests within Lot */}
                      {lot.harvests && lot.harvests.length > 0 ? (
                        <div className="mt-3 space-y-2.5 pl-4 border-l-2 border-blue-200 dark:border-blue-800">
                          {lot.harvests.map((harvest) => (
                            <div
                              key={harvest.harvest_id}
                              className="rounded-md border border-slate-200/60 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
                            >
                              <div className="flex items-center justify-between text-xs">
                                <div className="flex items-center gap-2">
                                  <Leaf className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                                    Harvest: {harvest.harvest_code}
                                  </span>
                                  <span className="rounded bg-emerald-50 px-1 py-0.2 text-[10px] text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                                    Tier 3
                                  </span>
                                </div>
                                <span className="font-mono text-slate-500 dark:text-slate-400">
                                  {harvest.quantity_used_kg.toFixed(1)} kg • {harvest.harvest_date}
                                </span>
                              </div>

                              {/* Tier 4: Hives within Harvest */}
                              {harvest.hives && harvest.hives.length > 0 && (
                                <div className="mt-2 space-y-1 pl-3 border-l border-emerald-200 dark:border-emerald-800">
                                  {harvest.hives.map((hive) => (
                                    <div
                                      key={hive.hive_id}
                                      className="flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400"
                                    >
                                      <div className="flex items-center gap-1.5">
                                        <Hexagon className="h-3 w-3 text-amber-500" />
                                        <span className="font-mono font-semibold">{hive.hive_code}</span>
                                        <span>({hive.location_region})</span>
                                      </div>
                                      <span className="font-mono font-medium">
                                        {hive.quantity_used_kg.toFixed(1)} kg
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 pl-4 text-[11px] text-slate-400">
                          No harvest allocations recorded inside this lot.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function TraceabilityPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-[#070e1e]">
          <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
        </div>
      }
    >
      <TraceabilityContent />
    </Suspense>
  );
}
