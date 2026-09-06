"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Hexagon,
  Package,
  GitBranch,
  Leaf,
  Scale,
  CheckCircle2,
  AlertCircle,
  Activity,
  Layers,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import type {
  HiveResponse,
  BatchResponse,
  CollectionLotResponse,
  HarvestResponse,
} from "../../types/contracts";

export default function AnalyticsPage() {
  const session = useAppSession();

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [lots, setLots] = useState<CollectionLotResponse[]>([]);
  const [harvests, setHarvests] = useState<HarvestResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiClient.get<HiveResponse[]>("/hives").catch(() => []),
      apiClient.get<BatchResponse[]>("/batches").catch(() => []),
      apiClient.get<CollectionLotResponse[]>("/collection-lots").catch(() => []),
      apiClient.get<HarvestResponse[]>("/harvests").catch(() => []),
    ])
      .then(([hivesRes, batchesRes, lotsRes, harvestsRes]) => {
        if (!active) return;
        setHives(hivesRes || []);
        setBatches(batchesRes || []);
        setLots(lotsRes || []);
        setHarvests(harvestsRes || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load platform analytics.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [hivesRes, batchesRes, lotsRes, harvestsRes] = await Promise.all([
        apiClient.get<HiveResponse[]>("/hives").catch(() => []),
        apiClient.get<BatchResponse[]>("/batches").catch(() => []),
        apiClient.get<CollectionLotResponse[]>("/collection-lots").catch(() => []),
        apiClient.get<HarvestResponse[]>("/harvests").catch(() => []),
      ]);
      setHives(hivesRes || []);
      setBatches(batchesRes || []);
      setLots(lotsRes || []);
      setHarvests(harvestsRes || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load platform analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Dynamic calculations from live data
  const totalHives = hives.length;
  const activeHives = hives.filter((h) => h.status === "ACTIVE").length;
  const maintenanceHives = hives.filter((h) => h.status === "MAINTENANCE").length;

  const totalBatches = batches.length;
  const activeBatches = batches.filter((b) => b.status === "ACTIVE").length;
  const holdBatches = batches.filter((b) => b.status === "HOLD").length;
  const recallBatches = batches.filter((b) => b.status === "RECALL").length;

  const totalLots = lots.length;
  const totalHarvests = harvests.length;

  const grossHarvestVolumeKg = harvests.reduce((sum, h) => sum + (h.quantity_kg || 0), 0);
  const grossBatchVolumeKg = batches.reduce((sum, b) => sum + (b.derived_quantity_kg || 0), 0);

  const totalLineageNodes = totalHives + totalHarvests + totalLots + totalBatches;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <AppHeader
          title="Platform Intelligence & Analytics"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Management" },
            { label: "Analytics" },
          ]}
          session={session}
          onRefresh={handleRefresh}
          refreshing={loading}
        />

        {/* Global Error Banner */}
        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-medium text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Summary Metrics */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="TOTAL REGISTERED HIVES"
            value={totalHives}
            icon={Hexagon}
            subtitle={`${activeHives} active, ${maintenanceHives} maintenance`}
          />
          <MetricCard
            title="COMMERCIAL BATCHES"
            value={totalBatches}
            icon={Package}
            subtitle={`${activeBatches} active, ${recallBatches} recall`}
          />
          <MetricCard
            title="SUPPLY CHAIN NODES"
            value={totalLineageNodes}
            icon={Layers}
            subtitle="Across 4 traceability tiers"
          />
          <MetricCard
            title="PROCESSED HONEY MASS"
            value={`${grossBatchVolumeKg.toFixed(1)} kg`}
            icon={Scale}
            subtitle={`${grossHarvestVolumeKg.toFixed(1)} kg raw harvested`}
          />
        </div>

        {/* Analytics Breakdown Grid */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Card 1: Multi-Tier Lineage Inventory */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-[#0c1527]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Traceability Pipeline Inventory
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Live counts of entities anchored across the 4 Honey Chain tiers.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800/60 dark:bg-slate-900/40">
                <div className="flex items-center gap-2.5">
                  <Package className="h-4 w-4 text-amber-500" />
                  <div>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      Tier 1: Commercial Batches
                    </span>
                    <p className="text-[11px] text-slate-400">Bottled distribution units</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                    {totalBatches}
                  </span>
                  <Link
                    href="/batches"
                    className="rounded p-1 text-slate-400 hover:text-amber-500"
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800/60 dark:bg-slate-900/40">
                <div className="flex items-center gap-2.5">
                  <GitBranch className="h-4 w-4 text-blue-500" />
                  <div>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      Tier 2: Collection Lots
                    </span>
                    <p className="text-[11px] text-slate-400">Aggregated extraction volumes</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                    {totalLots}
                  </span>
                  <Link
                    href="/collection-lots"
                    className="rounded p-1 text-slate-400 hover:text-blue-500"
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800/60 dark:bg-slate-900/40">
                <div className="flex items-center gap-2.5">
                  <Leaf className="h-4 w-4 text-emerald-500" />
                  <div>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      Tier 3: Apiary Harvests
                    </span>
                    <p className="text-[11px] text-slate-400">Field collection logs</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                    {totalHarvests}
                  </span>
                  <Link
                    href="/harvests"
                    className="rounded p-1 text-slate-400 hover:text-emerald-500"
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800/60 dark:bg-slate-900/40">
                <div className="flex items-center gap-2.5">
                  <Hexagon className="h-4 w-4 text-amber-600" />
                  <div>
                    <span className="font-bold text-slate-800 dark:text-slate-200">
                      Tier 4: Monitored Apiary Hives
                    </span>
                    <p className="text-[11px] text-slate-400">IoT sensor telemetry points</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                    {totalHives}
                  </span>
                  <Link
                    href="/hives"
                    className="rounded p-1 text-slate-400 hover:text-amber-600"
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Status & Integrity Distribution */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-[#0c1527]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
                  <CheckCircle2 className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Operational Integrity & Health Status
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Health status distributions derived from current database records.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div>
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-slate-700 dark:text-slate-300">Hive Operational Health</span>
                  <span className="text-slate-500 dark:text-slate-400">{totalHives} Total</span>
                </div>
                <div className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    style={{ width: `${totalHives ? (activeHives / totalHives) * 100 : 0}%` }}
                    className="bg-emerald-500"
                    title={`Active: ${activeHives}`}
                  />
                  <div
                    style={{ width: `${totalHives ? (maintenanceHives / totalHives) * 100 : 0}%` }}
                    className="bg-amber-500"
                    title={`Maintenance: ${maintenanceHives}`}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" /> Active ({activeHives})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-amber-500" /> Maintenance ({maintenanceHives})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-slate-400" /> Inactive ({totalHives - activeHives - maintenanceHives})
                  </span>
                </div>
              </div>

              <div className="border-t border-slate-100 pt-3 dark:border-slate-800">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-slate-700 dark:text-slate-300">Processing Batch Compliance</span>
                  <span className="text-slate-500 dark:text-slate-400">{totalBatches} Total</span>
                </div>
                <div className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    style={{ width: `${totalBatches ? (activeBatches / totalBatches) * 100 : 0}%` }}
                    className="bg-emerald-500"
                    title={`Active: ${activeBatches}`}
                  />
                  <div
                    style={{ width: `${totalBatches ? (holdBatches / totalBatches) * 100 : 0}%` }}
                    className="bg-amber-500"
                    title={`Hold: ${holdBatches}`}
                  />
                  <div
                    style={{ width: `${totalBatches ? (recallBatches / totalBatches) * 100 : 0}%` }}
                    className="bg-rose-500"
                    title={`Recall: ${recallBatches}`}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" /> Compliant / Active ({activeBatches})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-amber-500" /> On Hold ({holdBatches})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-rose-500" /> Recalled ({recallBatches})
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
