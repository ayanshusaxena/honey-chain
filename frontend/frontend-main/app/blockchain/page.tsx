"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Blocks,
  ShieldCheck,
  Search,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Copy,
  Check,
  Layers,
  X,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import type {
  BatchResponse,
  BlockchainRecordResponse,
} from "../../types/contracts";

export default function BlockchainPage() {
  const session = useAppSession();

  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string>("");
  const [records, setRecords] = useState<BlockchainRecordResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [registering, setRegistering] = useState(false);
  const [copiedTx, setCopiedTx] = useState<string | null>(null);

  // 1. Load Batches
  useEffect(() => {
    let active = true;
    apiClient
      .get<BatchResponse[]>("/batches")
      .then((data) => {
        if (!active) return;
        const list = data || [];
        setBatches(list);
        if (list.length > 0) {
          setSelectedBatchId(list[0].id);
        } else {
          setLoading(false);
        }
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

  // 2. Load Blockchain Records when selectedBatchId changes
  useEffect(() => {
    if (!selectedBatchId) return;
    let active = true;
    apiClient
      .get<BlockchainRecordResponse[]>(`/batches/${selectedBatchId}/blockchain-records`)
      .then((data) => {
        if (!active) return;
        setRecords(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Failed to load blockchain audit records."
        );
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedBatchId]);

  const reloadData = useCallback(async () => {
    if (!selectedBatchId) return;
    try {
      setError(null);
      setLoading(true);
      const data = await apiClient.get<BlockchainRecordResponse[]>(
        `/batches/${selectedBatchId}/blockchain-records`
      );
      setRecords(data || []);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to load blockchain audit records."
      );
    } finally {
      setLoading(false);
    }
  }, [selectedBatchId]);

  const handleRegisterOnChain = async () => {
    if (!selectedBatchId) return;
    try {
      setRegistering(true);
      setError(null);
      await apiClient.post<BlockchainRecordResponse>(
        `/batches/${selectedBatchId}/blockchain-register`,
        {}
      );
      await reloadData();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to register batch on blockchain contract."
      );
    } finally {
      setRegistering(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTx(id);
    setTimeout(() => setCopiedTx(null), 2000);
  };

  const filteredRecords = useMemo(() => {
    if (!searchQuery.trim()) return records;
    const q = searchQuery.toLowerCase();
    return records.filter(
      (r) =>
        r.event_type.toLowerCase().includes(q) ||
        (r.transaction_hash && r.transaction_hash.toLowerCase().includes(q)) ||
        r.network.toLowerCase().includes(q)
    );
  }, [records, searchQuery]);

  const canRegister =
    !session?.role || session.role === "ADMIN" || session.role === "PROCESSOR";

  const selectedBatch = batches.find((b) => b.id === selectedBatchId);
  const confirmedCount = records.filter((r) => r.status === "CONFIRMED").length;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <AppHeader
          title="Blockchain Ledger & Audit Trail"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Verification" },
            { label: "Blockchain" },
          ]}
          session={session}
          onRefresh={reloadData}
          refreshing={loading}
          actions={
            <div className="flex items-center gap-2">
              {batches.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="hidden text-xs font-semibold text-slate-500 sm:inline dark:text-slate-400">
                    Target Batch:
                  </span>
                  <select
                    value={selectedBatchId}
                    onChange={(e) => setSelectedBatchId(e.target.value)}
                    className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-sm transition focus:border-amber-500 focus:outline-none dark:border-slate-800 dark:bg-[#0c1527] dark:text-slate-200"
                  >
                    {batches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.batch_code} ({b.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {canRegister && (
                <button
                  onClick={handleRegisterOnChain}
                  disabled={registering || !selectedBatchId}
                  className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20 disabled:opacity-50"
                >
                  {registering ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Blocks className="h-4 w-4" />
                  )}
                  <span>Anchor Batch On-Chain</span>
                </button>
              )}
            </div>
          }
        />

        {/* Global Error Banner */}
        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-medium text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800 dark:text-red-400"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Summary Metrics */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="ON-CHAIN RECORDS"
            value={records.length}
            icon={Layers}
            subtitle="Immutable ledger entries"
          />
          <MetricCard
            title="CONFIRMED TRANSACTIONS"
            value={confirmedCount}
            icon={CheckCircle2}
            subtitle="Cryptographic consensus verified"
          />
          <MetricCard
            title="SETTLEMENT NETWORK"
            value="Polygon Amoy"
            icon={Blocks}
            subtitle="EVM Smart Contract Tier"
          />
          <MetricCard
            title="ACTIVE BATCH TARGET"
            value={selectedBatch?.batch_code || "None"}
            icon={ShieldCheck}
            subtitle={selectedBatch ? `Status: ${selectedBatch.status}` : "No batches available"}
          />
        </div>

        {/* Blockchain Ledger Table */}
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-[#0c1527]">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Cryptographic Ledger Transactions
              </h2>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                On-chain proof of batch origin, processing transitions, and certified lab evidence hashes.
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter event or transaction..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-8.5 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-amber-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-200 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                Querying on-chain records...
              </span>
            </div>
          )}

          {!loading && filteredRecords.length === 0 && records.length === 0 && (
            <EmptyState
              icon={Blocks}
              title="No blockchain records found"
              description={
                selectedBatch
                  ? `Batch ${selectedBatch.batch_code} has not yet been registered on-chain.`
                  : "No batches exist in the registry."
              }
              actionLabel={canRegister && selectedBatch ? "Anchor Batch On-Chain" : undefined}
              onAction={canRegister && selectedBatch ? handleRegisterOnChain : undefined}
              className="py-12"
            />
          )}

          {!loading && filteredRecords.length === 0 && records.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No blockchain records match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredRecords.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Event Type</th>
                    <th className="px-5 py-3">Transaction Hash</th>
                    <th className="px-5 py-3">Network</th>
                    <th className="px-5 py-3">Block Number</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredRecords.map((rec) => (
                    <tr
                      key={rec.id}
                      className="transition-colors hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
                    >
                      <td className="px-5 py-3.5 font-bold text-slate-900 dark:text-white">
                        <div className="flex items-center gap-2">
                          <Blocks className="h-4 w-4 text-amber-500" />
                          <span>{rec.event_type}</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5">
                        {rec.transaction_hash ? (
                          <div className="flex items-center gap-1.5">
                            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                              {rec.transaction_hash.slice(0, 10)}...{rec.transaction_hash.slice(-8)}
                            </code>
                            <button
                              onClick={() => copyToClipboard(rec.transaction_hash!, rec.id)}
                              title="Copy transaction hash"
                              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            >
                              {copiedTx === rec.id ? (
                                <Check className="h-3.5 w-3.5 text-emerald-500" />
                              ) : (
                                <Copy className="h-3.5 w-3.5" />
                              )}
                            </button>
                          </div>
                        ) : (
                          <span className="font-mono text-[10px] text-slate-400">Pending Mining</span>
                        )}
                      </td>

                      <td className="px-5 py-3.5 text-slate-600 dark:text-slate-300">
                        {rec.network}
                      </td>

                      <td className="px-5 py-3.5 font-mono text-slate-700 dark:text-slate-300">
                        {rec.block_number ? `#${rec.block_number}` : "—"}
                      </td>

                      <td className="px-5 py-3.5">
                        <StatusBadge
                          status={
                            rec.status === "CONFIRMED"
                              ? "ACTIVE"
                              : rec.status === "FAILED"
                              ? "INACTIVE"
                              : "STALE"
                          }
                        />
                      </td>

                      <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                        {new Date(rec.recorded_at).toLocaleDateString("en-GB", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
