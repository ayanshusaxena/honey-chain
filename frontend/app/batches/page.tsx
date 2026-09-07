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
  QrCode,
  ShieldAlert,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import { QrCodeModal } from "../../components/qr/QrCodeModal";
import type {
  BatchResponse,
  BatchDetailResponse,
  BatchStatus,
  PackagingLotResponse,
  PackagingUnit,
  QrTokenMetadataResponse,
} from "../../types/contracts";

export default function BatchesPage() {
  const router = useRouter();
  const session = useAppSession();

  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<BatchDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State for Batch Creation
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newBatchCode, setNewBatchCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Status transition state
  const [statusUpdating, setStatusUpdating] = useState(false);

  // Packaging Lot & QR State for Selected Batch
  const [packagingLots, setPackagingLots] = useState<PackagingLotResponse[]>([]);
  const [qrMetadataMap, setQrMetadataMap] = useState<Record<string, QrTokenMetadataResponse | null>>({});
  const [loadingPackaging, setLoadingPackaging] = useState(false);
  const [actionLoadingLotId, setActionLoadingLotId] = useState<string | null>(null);
  const [qrActionError, setQrActionError] = useState<string | null>(null);

  // Modal State for Packaging Lot Creation
  const [isAddPkgOpen, setIsAddPkgOpen] = useState(false);
  const [newPkgCode, setNewPkgCode] = useState("");
  const [newPkgQty, setNewPkgQty] = useState<number>(100);
  const [newPkgUnit, setNewPkgUnit] = useState<PackagingUnit>("JARS");
  const [newPkgSizeGrams, setNewPkgSizeGrams] = useState<number>(500);
  const [pkgSubmitting, setPkgSubmitting] = useState(false);
  const [pkgError, setPkgError] = useState<string | null>(null);

  // QR Modal for Generated Verification Link
  const [qrModal, setQrModal] = useState<{
    isOpen: boolean;
    url: string;
    lotCode: string;
    batchCode?: string;
  }>({
    isOpen: false,
    url: "",
    lotCode: "",
  });

  const canCreateBatch = !session?.role || session.role === "ADMIN" || session.role === "PROCESSOR";
  const canUpdateStatus = session?.role === "ADMIN";
  const canManagePackaging = session?.role === "ADMIN" || session?.role === "PROCESSOR";
  const canRevokeQr = session?.role === "ADMIN";

  const loadPackagingLots = useCallback(async (batchId: string) => {
    setLoadingPackaging(true);
    setQrActionError(null);
    try {
      const lots = await apiClient.getBatchPackagingLots(batchId);
      setPackagingLots(lots);

      const metaMap: Record<string, QrTokenMetadataResponse | null> = {};
      await Promise.all(
        lots.map(async (lot) => {
          try {
            const meta = await apiClient.getQrTokenMetadata(lot.id);
            metaMap[lot.id] = meta;
          } catch {
            metaMap[lot.id] = null;
          }
        })
      );
      setQrMetadataMap(metaMap);
    } catch {
      setPackagingLots([]);
    } finally {
      setLoadingPackaging(false);
    }
  }, []);

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
      loadPackagingLots(batchId);
    } catch {
      const fallback = batches.find((b) => b.id === batchId);
      if (fallback) {
        setSelectedBatch({
          ...fallback,
          collection_lots: [],
        });
        loadPackagingLots(batchId);
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
        loadPackagingLots(batchId);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update batch status.");
    } finally {
      setStatusUpdating(false);
    }
  };

  // Packaging Lot Submission
  const handleCreatePackagingLot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBatch) return;
    if (!newPkgCode.trim()) {
      setPkgError("Packaging lot code is required.");
      return;
    }
    if (newPkgQty <= 0 || newPkgSizeGrams <= 0) {
      setPkgError("Quantity and package size must be greater than 0.");
      return;
    }

    try {
      setPkgSubmitting(true);
      setPkgError(null);
      await apiClient.createPackagingLot(selectedBatch.id, {
        package_lot_code: newPkgCode.trim(),
        quantity: Number(newPkgQty),
        unit: newPkgUnit,
        package_size_grams: Number(newPkgSizeGrams),
      });

      setIsAddPkgOpen(false);
      setNewPkgCode("");
      await loadPackagingLots(selectedBatch.id);
    } catch (err) {
      if (err instanceof ApiError) {
        setPkgError(err.message);
      } else {
        setPkgError("Failed to create packaging lot.");
      }
    } finally {
      setPkgSubmitting(false);
    }
  };

  // QR Token Generation
  const handleGenerateQr = async (lot: PackagingLotResponse) => {
    if (!selectedBatch) return;
    setActionLoadingLotId(lot.id);
    setQrActionError(null);
    try {
      const res = await apiClient.createQrToken(lot.id);
      setQrMetadataMap((prev) => ({
        ...prev,
        [lot.id]: {
          id: res.id,
          packaging_lot_id: res.packaging_lot_id,
          status: res.status,
          created_at: res.created_at,
        },
      }));

      // Open QR Code Modal with single-use verification URL
      const tokenMatch = res.verification_url.match(/\/verify\/([0-9a-fA-F]{64})/);
      const rawToken = tokenMatch ? tokenMatch[1] : "";
      const consumerUrl =
        typeof window !== "undefined" && rawToken
          ? `${window.location.origin}/verify/${rawToken}`
          : res.verification_url;

      setQrModal({
        isOpen: true,
        url: consumerUrl,
        lotCode: lot.package_lot_code,
        batchCode: selectedBatch.batch_code,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setQrActionError(`Lot ${lot.package_lot_code}: ${err.message}`);
      } else {
        setQrActionError(`Failed to generate QR token for lot ${lot.package_lot_code}.`);
      }
    } finally {
      setActionLoadingLotId(null);
    }
  };

  // Admin QR Revocation
  const handleRevokeQr = async (lotId: string, qrId: string) => {
    if (!confirm("Are you sure you want to revoke this QR verification token?\n\nThis action is TERMINAL and cannot be undone.")) {
      return;
    }

    setActionLoadingLotId(lotId);
    setQrActionError(null);
    try {
      const res = await apiClient.revokeQrToken(qrId);
      setQrMetadataMap((prev) => ({
        ...prev,
        [lotId]: res,
      }));
    } catch (err) {
      if (err instanceof ApiError) {
        setQrActionError(err.message);
      } else {
        setQrActionError("Failed to revoke QR token.");
      }
    } finally {
      setActionLoadingLotId(null);
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
        b.status.toLowerCase().includes(q) ||
        b.id.toLowerCase().includes(q)
    );
  }, [batches, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        <AppHeader
          title="Processing Batches & Packaging"
          session={session}
          onRefresh={() => loadBatches(false)}
          refreshing={loading}
          actions={
            canCreateBatch ? (
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-xs transition hover:bg-amber-600 cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                <span>New Batch</span>
              </button>
            ) : undefined
          }
        />

        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50/80 p-3.5 text-xs font-semibold text-red-600 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {qrActionError && (
          <div className="flex items-center justify-between rounded-xl border border-amber-300 bg-amber-50/90 p-3.5 text-xs font-semibold text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
              <span>{qrActionError}</span>
            </div>
            <button
              onClick={() => setQrActionError(null)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Total Batches"
            value={totalBatches}
            icon={Package}
            subtitle="Registered batches"
          />
          <MetricCard
            title="Active Batches"
            value={activeBatches}
            icon={CheckCircle2}
            subtitle="Ready for distribution"
          />
          <MetricCard
            title="Total Derived Volume"
            value={`${derivedVolumeKg.toFixed(1)} kg`}
            icon={Scale}
            subtitle="Sum of allocated raw yield"
          />
        </div>

        {/* Batches Table Card */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4 dark:border-slate-800">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Batch Registry ({filteredBatches.length})
              </h3>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search batch code or status..."
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
                              className={`inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11px] font-semibold transition cursor-pointer ${
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
                              className="inline-flex h-7 items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 text-[11px] font-semibold text-amber-700 transition hover:bg-amber-100 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-300 cursor-pointer"
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
          <div className="rounded-xl border border-amber-200 bg-amber-50/20 p-5 shadow-sm dark:border-amber-800/40 dark:bg-amber-950/10 space-y-6">
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
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/50 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
              <div className="flex flex-wrap items-center gap-2 border-t border-amber-200/60 pt-3 dark:border-amber-800/40">
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                  Admin Transition:
                </span>
                <button
                  disabled={statusUpdating || selectedBatch.status === "ACTIVE"}
                  onClick={() => handleStatusChange(selectedBatch.id, "ACTIVE")}
                  className="rounded-md border border-emerald-300 bg-white px-2.5 py-1 text-[11px] font-bold text-emerald-700 hover:bg-emerald-50 disabled:opacity-40 dark:border-emerald-700 dark:bg-slate-800 dark:text-emerald-300 cursor-pointer"
                >
                  Set ACTIVE
                </button>
                <button
                  disabled={statusUpdating || selectedBatch.status === "HOLD"}
                  onClick={() => handleStatusChange(selectedBatch.id, "HOLD")}
                  className="rounded-md border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-bold text-amber-700 hover:bg-amber-50 disabled:opacity-40 dark:border-amber-700 dark:bg-slate-800 dark:text-amber-300 cursor-pointer"
                >
                  Place on HOLD
                </button>
                <button
                  disabled={statusUpdating || selectedBatch.status === "RECALL"}
                  onClick={() => handleStatusChange(selectedBatch.id, "RECALL")}
                  className="rounded-md border border-rose-300 bg-white px-2.5 py-1 text-[11px] font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-40 dark:border-rose-700 dark:bg-slate-800 dark:text-rose-300 cursor-pointer"
                >
                  Trigger RECALL
                </button>
              </div>
            )}

            {/* Packaging Lots & QR Verification Section */}
            <div className="border-t border-amber-200/80 pt-4 dark:border-amber-800/60 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                    <Package className="h-4 w-4 text-amber-500" />
                    <span>Packaging Lots & QR Verification</span>
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Consumer package units, single-use 256-bit QR tokens, and verification status.
                  </p>
                </div>

                {canManagePackaging && selectedBatch.is_finalized && selectedBatch.status === "ACTIVE" && (
                  <button
                    onClick={() => setIsAddPkgOpen(true)}
                    className="inline-flex items-center gap-1 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-600 transition shadow-xs cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Add Packaging Lot</span>
                  </button>
                )}
              </div>

              {!selectedBatch.is_finalized && (
                <div className="rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/60">
                  Notice: Packaging lots and QR tokens can only be generated for <strong>Finalized, ACTIVE</strong> batches.
                </div>
              )}

              {loadingPackaging && (
                <div className="flex items-center justify-center p-6 text-xs text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin text-amber-500 mr-2" />
                  <span>Loading packaging lots & QR metadata...</span>
                </div>
              )}

              {!loadingPackaging && packagingLots.length === 0 && selectedBatch.is_finalized && (
                <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  No packaging lots created for this batch yet.
                </div>
              )}

              {!loadingPackaging && packagingLots.length > 0 && (
                <div className="overflow-x-auto rounded-lg border border-slate-200/80 bg-white dark:border-slate-800 dark:bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-100 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:border-slate-800 dark:bg-slate-800/50">
                      <tr>
                        <th className="px-4 py-2.5">Package Lot Code</th>
                        <th className="px-4 py-2.5">Packaging Unit</th>
                        <th className="px-4 py-2.5">Total Packaged</th>
                        <th className="px-4 py-2.5">QR Status</th>
                        <th className="px-4 py-2.5 text-right">QR Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {packagingLots.map((lot) => {
                        const qrMeta = qrMetadataMap[lot.id];
                        const hasQr = qrMeta !== null && qrMeta !== undefined;
                        const isQrActive = qrMeta?.status === "ACTIVE";
                        const isQrRevoked = qrMeta?.status === "REVOKED";
                        const isActionBusy = actionLoadingLotId === lot.id;

                        return (
                          <tr key={lot.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                            <td className="px-4 py-3 font-mono font-bold text-slate-900 dark:text-white">
                              {lot.package_lot_code}
                            </td>
                            <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                              {lot.quantity} {lot.unit} ({lot.package_size_grams}g)
                            </td>
                            <td className="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200">
                              {lot.packaged_quantity_kg.toFixed(1)} kg
                            </td>
                            <td className="px-4 py-3">
                              {!hasQr ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                                  Not Issued
                                </span>
                              ) : isQrActive ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60">
                                  <CheckCircle2 className="h-3 w-3" /> ACTIVE QR
                                </span>
                              ) : isQrRevoked ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60">
                                  <ShieldAlert className="h-3 w-3" /> REVOKED
                                </span>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                {!hasQr ? (
                                  canManagePackaging && selectedBatch.status === "ACTIVE" && (
                                    <button
                                      disabled={isActionBusy}
                                      onClick={() => handleGenerateQr(lot)}
                                      className="inline-flex items-center gap-1 rounded-md bg-amber-500 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-amber-600 disabled:opacity-50 transition shadow-2xs cursor-pointer"
                                    >
                                      {isActionBusy ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <QrCode className="h-3 w-3" />
                                      )}
                                      <span>Generate QR</span>
                                    </button>
                                  )
                                ) : isQrActive ? (
                                  canRevokeQr && (
                                    <button
                                      disabled={isActionBusy}
                                      onClick={() => handleRevokeQr(lot.id, qrMeta.id)}
                                      className="inline-flex items-center gap-1 rounded-md border border-rose-300 bg-white px-2 py-1 text-[11px] font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-800/60 dark:bg-slate-800 dark:text-rose-300 cursor-pointer"
                                    >
                                      {isActionBusy ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <ShieldAlert className="h-3 w-3" />
                                      )}
                                      <span>Revoke</span>
                                    </button>
                                  )
                                ) : (
                                  <span className="text-[10px] text-slate-400 italic">Terminal</span>
                                )}
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
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300 cursor-pointer"
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
                    className="rounded-lg border border-slate-200 px-3.5 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50 cursor-pointer"
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

        {/* Add Packaging Lot Modal */}
        {isAddPkgOpen && selectedBatch && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <Package className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Add Packaging Lot</h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Batch: {selectedBatch.batch_code}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsAddPkgOpen(false)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {pkgError && (
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs font-semibold text-red-600 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{pkgError}</span>
                </div>
              )}

              <form onSubmit={handleCreatePackagingLot} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Package Lot Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. PKG-2026-001"
                    value={newPkgCode}
                    onChange={(e) => setNewPkgCode(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Unit Type *
                    </label>
                    <select
                      value={newPkgUnit}
                      onChange={(e) => setNewPkgUnit(e.target.value as PackagingUnit)}
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    >
                      <option value="JARS">JARS</option>
                      <option value="BOTTLES">BOTTLES</option>
                      <option value="PACKS">PACKS</option>
                      <option value="POUCHES">POUCHES</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Unit Size (grams) *
                    </label>
                    <input
                      type="number"
                      required
                      min={1}
                      step="any"
                      placeholder="e.g. 500"
                      value={newPkgSizeGrams}
                      onChange={(e) => setNewPkgSizeGrams(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Units Quantity *
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    placeholder="e.g. 100"
                    value={newPkgQty}
                    onChange={(e) => setNewPkgQty(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                  />
                  <p className="mt-1 text-[10px] text-slate-400 font-mono">
                    Total yield: {((Number(newPkgQty) * Number(newPkgSizeGrams)) / 1000).toFixed(2)} kg
                  </p>
                </div>

                <div className="mt-6 flex justify-end gap-2.5 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddPkgOpen(false)}
                    className="rounded-lg border border-slate-200 px-3.5 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={pkgSubmitting}
                    className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50 cursor-pointer"
                  >
                    {pkgSubmitting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Creating...</span>
                      </>
                    ) : (
                      <>
                        <Plus className="h-3.5 w-3.5" />
                        <span>Create Packaging Lot</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* QR Code Single-Use Issuance Modal */}
        <QrCodeModal
          isOpen={qrModal.isOpen}
          onClose={() => setQrModal((prev) => ({ ...prev, isOpen: false }))}
          verificationUrl={qrModal.url}
          packageLotCode={qrModal.lotCode}
          batchCode={qrModal.batchCode}
        />
      </div>
    </AppShell>
  );
}
