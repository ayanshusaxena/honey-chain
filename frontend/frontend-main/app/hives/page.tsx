"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Hexagon,
  CheckCircle2,
  TriangleAlert,
  X,
  Radio,
  ShieldAlert,
  Eye,
  Plus,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import type { HiveResponse } from "../../types/contracts";

export default function HivesPage() {
  const router = useRouter();
  const [hives, setHives] = useState<HiveResponse[]>([]);
  const [selectedHive, setSelectedHive] = useState<HiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Hive modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newHiveCode, setNewHiveCode] = useState("");
  const [newRegion, setNewRegion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const loadHives = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      setError(null);
      const data = await apiClient.get<HiveResponse[]>("/hives");
      setHives(data || []);
      return data || [];
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load hives from backend.");
      }
      return [];
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    apiClient
      .get<HiveResponse[]>("/hives")
      .then((data) => {
        if (!active) return;
        setHives(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load hives from backend.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreateHive = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHiveCode.trim() || !newRegion.trim()) {
      setModalError("Hive code and region are required.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);
      const created = await apiClient.post<HiveResponse>("/hives", {
        hive_code: newHiveCode.trim(),
        location_region: newRegion.trim(),
      });
      setIsAddModalOpen(false);
      setNewHiveCode("");
      setNewRegion("");
      await loadHives(false);
      setSelectedHive(created);
    } catch (err) {
      if (err instanceof ApiError) {
        setModalError(err.message);
      } else {
        setModalError("Failed to create hive.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const totalHives = hives.length;
  const activeHives = hives.filter((h) => h.status === "ACTIVE").length;
  const maintenanceHives = hives.filter((h) => h.status === "MAINTENANCE").length;

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-amber-600">Honey Chain</p>

          <h1 className="mt-1 text-3xl font-bold text-slate-800">
            Hive Workspace
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Manage and monitor registered honey bee hives.
          </p>
        </div>

        <button
          onClick={() => {
            setModalError(null);
            setIsAddModalOpen(true);
          }}
          className="flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
        >
          <Hexagon size={18} />
          Add Hive
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle size={20} className="shrink-0" />
          <p className="text-sm font-medium">{error}</p>
          <button
            onClick={() => loadHives(true)}
            className="ml-auto text-xs font-bold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Summary */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <SummaryCard
          title="Total Hives"
          value={loading ? "..." : String(totalHives)}
          icon={<Hexagon size={21} />}
        />

        <SummaryCard
          title="Active Hives"
          value={loading ? "..." : String(activeHives)}
          icon={<CheckCircle2 size={21} />}
        />

        <SummaryCard
          title="Maintenance"
          value={loading ? "..." : String(maintenanceHives)}
          icon={<TriangleAlert size={21} />}
        />
      </div>

      {/* Hive List */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">
            Registered Hives
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Select a hive to view its details.
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
            <span className="ml-3 text-sm font-medium">Loading hives from backend...</span>
          </div>
        )}

        {!loading && hives.length === 0 && (
          <div className="p-12 text-center text-slate-400">
            <Hexagon size={40} className="mx-auto mb-3 text-slate-300" />
            <p className="text-sm font-semibold">No registered hives found.</p>
            <p className="mt-1 text-xs text-slate-400">
              Click &quot;Add Hive&quot; above to register your first hive.
            </p>
          </div>
        )}

        {!loading && hives.length > 0 && (
          <div className="divide-y divide-slate-100">
            {hives.map((hive) => (
              <div
                key={hive.id}
                className="flex flex-col gap-4 p-5 transition hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                    <Hexagon size={24} />
                  </div>

                  <div>
                    <h3 className="font-bold text-slate-800">
                      {hive.hive_code}
                    </h3>

                    <p className="text-sm text-slate-500">
                      {hive.location_region} •{" "}
                      {hive.beekeeper?.name || (hive.beekeeper_id ? `Beekeeper (${hive.beekeeper_id.slice(0, 8)})` : "Unassigned")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${
                      hive.status === "ACTIVE"
                        ? "bg-green-50 text-green-600"
                        : hive.status === "MAINTENANCE"
                        ? "bg-yellow-50 text-yellow-600"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {hive.status === "ACTIVE" ? (
                      <CheckCircle2 size={13} />
                    ) : (
                      <TriangleAlert size={13} />
                    )}

                    {hive.status}
                  </span>

                  <button
                    onClick={() => setSelectedHive(hive)}
                    className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
                  >
                    <Eye size={16} />
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Hive Details */}
      {selectedHive && (
        <div className="mt-7 rounded-2xl border border-amber-100 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-600">
                Hive Detail
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-800">
                {selectedHive.hive_code}
              </h2>
            </div>

            <button
              onClick={() => setSelectedHive(null)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            >
              <X size={20} />
            </button>
          </div>

          {/* Details */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem label="Hive Code" value={selectedHive.hive_code} />

            <DetailItem label="Region" value={selectedHive.location_region} />

            <DetailItem label="Status" value={selectedHive.status} />

            <DetailItem
              label="Beekeeper / Owner"
              value={selectedHive.beekeeper?.name || selectedHive.beekeeper_id}
            />
          </div>

          {/* Actions */}
          <div className="mt-6 flex flex-wrap gap-3">
            {/* Telemetry */}
            <button
              onClick={() => router.push(`/telemetry?hive_id=${selectedHive.id}`)}
              className="flex items-center gap-2 rounded-xl bg-slate-800 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-700"
            >
              <Radio size={18} />
              View Telemetry
            </button>

            {/* Risk */}
            <button
              onClick={() => router.push(`/risk?hive_id=${selectedHive.id}`)}
              className="flex items-center gap-2 rounded-xl border border-amber-200 px-5 py-3 text-sm font-bold text-amber-600 transition hover:bg-amber-50"
            >
              <ShieldAlert size={18} />
              View Risk
            </button>
          </div>
        </div>
      )}

      {/* Add Hive Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-800">
                <Hexagon size={20} className="text-amber-500" />
                <h3 className="text-lg font-bold">Register New Hive</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X size={18} />
              </button>
            </div>

            {modalError && (
              <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 p-3 text-xs font-semibold text-red-600">
                <AlertCircle size={16} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateHive} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                  Hive Code
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. HIVE-0005"
                  value={newHiveCode}
                  onChange={(e) => setNewHiveCode(e.target.value)}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                  Location Region
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Gwalior"
                  value={newRegion}
                  onChange={(e) => setNewRegion(e.target.value)}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus size={16} />
                      Register Hive
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function SummaryCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>

          <h3 className="mt-2 text-3xl font-bold text-slate-800">{value}</h3>
        </div>

        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-xs font-medium text-slate-400">{label}</p>

      <p className="mt-1 font-bold text-slate-700">{value}</p>
    </div>
  );
}