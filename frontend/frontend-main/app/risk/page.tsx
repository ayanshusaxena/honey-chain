"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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
  Hexagon,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { RiskBadge } from "../../components/ui/RiskBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import type {
  HiveResponse,
  RiskEventResponse,
} from "../../types/contracts";

function RiskContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const session = useAppSession();
  const initialHiveId = searchParams.get("hive_id") || "";

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHiveId, setSelectedHiveId] = useState<string>(initialHiveId);
  const [latestRisk, setLatestRisk] = useState<RiskEventResponse | null>(null);
  const [loadingHives, setLoadingHives] = useState(true);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evalSuccessMsg, setEvalSuccessMsg] = useState<string | null>(null);

  const canEvaluate = !session?.role || session.role === "ADMIN" || session.role === "BEEKEEPER";

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
    if (!selectedHiveId) return;
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
      setEvalSuccessMsg("Automated colony risk evaluation completed successfully.");
      setTimeout(() => setEvalSuccessMsg(null), 4000);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Colony risk evaluation failed.");
      }
    } finally {
      setEvaluating(false);
    }
  };

  const selectedHive = hives.find((h) => h.id === selectedHiveId);

  const formatTimestamp = (ts?: string) => {
    if (!ts) return "N/A";
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

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Standardized Header */}
        <AppHeader
          title="Colony Risk Assessment"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Operations" },
            { label: "Risk Assessment" },
          ]}
          showBack={true}
          backFallbackUrl="/dashboard"
          session={session}
          onRefresh={reloadData}
          refreshing={loadingRisk || loadingHives}
          actions={
            <div className="flex items-center gap-2">
              {selectedHiveId && (
                <button
                  onClick={() => router.push(`/telemetry?hive_id=${selectedHiveId}`)}
                  className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  <Radio className="h-3.5 w-3.5 text-slate-400" />
                  <span className="hidden sm:inline">Telemetry ↗</span>
                </button>
              )}

              {canEvaluate && (
                <button
                  onClick={handleEvaluate}
                  disabled={evaluating || !selectedHiveId}
                  className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20 disabled:opacity-50"
                >
                  {evaluating ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Evaluating...</span>
                    </>
                  ) : (
                    <>
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span>Re-evaluate Risk</span>
                    </>
                  )}
                </button>
              )}
            </div>
          }
        />

        {/* Global Error Banner */}
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

        {/* Success Alert */}
        {evalSuccessMsg && (
          <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-xs font-semibold text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-400">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
            <span>{evalSuccessMsg}</span>
          </div>
        )}

        {/* Hive Selection Control */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
                <Hexagon className="h-5 w-5" />
              </div>
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Target Hive Assessment
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
                <p className="text-xs text-slate-400">No apiaries registered yet.</p>
              ) : (
                <select
                  value={selectedHiveId}
                  onChange={(e) => {
                    const nextId = e.target.value;
                    setSelectedHiveId(nextId);
                    setLoadingRisk(true);
                    router.replace(`/risk?hive_id=${nextId}`);
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

        {/* Loading Indicator */}
        {loadingRisk && (
          <div className="flex items-center justify-center p-12 text-slate-400 dark:text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
            <span className="ml-3 text-xs font-medium">Evaluating telemetry anomalies and risk rules...</span>
          </div>
        )}

        {/* Empty State: No Evaluation Yet */}
        {!loadingRisk && !latestRisk && (
          <div className="rounded-xl border border-slate-200/80 bg-white p-8 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
            <EmptyState
              icon={ShieldAlert}
              title="No Colony Risk Assessment Recorded"
              description={`Apiary unit ${selectedHive?.hive_code || "selected"} has not undergone automated rule evaluation. Trigger evaluation to analyze sensor deviations.`}
              actionLabel={canEvaluate ? "Evaluate Colony Risk Now" : undefined}
              onAction={canEvaluate ? handleEvaluate : undefined}
            />
          </div>
        )}

        {/* Active Risk Evaluation Results */}
        {!loadingRisk && latestRisk && (
          <>
            {/* Primary Risk Metrics */}
            <div className="grid gap-4 sm:grid-cols-3">
              <MetricCard
                title="Colony Risk Score"
                value={latestRisk.risk_score.toFixed(2)}
                subtitle={`${(latestRisk.risk_score * 100).toFixed(0)}% composite anomaly index`}
                icon={Activity}
                testId="metric-risk-score"
              />

              <div className="flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Health Risk Severity
                  </span>
                  <RiskBadge level={latestRisk.risk_level} />
                </div>
                <div className="mt-4">
                  <p className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                    {latestRisk.risk_level}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Rule-engine classification
                  </p>
                </div>
              </div>

              <div className="flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Evaluated Unit
                  </span>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
                    <Hexagon className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4">
                  <p className="font-mono text-xl font-bold text-slate-900 dark:text-white truncate">
                    {selectedHive?.hive_code || selectedHiveId}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {selectedHive?.location_region || "Monitored apiary"}
                  </p>
                </div>
              </div>
            </div>

            {/* Assessment Reason / Anomaly Panel */}
            <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Anomaly Assessment Reason
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Deterministic inference generated from telemetry thresholds and colony indicators.
              </p>

              <div className="mt-4 rounded-lg border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-800/50">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    {latestRisk.risk_level === "LOW" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <ShieldAlert
                        className={`h-5 w-5 ${
                          latestRisk.risk_level === "MEDIUM" ? "text-amber-500" : "text-rose-500"
                        }`}
                      />
                    )}
                  </div>
                  <div>
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                      Rule Evaluation Outcome
                    </span>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                      {latestRisk.reason || "No detailed anomaly reason provided by engine."}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Assessment Provenance Metadata */}
            <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800/90 dark:bg-slate-900/90">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Evaluation Provenance & Architecture
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Audit trail and telemetry linkage metadata for verification.
              </p>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                    <Database size={15} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Evaluation Source
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs font-bold text-slate-800 dark:text-slate-200">
                    {latestRisk.source || "RULE_ENGINE"}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                    <Cpu size={15} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Inference Engine
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs font-bold text-slate-800 dark:text-slate-200">
                    {latestRisk.model_name || "Deterministic Rule Engine"}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                    <Activity size={15} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Rule Version
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs font-bold text-slate-800 dark:text-slate-200">
                    {latestRisk.model_version || "v1.0.0"}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                    <Clock3 size={15} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Evaluated Timestamp
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs font-bold text-slate-800 dark:text-slate-200 truncate">
                    {formatTimestamp(latestRisk.evaluated_at)}
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

export default function RiskPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-[#070e1e]">
          <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
        </div>
      }
    >
      <RiskContent />
    </Suspense>
  );
}
