"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Radio,
  Thermometer,
  Droplets,
  Scale,
  CheckCircle2,
  TriangleAlert,
  CircleAlert,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import type {
  HiveResponse,
  TelemetryResponse,
  TelemetryQuality,
} from "../../types/contracts";

function TelemetryContent() {
  const searchParams = useSearchParams();
  const initialHiveId = searchParams.get("hive_id") || "";

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHiveId, setSelectedHiveId] = useState<string>(initialHiveId);
  const [readings, setReadings] = useState<TelemetryResponse[]>([]);
  const [loadingHives, setLoadingHives] = useState(true);
  const [loadingReadings, setLoadingReadings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch hives list on mount
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

  // Fetch telemetry for selected hive
  useEffect(() => {
    if (!selectedHiveId) {
      return;
    }
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
        setError("Failed to reload data.");
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
    latest.humidity_pct <= 75 &&
    latest.quality === "VALID";

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return ts;
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      {/* Header */}
      <div className="mb-8">
        <p className="text-sm font-medium text-amber-600">Honey Chain</p>

        <div className="mt-1 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
            <Radio size={22} />
          </div>

          <h1 className="text-3xl font-bold text-slate-800">Telemetry</h1>
        </div>

        <p className="mt-2 text-sm text-slate-500">
          Monitor temperature, humidity and weight readings from registered hives.
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle size={20} className="shrink-0" />
          <p className="text-sm font-medium">{error}</p>
          <button
            onClick={reloadData}
            className="ml-auto text-xs font-bold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Hive Selection */}
      <div className="mb-7 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label className="text-sm font-bold text-slate-700">Select Hive</label>

        {loadingHives ? (
          <div className="mt-3 flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
            Loading hives...
          </div>
        ) : hives.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No hives registered yet.</p>
        ) : (
          <select
            value={selectedHiveId}
            onChange={(e) => setSelectedHiveId(e.target.value)}
            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition focus:border-amber-400 sm:w-80"
          >
            {hives.map((hive) => (
              <option key={hive.id} value={hive.id}>
                {hive.hive_code} ({hive.location_region})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Current Readings */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <MetricCard
          title="Temperature"
          value={latest ? `${latest.temperature_c.toFixed(1)}°C` : "--"}
          icon={<Thermometer size={24} />}
          description={latest ? "Latest reading" : "No data"}
        />

        <MetricCard
          title="Humidity"
          value={latest ? `${latest.humidity_pct.toFixed(1)}%` : "--"}
          icon={<Droplets size={24} />}
          description={latest ? "Latest reading" : "No data"}
        />

        <MetricCard
          title="Hive Weight"
          value={latest ? `${latest.weight_kg.toFixed(2)} kg` : "--"}
          icon={<Scale size={24} />}
          description={latest ? "Latest reading" : "No data"}
        />
      </div>

      {/* Telemetry Status Banner */}
      {latest && (
        <div
          className={`mb-7 rounded-2xl border p-5 ${
            normal
              ? "border-green-100 bg-green-50"
              : "border-yellow-100 bg-yellow-50"
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full ${
                normal
                  ? "bg-green-100 text-green-600"
                  : "bg-yellow-100 text-yellow-600"
              }`}
            >
              {normal ? (
                <CheckCircle2 size={21} />
              ) : (
                <TriangleAlert size={21} />
              )}
            </div>

            <div>
              <p
                className={`font-bold ${
                  normal ? "text-green-700" : "text-yellow-700"
                }`}
              >
                {normal ? "Telemetry Available" : "Telemetry Requires Review"}
              </p>

              <p
                className={`text-sm ${
                  normal ? "text-green-600" : "text-yellow-600"
                }`}
              >
                Latest reading for {selectedHive?.hive_code || "selected hive"} is{" "}
                {normal ? "within standard thresholds." : `flagged as ${latest.quality}.`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Recent Readings Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">Recent Readings</h2>

          <p className="mt-1 text-sm text-slate-400">
            Temperature, humidity and weight history for{" "}
            {selectedHive?.hive_code || "selected hive"}.
          </p>
        </div>

        {loadingReadings && (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
            <span className="ml-3 text-sm font-medium">Loading telemetry records...</span>
          </div>
        )}

        {!loadingReadings && readings.length === 0 && (
          <div className="p-12 text-center text-slate-400">
            <Radio size={36} className="mx-auto mb-2 text-slate-300" />
            <p className="text-sm font-semibold">No telemetry readings recorded for this hive.</p>
            <p className="mt-1 text-xs text-slate-400">
              Telemetry events from IoT sensors or the simulator will appear here.
            </p>
          </div>
        )}

        {!loadingReadings && readings.length > 0 && (
          <div className="overflow-x-auto p-6">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                  <th className="pb-4">Time</th>
                  <th className="pb-4">Temperature</th>
                  <th className="pb-4">Humidity</th>
                  <th className="pb-4">Weight</th>
                  <th className="pb-4">Quality</th>
                </tr>
              </thead>

              <tbody className="text-sm">
                {readings.map((reading) => (
                  <tr key={reading.id} className="border-b border-slate-50">
                    <td className="py-4 font-semibold text-slate-700">
                      {formatTimestamp(reading.device_timestamp)}
                    </td>

                    <td className="py-4">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Thermometer size={16} />
                        {reading.temperature_c.toFixed(1)}°C
                      </div>
                    </td>

                    <td className="py-4">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Droplets size={16} />
                        {reading.humidity_pct.toFixed(1)}%
                      </div>
                    </td>

                    <td className="py-4">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Scale size={16} />
                        {reading.weight_kg.toFixed(2)} kg
                      </div>
                    </td>

                    <td className="py-4">
                      <QualityBadge quality={reading.quality} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

export default function TelemetryPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    }>
      <TelemetryContent />
    </Suspense>
  );
}

function MetricCard({
  title,
  value,
  icon,
  description,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>

          <h2 className="mt-2 text-3xl font-bold text-slate-800">{value}</h2>

          <p className="mt-2 text-xs text-slate-400">{description}</p>
        </div>

        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

function QualityBadge({
  quality,
}: {
  quality: TelemetryQuality;
}) {
  if (quality === "VALID") {
    return (
      <span className="flex w-fit items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-bold text-green-600">
        <CheckCircle2 size={13} />
        VALID
      </span>
    );
  }

  if (quality === "SUSPECT") {
    return (
      <span className="flex w-fit items-center gap-1.5 rounded-full bg-yellow-50 px-3 py-1 text-xs font-bold text-yellow-600">
        <TriangleAlert size={13} />
        SUSPECT
      </span>
    );
  }

  return (
    <span className="flex w-fit items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-600">
      <CircleAlert size={13} />
      INVALID
    </span>
  );
}