"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  ShieldAlert,
  CheckCircle2,
  Activity,
  Database,
  Cpu,
  Clock3,
  RotateCcw,
  Radio,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import type {
  HiveResponse,
  RiskEventResponse,
} from "../../types/contracts";

function RiskContent() {
  const searchParams = useSearchParams();
  const initialHiveId = searchParams.get("hive_id") || "";

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHiveId, setSelectedHiveId] = useState<string>(initialHiveId);
  const [latestRisk, setLatestRisk] = useState<RiskEventResponse | null>(null);
  const [loadingHives, setLoadingHives] = useState(true);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evalSuccessMsg, setEvalSuccessMsg] = useState<string | null>(null);

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

  // Fetch risk events for selected hive
  useEffect(() => {
    if (!selectedHiveId) {
      return;
    }
    let active = true;
    apiClient
      .get<RiskEventResponse[]>(`/hives/${selectedHiveId}/risk`)
      .then((data) => {
        if (!active) return;
        if (data && data.length > 0) {
          const sorted = data.sort(
            (a, b) =>
              new Date(b.evaluated_at).getTime() - new Date(a.evaluated_at).getTime()
          );
          setLatestRisk(sorted[0]);
        } else {
          setLatestRisk(null);
        }
        setLoadingRisk(false);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 404) {
          setLatestRisk(null);
        } else {
          setError(err instanceof ApiError ? err.message : "Failed to load risk evaluations.");
        }
        setLoadingRisk(false);
      });
    return () => {
      active = false;
    };
  }, [selectedHiveId]);

  const reloadData = useCallback(async () => {
    try {
      setError(null);
      setEvalSuccessMsg(null);
      setLoadingHives(true);
      const data = await apiClient.get<HiveResponse[]>("/hives");
      const list = data || [];
      setHives(list);
      setLoadingHives(false);

      const targetId = selectedHiveId || (list.length > 0 ? list[0].id : "");
      if (targetId) {
        setLoadingRisk(true);
        const rData = await apiClient.get<RiskEventResponse[]>(`/hives/${targetId}/risk`);
        if (rData && rData.length > 0) {
          const sorted = rData.sort(
            (a, b) =>
              new Date(b.evaluated_at).getTime() - new Date(a.evaluated_at).getTime()
          );
          setLatestRisk(sorted[0]);
        } else {
          setLatestRisk(null);
        }
        setLoadingRisk(false);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setLatestRisk(null);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to reload risk data.");
      }
      setLoadingHives(false);
      setLoadingRisk(false);
    }
  }, [selectedHiveId]);

  // Trigger risk evaluation
  const handleEvaluate = async () => {
    if (!selectedHiveId) return;
    try {
      setEvaluating(true);
      setError(null);
      setEvalSuccessMsg(null);
      const result = await apiClient.post<RiskEventResponse>(
        `/hives/${selectedHiveId}/risk/evaluate`,
        {}
      );
      setLatestRisk(result);
      setEvalSuccessMsg("Risk evaluation completed successfully.");
      setTimeout(() => setEvalSuccessMsg(null), 4000);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Risk evaluation failed.");
      }
    } finally {
      setEvaluating(false);
    }
  };

  const selectedHive = hives.find((h) => h.id === selectedHiveId);

  const levelStyle =
    latestRisk?.risk_level === "LOW"
      ? "bg-green-50 text-green-700 border-green-100"
      : latestRisk?.risk_level === "MEDIUM"
      ? "bg-yellow-50 text-yellow-700 border-yellow-100"
      : latestRisk?.risk_level === "HIGH"
      ? "bg-red-50 text-red-700 border-red-100"
      : "bg-slate-50 text-slate-700 border-slate-200";

  const formatTimestamp = (ts?: string) => {
    if (!ts) return "N/A";
    try {
      const d = new Date(ts);
      return d.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
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
            <ShieldAlert size={22} />
          </div>

          <h1 className="text-3xl font-bold text-slate-800">
            Risk Assessment
          </h1>
        </div>

        <p className="mt-2 text-sm text-slate-500">
          Review telemetry-based hive risk assessments and anomalies.
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

      {/* Success Alert */}
      {evalSuccessMsg && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-green-200 bg-green-50 p-4 text-green-700">
          <CheckCircle2 size={20} className="shrink-0" />
          <p className="text-sm font-medium">{evalSuccessMsg}</p>
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
            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 outline-none focus:border-amber-400 sm:w-80"
          >
            {hives.map((hive) => (
              <option key={hive.id} value={hive.id}>
                {hive.hive_code} ({hive.location_region})
              </option>
            ))}
          </select>
        )}
      </div>

      {loadingRisk && (
        <div className="flex items-center justify-center p-12 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
          <span className="ml-3 text-sm font-medium">Loading risk evaluation...</span>
        </div>
      )}

      {!loadingRisk && !latestRisk && (
        <div className="mb-7 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <ShieldAlert size={40} className="mx-auto mb-3 text-slate-300" />
          <h3 className="text-lg font-bold text-slate-800">
            No Risk Assessment Recorded
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Hive {selectedHive?.hive_code || "selected"} has not been evaluated for risk yet.
          </p>
          <button
            onClick={handleEvaluate}
            disabled={evaluating || !selectedHiveId}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50"
          >
            {evaluating ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Evaluating...
              </>
            ) : (
              <>
                <RotateCcw size={16} />
                Evaluate Risk Now
              </>
            )}
          </button>
        </div>
      )}

      {!loadingRisk && latestRisk && (
        <>
          {/* Risk Score */}
          <div className="mb-7 grid gap-5 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-400">
                    Risk Score
                  </p>

                  <h2 className="mt-2 text-4xl font-bold text-slate-800">
                    {latestRisk.risk_score.toFixed(2)}
                  </h2>

                  <p className="mt-2 text-xs text-slate-400">
                    {(latestRisk.risk_score * 100).toFixed(0)}% risk index (Scale: 0.00 – 1.00)
                  </p>
                </div>

                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                  <Activity size={24} />
                </div>
              </div>
            </div>

            <div className={`rounded-2xl border p-6 ${levelStyle}`}>
              <p className="text-sm font-medium opacity-70">Risk Level</p>

              <h2 className="mt-2 text-3xl font-bold">{latestRisk.risk_level}</h2>

              <p className="mt-2 text-xs opacity-70">Assessment status</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-400">Hive</p>

                  <h2 className="mt-2 text-2xl font-bold text-slate-800">
                    {selectedHive?.hive_code || selectedHiveId}
                  </h2>

                  <p className="mt-2 text-xs text-slate-400">
                    {selectedHive?.location_region || "Monitored hive"}
                  </p>
                </div>

                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-slate-500">
                  <Radio size={24} />
                </div>
              </div>
            </div>
          </div>

          {/* Assessment */}
          <div className="mb-7 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-bold text-slate-800">
                  Risk Assessment
                </h2>

                <p className="mt-1 text-sm text-slate-400">
                  Review the reason and source of the current assessment.
                </p>
              </div>

              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="flex items-center justify-center gap-2 rounded-xl bg-slate-800 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-700 disabled:opacity-50"
              >
                {evaluating ? (
                  <>
                    <Loader2 size={17} className="animate-spin" />
                    Evaluating...
                  </>
                ) : (
                  <>
                    <RotateCcw size={17} />
                    Re-evaluate
                  </>
                )}
              </button>
            </div>

            <div className="mt-6 rounded-xl bg-slate-50 p-5">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 text-amber-600">
                  {latestRisk.risk_level === "LOW" ? (
                    <CheckCircle2 size={22} className="text-green-600" />
                  ) : (
                    <ShieldAlert
                      size={22}
                      className={
                        latestRisk.risk_level === "MEDIUM"
                          ? "text-yellow-600"
                          : "text-red-600"
                      }
                    />
                  )}
                </div>

                <div>
                  <p className="font-bold text-slate-800">Assessment Reason</p>

                  <p className="mt-1 text-sm text-slate-500">
                    {latestRisk.reason || "No detailed anomaly reason provided."}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Assessment Metadata */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5">
              <h2 className="text-lg font-bold text-slate-800">
                Assessment Details
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Metadata associated with this risk evaluation.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <InfoCard
                icon={<Database size={18} />}
                label="Source"
                value={latestRisk.source || "RULE_ENGINE"}
              />

              <InfoCard
                icon={<Cpu size={18} />}
                label="Model"
                value={latestRisk.model_name || "N/A"}
              />

              <InfoCard
                icon={<Activity size={18} />}
                label="Version"
                value={latestRisk.model_version || "N/A"}
              />

              <InfoCard
                icon={<Clock3 size={18} />}
                label="Evaluated At"
                value={formatTimestamp(latestRisk.evaluated_at)}
              />
            </div>
          </div>
        </>
      )}
    </main>
  );
}

export default function RiskPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    }>
      <RiskContent />
    </Suspense>
  );
}

function InfoCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <div className="flex items-center gap-2 text-amber-600">
        {icon}

        <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
          {label}
        </p>
      </div>

      <p className="mt-3 font-bold text-slate-700">{value}</p>
    </div>
  );
}