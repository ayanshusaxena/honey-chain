"use client";

import { useState } from "react";
import {
  PackageOpen,
  Scale,
  TriangleAlert,
  Plus,
  X,
  Eye,
  CheckCircle2,
  Clock3,
  MapPin,
} from "lucide-react";

type Harvest = {
  id: string;
  hive: string;
  date: string;
  quantity: number;
  location: string;
  status: "COLLECTED" | "PENDING" | "REVIEW";
};

const harvests: Harvest[] = [
  {
    id: "HARV-2026-001",
    hive: "HIVE-0001",
    date: "05 Sep 2026",
    quantity: 24,
    location: "Gwalior",
    status: "COLLECTED",
  },
  {
    id: "HARV-2026-002",
    hive: "HIVE-0002",
    date: "04 Sep 2026",
    quantity: 18,
    location: "Morena",
    status: "PENDING",
  },
  {
    id: "HARV-2026-003",
    hive: "HIVE-0003",
    date: "03 Sep 2026",
    quantity: 15,
    location: "Gwalior",
    status: "REVIEW",
  },
];

export default function HarvestsPage() {
  const [selectedHarvest, setSelectedHarvest] =
    useState<Harvest | null>(null);

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-amber-600">
            Honey Chain
          </p>

          <div className="mt-1 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <PackageOpen size={22} />
            </div>

            <h1 className="text-3xl font-bold text-slate-800">
              Harvest Records
            </h1>
          </div>

          <p className="mt-2 text-sm text-slate-500">
            Track honey harvested from registered hives.
          </p>
        </div>

        <button
          onClick={() =>
            alert("New harvest form will be connected to the backend.")
          }
          className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
        >
          <Plus size={18} />
          Add Harvest
        </button>
      </div>

      {/* Summary */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <SummaryCard
          title="Total Harvests"
          value="3"
          icon={<PackageOpen size={21} />}
        />

        <SummaryCard
          title="Total Quantity"
          value="57 kg"
          icon={<Scale size={21} />}
        />

        <SummaryCard
          title="Pending Review"
          value="2"
          icon={<TriangleAlert size={21} />}
        />
      </div>

      {/* Harvest Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">
            Harvest History
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Harvest records linked to registered hives.
          </p>
        </div>

        <div className="overflow-x-auto p-6">
          <table className="w-full min-w-[750px]">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-4">Harvest ID</th>
                <th className="pb-4">Hive</th>
                <th className="pb-4">Date</th>
                <th className="pb-4">Quantity</th>
                <th className="pb-4">Location</th>
                <th className="pb-4">Status</th>
                <th className="pb-4">Action</th>
              </tr>
            </thead>

            <tbody className="text-sm">
              {harvests.map((harvest) => (
                <tr
                  key={harvest.id}
                  className="border-b border-slate-50"
                >
                  <td className="py-4 font-bold text-slate-700">
                    {harvest.id}
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    {harvest.hive}
                  </td>

                  <td className="py-4">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Clock3 size={15} />
                      {harvest.date}
                    </div>
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    <div className="flex items-center gap-2">
                      <Scale size={15} />
                      {harvest.quantity} kg
                    </div>
                  </td>

                  <td className="py-4">
                    <div className="flex items-center gap-2 text-slate-500">
                      <MapPin size={15} />
                      {harvest.location}
                    </div>
                  </td>

                  <td className="py-4">
                    <StatusBadge status={harvest.status} />
                  </td>

                  <td className="py-4">
                    <button
                      onClick={() => setSelectedHarvest(harvest)}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
                    >
                      <Eye size={15} />
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Details */}
      {selectedHarvest && (
        <div className="mt-7 rounded-2xl border border-amber-100 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-600">
                Harvest Detail
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-800">
                {selectedHarvest.id}
              </h2>
            </div>

            <button
              onClick={() => setSelectedHarvest(null)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            >
              <X size={20} />
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <DetailItem
              label="Harvest ID"
              value={selectedHarvest.id}
            />

            <DetailItem
              label="Hive"
              value={selectedHarvest.hive}
            />

            <DetailItem
              label="Date"
              value={selectedHarvest.date}
            />

            <DetailItem
              label="Quantity"
              value={`${selectedHarvest.quantity} kg`}
            />

            <DetailItem
              label="Location"
              value={selectedHarvest.location}
            />
          </div>

          <div className="mt-6 flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-500">
              Current Status:
            </span>

            <StatusBadge status={selectedHarvest.status} />
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
          <p className="text-sm font-medium text-slate-400">
            {title}
          </p>

          <h3 className="mt-2 text-3xl font-bold text-slate-800">
            {value}
          </h3>
        </div>

        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: Harvest["status"];
}) {
  const style =
    status === "COLLECTED"
      ? "bg-green-50 text-green-600"
      : status === "PENDING"
      ? "bg-yellow-50 text-yellow-600"
      : "bg-orange-50 text-orange-600";

  const icon =
    status === "COLLECTED" ? (
      <CheckCircle2 size={13} />
    ) : status === "PENDING" ? (
      <Clock3 size={13} />
    ) : (
      <TriangleAlert size={13} />
    );

  return (
    <span
      className={`flex w-fit items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${style}`}
    >
      {icon}
      {status}
    </span>
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
      <p className="text-xs font-medium text-slate-400">
        {label}
      </p>

      <p className="mt-1 font-bold text-slate-700">
        {value}
      </p>
    </div>
  );
}