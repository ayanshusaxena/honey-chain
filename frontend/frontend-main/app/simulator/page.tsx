"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Cpu,
  Play,
  CheckCircle2,
  AlertTriangle,
  Radio,
  ShieldAlert,
  Loader2,
  ExternalLink,
  Thermometer,
  Droplets,
  Scale,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  Database,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { RiskBadge } from "../../components/ui/RiskBadge";
import type { HiveResponse } from "../../types/contracts";

interface ScenarioInfo {
  id: string;
  label: string;
  description: string;
}

interface SimulatorRunResponse {
  hive_id: string;
  hive_code: string;
  scenario: string;
  temperature_c: number;
  humidity_pct: number;
  weight_kg: number;
  quality: string;
  device_timestamp: string;
  telemetry_id: string | null;
  ingestion_status: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | null;
  risk_score: number | null;
  risk_reasons: string[];
  recommended_action: string | null;
  simulated: boolean;
}

const DEFAULT_SCENARIOS: ScenarioInfo[] = [
  {
    id: "NORMAL",
    label: "NORMAL",
    description: "Stable nominal readings within standard hive comfort envelope.",
  },
  {
    id: "TEMP_ANOMALY",
    label: "TEMP_ANOMALY",
    description: "Elevated brood nest temperature condition (heat stress).",
  },
  {
    id: "HUMIDITY_ANOMALY",
    label: "HUMIDITY_ANOMALY",
    description: "Elevated moisture level condition (condensation risk).",
  },
  {
    id: "WEIGHT_DROP",
    label: "WEIGHT_DROP",
    description: "Rapid hive weight decrease indicating potential swarming or honey depletion.",
  },
  {
    id: "COMBINED",
    label: "COMBINED",
    description: "Multiple simultaneous anomalous telemetry signals across temperature, humidity, and weight.",
  },
];

export default function SimulatorPage() {
  const router = useRouter();
  const session = useAppSession();

  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHiveId, setSelectedHiveId] = useState<string>("");
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>(DEFAULT_SCENARIOS);
  const [selectedScenario, setSelectedScenario] = useState<string>("COMBINED");
  const [seed, setSeed] = useState<number>(42);

  const [running, setRunning] = useState<boolean>(false);
  const [lastResult, setLastResult] = useState<SimulatorRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Load available hives and scenarios
  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [hivesData, scenData] = await Promise.allSettled([
        apiClient.get<HiveResponse[]>("/hives"),
        apiClient.get<{ scenarios: ScenarioInfo[] }>("/demo/simulator/scenarios"),
      ]);

      if (hivesData.status === "fulfilled" && hivesData.value) {
        setHives(hivesData.value);
        if (hivesData.value.length > 0 && !selectedHiveId) {
          setSelectedHiveId(hivesData.value[0].id);
        }
      }

      if (scenData.status === "fulfilled" && scenData.value?.scenarios) {
        setScenarios(scenData.value.scenarios);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to initialize simulator controls.");
      }
    } finally {
      setLoading(false);
    }
  }, [selectedHiveId]);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      apiClient.get<HiveResponse[]>("/hives"),
      apiClient.get<{ scenarios: ScenarioInfo[] }>("/demo/simulator/scenarios"),
    ])
      .then(([hivesData, scenData]) => {
        if (!active) return;
        if (hivesData.status === "fulfilled" && hivesData.value) {
          setHives(hivesData.value);
          if (hivesData.value.length > 0) {
            setSelectedHiveId((prev) => prev || (hivesData.value ? hivesData.value[0].id : ""));
          }
        }
        if (scenData.status === "fulfilled" && scenData.value?.scenarios) {
          setScenarios(scenData.value.scenarios);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError("Failed to initialize simulator controls.");
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleRunSimulation = async () => {
    if (!selectedHiveId) {
      setError("Please select a target hive.");
      return;
    }

    try {
      setRunning(true);
      setError(null);

      const res = await apiClient.post<SimulatorRunResponse>("/demo/simulator/run", {
        hive_id: selectedHiveId,
        scenario: selectedScenario,
        seed: Number(seed) || 42,
        ingest: true,
      });

      setLastResult(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to run simulation.");
      }
    } finally {
      setRunning(false);
    }
  };

  const selectedHive = hives.find((h) => h.id === selectedHiveId);
  const selectedScenarioInfo = scenarios.find((s) => s.id === selectedScenario);

  const isAdmin = !session?.role || session.role === "ADMIN";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <AppHeader
          title="IoT Simulator"
          session={session}
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Management" },
            { label: "IoT Simulator" },
          ]}
          showBack={false}
          onRefresh={loadInitialData}
        />

        {/* Role Access Guard */}
        {!isAdmin ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-8 text-center dark:border-amber-900/30 dark:bg-amber-950/20">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500 text-white shadow-md">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
              Administrator Privileges Required
            </h3>
            <p className="mx-auto mt-2 max-w-md text-xs text-slate-600 dark:text-slate-400">
              The IoT Telemetry Simulator is a privileged demonstration control surface reserved exclusively for Platform Administrators.
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              Return to Dashboard
            </button>
          </div>
        ) : (
          <>
            {/* Notice Banner */}
            <div className="flex items-center gap-3 rounded-xl border border-blue-200/80 bg-blue-50/70 px-4 py-3 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-200">
              <Sparkles className="h-4 w-4 shrink-0 text-amber-500" />
              <div className="flex-1">
                <span className="font-bold uppercase tracking-wider text-[11px] text-blue-700 dark:text-blue-300">
                  SIMULATED / DEMO DATA:
                </span>{" "}
                Deterministic sensor event generator for operational validation, AI anomaly detection, and end-to-end supply chain demonstration.
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-600 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Control Surface Grid */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Simulator Parameters Card */}
              <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs dark:border-slate-800 dark:bg-slate-900">
                <div className="flex items-center gap-2.5 border-b border-slate-100 pb-3 dark:border-slate-800">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
                    <Cpu className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      Simulation Controls
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Configure target hive and scenario parameters
                    </p>
                  </div>
                </div>

                {/* Hive Selection */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Target Hive *
                  </label>
                  <select
                    value={selectedHiveId}
                    onChange={(e) => setSelectedHiveId(e.target.value)}
                    disabled={loading || running}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  >
                    {hives.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.hive_code} — {h.location_region} ({h.status})
                      </option>
                    ))}
                  </select>
                  {selectedHive && (
                    <p className="mt-1 text-[10px] text-slate-400">
                      UUID: <code className="font-mono">{selectedHive.id.slice(0, 18)}...</code>
                    </p>
                  )}
                </div>

                {/* Scenario Selection */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Simulation Scenario *
                  </label>
                  <select
                    value={selectedScenario}
                    onChange={(e) => setSelectedScenario(e.target.value)}
                    disabled={running}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  >
                    {scenarios.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  {selectedScenarioInfo && (
                    <p className="mt-1.5 rounded-md bg-slate-50 p-2 text-[11px] leading-relaxed text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                      {selectedScenarioInfo.description}
                    </p>
                  )}
                </div>

                {/* Seed Parameter */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Deterministic Seed
                  </label>
                  <input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    disabled={running}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:border-amber-400 dark:focus:bg-slate-900"
                  />
                  <p className="mt-1 text-[10px] text-slate-400">
                    Ensures exact repeatable values for judging demonstration.
                  </p>
                </div>

                {/* Run Action */}
                <div className="pt-2">
                  <button
                    onClick={handleRunSimulation}
                    disabled={running || !selectedHiveId}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 px-4 py-3 text-xs font-bold text-white shadow-md transition hover:from-amber-600 hover:to-amber-700 disabled:opacity-50"
                  >
                    {running ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Simulating & Ingesting...</span>
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 fill-white" />
                        <span>Run Once (Simulate & Ingest)</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Simulation Result Presentation (2 Columns) */}
              <div className="space-y-6 lg:col-span-2">
                {lastResult ? (
                  <>
                    {/* Telemetry Metric Cards */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                      <MetricCard
                        title="Temperature"
                        value={`${lastResult.temperature_c} °C`}
                        subtitle={
                          lastResult.temperature_c > 38
                            ? "Elevated (Heat stress)"
                            : "Within comfort range"
                        }
                        icon={Thermometer}
                      />
                      <MetricCard
                        title="Humidity"
                        value={`${lastResult.humidity_pct} %`}
                        subtitle={
                          lastResult.humidity_pct > 75
                            ? "High condensation"
                            : "Nominal moisture"
                        }
                        icon={Droplets}
                      />
                      <MetricCard
                        title="Hive Weight"
                        value={`${lastResult.weight_kg} kg`}
                        subtitle="Gross colony mass"
                        icon={Scale}
                      />
                      <MetricCard
                        title="Ingestion"
                        value={lastResult.ingestion_status}
                        subtitle="FastAPI telemetry stream"
                        icon={Database}
                      />
                    </div>

                    {/* AI Risk Evaluation Card */}
                    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs dark:border-slate-800 dark:bg-slate-900">
                      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500 text-white">
                            <ShieldCheck className="h-4 w-4" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                              AI Risk & Anomaly Observation
                            </h4>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                              Computed by backend rule-engine baseline
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                            Assessment:
                          </span>
                          <RiskBadge
                            level={
                              lastResult.risk_level === "HIGH"
                                ? "CRITICAL"
                                : lastResult.risk_level === "MEDIUM"
                                ? "MEDIUM"
                                : "LOW"
                            }
                          />
                          {lastResult.risk_score !== null && (
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                              Score: {lastResult.risk_score.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Observations / Reasons */}
                      <div className="mt-4 space-y-3">
                        <div>
                          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                            Signal Factors:
                          </span>
                          {lastResult.risk_reasons.length > 0 ? (
                            <ul className="mt-2 space-y-1.5">
                              {lastResult.risk_reasons.map((r, i) => (
                                <li
                                  key={i}
                                  className="flex items-start gap-2 text-xs text-slate-700 dark:text-slate-300"
                                >
                                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                                  <span>{r}</span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                              All readings nominal. No abnormal telemetry deviations detected.
                            </p>
                          )}
                        </div>

                        {lastResult.recommended_action && (
                          <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs dark:border-slate-800 dark:bg-slate-800/50">
                            <span className="font-bold text-slate-700 dark:text-slate-200">
                              Recommended Action:{" "}
                            </span>
                            <span className="text-slate-600 dark:text-slate-300">
                              {lastResult.recommended_action}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Quick Navigation E2E Buttons */}
                      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="h-4 w-4" />
                          <span>Telemetry ingested into hive {lastResult.hive_code}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() =>
                              router.push(`/telemetry?hive_id=${lastResult.hive_id}`)
                            }
                            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-xs transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                          >
                            <Radio className="h-3.5 w-3.5 text-blue-500" />
                            <span>Open Telemetry</span>
                            <ExternalLink className="h-3 w-3 text-slate-400" />
                          </button>

                          <button
                            onClick={() => router.push(`/risk?hive_id=${lastResult.hive_id}`)}
                            className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50/50 px-3 py-2 text-xs font-bold text-amber-700 shadow-xs transition hover:bg-amber-100/60 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-900/40"
                          >
                            <ShieldAlert className="h-3.5 w-3.5 text-amber-600" />
                            <span>Open Risk</span>
                            <ExternalLink className="h-3 w-3 text-amber-500" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center dark:border-slate-800 dark:bg-slate-900/30">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
                      <Cpu className="h-6 w-6" />
                    </div>
                    <h4 className="mt-3 text-sm font-bold text-slate-800 dark:text-slate-200">
                      Simulator Ready
                    </h4>
                    <p className="mt-1 max-w-sm text-xs text-slate-500 dark:text-slate-400">
                      Select a hive and scenario, then click{" "}
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        &quot;Run Once&quot;
                      </span>{" "}
                      to dispatch simulated sensor telemetry and view real-time AI ingestion results.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
