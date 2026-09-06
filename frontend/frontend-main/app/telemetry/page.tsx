"use client";

import React, { useState, useEffect, useCallback, Suspense, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Radio,
  Thermometer,
  Droplets,
  Scale,
  CheckCircle2,
  TriangleAlert,
  Loader2,
  AlertCircle,
  ShieldAlert,
  Clock,
  Hexagon,
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
import type {
  HiveResponse,
  TelemetryResponse,
} from "../../types/contracts";

function TelemetryContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const session = useAppSession();
  const initialHiveId = searchParams.get("hive_id") || "";

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHiveId, setSelectedHiveId] = useState<string>(initialHiveId);
  const [readings, setReadings] = useState<TelemetryResponse[]>([]);
  const [loadingHives, setLoadingHives] = useState(true);
  const [loadingReadings, setLoadingReadings] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch hives on mount
  useEffect(() => {
    let active = true;
    apiClient
      .get<HiveResponse[]>("/hives")
      .then((data) => {
        if (!active) return;
        const list = data || [];
        setHives(list);
        if (list.length > 0) {
          const matching = initialHiveId && list.some((h) => h.id === initialHiveId);
          if (matching) {
            setSelectedHiveId(initialHiveId);
          } else {
            setSelectedHiveId((prev) => (prev ? prev : list[0].id));
          }
        }
        setLoadingHives(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load hives.");
        setLoadingHives(false);
      });
    return () => {
      active = false;
    };
  }, [initialHiveId]);

  // Fetch telemetry records when selected hive changes
  useEffect(() => {
    if (!selectedHiveId) return;
    let active = true;
    apiClient
      .get<TelemetryResponse[]>("/telemetry", {
        params: { hive_id: selectedHiveId },
      })
      .then((data) => {
        if (!active) return;
        const sorted = (data || []).sort(
          (a, b) =>
            new Date(b.device_timestamp).getTime() -
            new Date(a.device_timestamp).getTime()
        );
        setReadings(sorted);
        setLoadingReadings(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load telemetry readings.");
        setLoadingReadings(false);
      });
    return () => {
      active = false;
    };
  }, [selectedHiveId]);

  const reloadData = useCallback(async () => {
    try {
      setError(null);
      setLoadingHives(true);
      const data = await apiClient.get<HiveResponse[]>("/hives");
      const list = data || [];
      setHives(list);
      setLoadingHives(false);

      const targetId = selectedHiveId || (list.length > 0 ? list[0].id : "");
      if (targetId) {
        setLoadingReadings(true);
        const tData = await apiClient.get<TelemetryResponse[]>("/telemetry", {
          params: { hive_id: targetId },
        });
        const sorted = (tData || []).sort(
          (a, b) =>
            new Date(b.device_timestamp).getTime() -
            new Date(a.device_timestamp).getTime()
        );
        setReadings(sorted);
        setLoadingReadings(false);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to reload telemetry data.");
      }
      setLoadingHives(false);
      setLoadingReadings(false);
    }
  }, [selectedHiveId]);

  const selectedHive = hives.find((h) => h.id === selectedHiveId);
  const latest = readings.length > 0 ? readings[0] : null;

  const normal =
    latest !== null &&
    latest.temperature_c <= 35 &&
    latest.temperature_c >= 28 &&
    latest.humidity_pct <= 75 &&
    latest.quality === "VALID";

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  const filteredReadings = useMemo(() => {
    if (!searchQuery.trim()) return readings;
    const q = searchQuery.toLowerCase();
    return readings.filter((r) =>
      r.quality.toLowerCase().includes(q) ||
      r.temperature_c.toString().includes(q) ||
      r.humidity_pct.toString().includes(q) ||
      r.weight_kg.toString().includes(q)
    );
  }, [readings, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Standardized Header */}
        <AppHeader
          title="Telemetry Stream"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Operations" },
            { label: "Telemetry" },
          ]}
          session={session}
          onRefresh={reloadData}
          refreshing={loadingReadings || loadingHives}
          actions={
            selectedHiveId ? (
              <button
                onClick={() => router.push(`/risk?hive_id=${selectedHiveId}`)}
                className="flex h-9 items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-500/10 px-3 text-xs font-bold text-amber-700 transition hover:bg-amber-500/20 dark:border-amber-700/60 dark:text-amber-300"
              >
                <ShieldAlert className="h-4 w-4" />
                <span>Colony Risk ↗</span>
              </button>
            ) : null
          }
        />

        {/* Global Error Alert */}
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

        {/* Hive Selector Bar */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                <Hexagon className="h-5 w-5" />
              </div>
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Monitored Apiary Unit
                </span>
                <p className="text-sm font-bold text-slate-800 dark:text-white">
                  {selectedHive ? `${selectedHive.hive_code} • ${selectedHive.location_region}` : "Select an apiary"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {loadingHives ? (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                  <span>Loading apiary units...</span>
                </div>
              ) : hives.length === 0 ? (
                <p className="text-xs text-slate-400">No apiaries found in registry.</p>
              ) : (
                <select
                  value={selectedHiveId}
                  onChange={(e) => {
                    const nextId = e.target.value;
                    setSelectedHiveId(nextId);
                    setLoadingReadings(true);
                    router.replace(`/telemetry?hive_id=${nextId}`);
                  }}
                  className="h-9 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs font-semibold text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                >
                  {hives.map((hive) => (
                    <option key={hive.id} value={hive.id}>
                      {hive.hive_code} ({hive.location_region})
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>

        {/* Current Sensor Metric Cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            title="Temperature"
            value={latest ? `${latest.temperature_c.toFixed(1)}°C` : "--"}
            subtitle={latest ? "Internal core probe" : "Awaiting telemetry"}
            icon={Thermometer}
            iconBg="bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400"
            testId="metric-temperature"
          />

          <MetricCard
            title="Relative Humidity"
            value={latest ? `${latest.humidity_pct.toFixed(1)}%` : "--"}
            subtitle={latest ? "Internal hive humidity" : "Awaiting telemetry"}
            icon={Droplets}
            iconBg="bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
            testId="metric-humidity"
          />

          <MetricCard
            title="Gross Hive Weight"
            value={latest ? `${latest.weight_kg.toFixed(2)} kg` : "--"}
            subtitle={latest ? "Scale platform sensor" : "Awaiting telemetry"}
            icon={Scale}
            iconBg="bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400"
            testId="metric-weight"
          />
        </div>

        {/* Telemetry Operational Status Banner */}
        {latest && (
          <div
            className={`rounded-xl border p-4.5 shadow-xs transition-colors ${
              normal
                ? "border-emerald-200 bg-emerald-50/70 dark:border-emerald-900/50 dark:bg-emerald-950/20"
                : "border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20"
            }`}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                    normal
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300"
                  }`}
                >
                  {normal ? <CheckCircle2 size={18} /> : <TriangleAlert size={18} />}
                </div>

                <div>
                  <p
                    className={`text-xs font-bold sm:text-sm ${
                      normal ? "text-emerald-800 dark:text-emerald-300" : "text-amber-800 dark:text-amber-300"
                    }`}
                  >
                    {normal ? "Nominal Telemetry Conditions" : "Telemetry Requires Operational Review"}
                  </p>
                  <p
                    className={`text-xs ${
                      normal ? "text-emerald-700/80 dark:text-emerald-400" : "text-amber-700/80 dark:text-amber-400"
                    }`}
                  >
                    Latest reading for {selectedHive?.hive_code || "selected hive"} is{" "}
                    {normal ? "within standard threshold specifications." : `flagged as ${latest.quality}.`}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                <Clock className="h-3.5 w-3.5 text-slate-400" />
                <span>Device: {formatTimestamp(latest.device_timestamp)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Telemetry Sensor History Table */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Sensor Event Log
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Timestamped environmental telemetry stream from on-hive IoT hardware.
              </p>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter readings..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-48 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:focus:border-amber-400 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loadingReadings && (
            <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-3 text-xs font-medium">Fetching telemetry events from backend...</span>
            </div>
          )}

          {!loadingReadings && filteredReadings.length === 0 && readings.length === 0 && (
            <EmptyState
              icon={Radio}
              title="No telemetry records found"
              description="No sensor packets have been recorded yet for this apiary unit. IoT gateway events will populate here."
              className="py-12"
            />
          )}

          {!loadingReadings && filteredReadings.length === 0 && readings.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No telemetry events match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loadingReadings && filteredReadings.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Device Timestamp</th>
                    <th className="px-5 py-3">Temperature</th>
                    <th className="px-5 py-3">Humidity</th>
                    <th className="px-5 py-3">Weight</th>
                    <th className="px-5 py-3 text-right">Data Quality</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredReadings.map((reading) => (
                    <tr
                      key={reading.id}
                      className="transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50"
                    >
                      <td className="px-5 py-3.5 font-mono text-slate-700 dark:text-slate-300">
                        <div className="flex items-center gap-2">
                          <Clock className="h-3.5 w-3.5 text-slate-400" />
                          <span>{formatTimestamp(reading.device_timestamp)}</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                        <div className="flex items-center gap-1.5">
                          <Thermometer className="h-3.5 w-3.5 text-rose-500" />
                          <span>{reading.temperature_c.toFixed(1)}°C</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                        <div className="flex items-center gap-1.5">
                          <Droplets className="h-3.5 w-3.5 text-blue-500" />
                          <span>{reading.humidity_pct.toFixed(1)}%</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 font-semibold text-slate-800 dark:text-slate-200">
                        <div className="flex items-center gap-1.5">
                          <Scale className="h-3.5 w-3.5 text-amber-500" />
                          <span>{reading.weight_kg.toFixed(2)} kg</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 text-right">
                        <StatusBadge status={reading.quality} size="sm" />
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

export default function TelemetryPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-[#070e1e]">
          <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
        </div>
      }
    >
      <TelemetryContent />
    </Suspense>
  );
}
