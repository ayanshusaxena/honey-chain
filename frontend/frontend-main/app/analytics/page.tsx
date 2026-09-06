"use client";

import {
  BarChart3,
  Activity,
  Hexagon,
  Package,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

const metrics = [
  {
    title: "Total Hives",
    value: "3",
    description: "Registered hives",
    icon: Hexagon,
  },
  {
    title: "Telemetry Readings",
    value: "128",
    description: "Recent readings",
    icon: Activity,
  },
  {
    title: "Risk Assessments",
    value: "3",
    description: "Current assessments",
    icon: ShieldAlert,
  },
  {
    title: "Processing Batches",
    value: "3",
    description: "Traceability records",
    icon: Package,
  },
];

const telemetryData = [
  { label: "Temperature", value: "32.5°C", status: "Normal" },
  { label: "Humidity", value: "68%", status: "Normal" },
  { label: "Hive Weight", value: "43.1 kg", status: "Latest reading" },
];

const riskData = [
  { hive: "HIVE-0001", score: 0.18, level: "LOW" },
  { hive: "HIVE-0002", score: 0.42, level: "MEDIUM" },
  { hive: "HIVE-0003", score: 0.78, level: "HIGH" },
];

export default function AnalyticsPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-5 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
            <BarChart3 size={22} />
          </div>

          <div>
            <p className="text-xs font-medium text-slate-400">
              Honey Chain
            </p>
            <h1 className="text-2xl font-bold text-slate-800">
              Analytics
            </h1>
          </div>
        </div>

        <p className="mt-3 text-sm text-slate-500">
          Overview of hive monitoring, telemetry, risk and traceability data.
        </p>
      </header>

      <div className="p-5 sm:p-8">
        {/* Metrics */}
        <div className="mb-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((item) => {
            const Icon = item.icon;

            return (
              <div
                key={item.title}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-400">
                      {item.title}
                    </p>

                    <h2 className="mt-2 text-3xl font-bold text-slate-800">
                      {item.value}
                    </h2>

                    <p className="mt-2 text-xs text-slate-400">
                      {item.description}
                    </p>
                  </div>

                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                    <Icon size={21} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Telemetry */}
        <div className="mb-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-6">
            <div className="flex items-center gap-3">
              <Activity size={21} className="text-amber-600" />
              <div>
                <h2 className="font-bold text-slate-800">
                  Telemetry Overview
                </h2>
                <p className="mt-1 text-sm text-slate-400">
                  Latest monitoring readings
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-5 p-6 md:grid-cols-3">
            {telemetryData.map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-slate-200 bg-slate-50 p-5"
              >
                <p className="text-sm text-slate-400">{item.label}</p>
                <p className="mt-2 text-2xl font-bold text-slate-800">
                  {item.value}
                </p>
                <p className="mt-2 text-xs font-semibold text-green-600">
                  {item.status}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Risk */}
        <div className="mb-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center gap-3 border-b border-slate-100 p-6">
            <TrendingUp size={21} className="text-amber-600" />

            <div>
              <h2 className="font-bold text-slate-800">
                Risk Assessment Overview
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Current hive risk scores
              </p>
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {riskData.map((item) => (
              <div
                key={item.hive}
                className="flex items-center justify-between p-5"
              >
                <div>
                  <p className="font-bold text-slate-700">
                    {item.hive}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Current assessment
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-xl font-bold text-slate-800">
                    {item.score.toFixed(2)}{" "}
                    <span className="text-xs font-normal text-slate-400">
                      ({(item.score * 100).toFixed(0)}%)
                    </span>
                  </p>
                  <span className={`text-xs font-bold ${
                    item.level === "LOW"
                      ? "text-green-600"
                      : item.level === "MEDIUM"
                      ? "text-yellow-600"
                      : "text-red-600"
                  }`}>
                    {item.level}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Traceability */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <Package size={21} className="text-amber-600" />

            <div>
              <h2 className="font-bold text-slate-800">
                Traceability Summary
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Current processing records across the workflow.
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <SummaryItem title="Harvests" value="3" />
            <SummaryItem title="Collection Lots" value="3" />
            <SummaryItem title="Processing Batches" value="3" />
          </div>
        </div>
      </div>
    </main>
  );
}

function SummaryItem({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-5">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-bold text-slate-800">{value}</p>
    </div>
  );
}