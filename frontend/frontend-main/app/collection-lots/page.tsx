"use client";

import { useState } from "react";
import {
  Package,
  Scale,
  CheckCircle2,
  Plus,
  Eye,
  X,
  MapPin,
  Clock3,
  LoaderCircle,
} from "lucide-react";

type CollectionLot = {
  id: string;
  harvests: string;
  honeyType: string;
  quantity: number;
  location: string;
  date: string;
  status: "COLLECTED" | "PROCESSING" | "VERIFIED";
};

const lots: CollectionLot[] = [
  {
    id: "LOT-2026-001",
    harvests: "HARV-2026-001",
    honeyType: "Wildflower",
    quantity: 24,
    location: "Gwalior",
    date: "05 Sep 2026",
    status: "COLLECTED",
  },
  {
    id: "LOT-2026-002",
    harvests: "HARV-2026-002",
    honeyType: "Mustard",
    quantity: 18,
    location: "Morena",
    date: "04 Sep 2026",
    status: "PROCESSING",
  },
  {
    id: "LOT-2026-003",
    harvests: "HARV-2026-003",
    honeyType: "Forest Honey",
    quantity: 15,
    location: "Gwalior",
    date: "03 Sep 2026",
    status: "VERIFIED",
  },
];

export default function LotsPage() {
  const [selectedLot, setSelectedLot] =
    useState<CollectionLot | null>(null);

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-amber-600">
            Honey Chain
          </p>

          <h1 className="mt-1 text-3xl font-bold text-slate-800">
            Collection Lots
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Manage collection lots created from harvested honey.
          </p>
        </div>

        <button
          onClick={() =>
            alert(
              "New collection lot form will be connected to the backend."
            )
          }
          className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
        >
          <Plus size={18} />
          Create Lot
        </button>
      </div>

      {/* Summary Cards */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <SummaryCard
          title="Total Lots"
          value="3"
          icon={<Package size={22} />}
        />

        <SummaryCard
          title="Total Quantity"
          value="57 kg"
          icon={<Scale size={22} />}
        />

        <SummaryCard
          title="Verified Lots"
          value="1"
          icon={<CheckCircle2 size={22} />}
        />
      </div>

      {/* Lots Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">
            Collection Lot History
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Collection lots linked to harvested honey.
          </p>
        </div>

        <div className="overflow-x-auto p-6">
          <table className="w-full min-w-[850px]">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-4">Lot ID</th>
                <th className="pb-4">Harvest</th>
                <th className="pb-4">Honey Type</th>
                <th className="pb-4">Quantity</th>
                <th className="pb-4">Location</th>
                <th className="pb-4">Date</th>
                <th className="pb-4">Status</th>
                <th className="pb-4">Action</th>
              </tr>
            </thead>

            <tbody className="text-sm">
              {lots.map((lot) => (
                <tr
                  key={lot.id}
                  className="border-b border-slate-50"
                >
                  <td className="py-4 font-bold text-slate-700">
                    {lot.id}
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    {lot.harvests}
                  </td>

                  <td className="py-4 text-slate-500">
                    {lot.honeyType}
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    <div className="flex items-center gap-2">
                      <Scale size={16} className="text-slate-400" />
                      {lot.quantity} kg
                    </div>
                  </td>

                  <td className="py-4 text-slate-500">
                    <div className="flex items-center gap-2">
                      <MapPin size={16} className="text-slate-400" />
                      {lot.location}
                    </div>
                  </td>

                  <td className="py-4 text-slate-500">
                    <div className="flex items-center gap-2">
                      <Clock3 size={16} className="text-slate-400" />
                      {lot.date}
                    </div>
                  </td>

                  <td className="py-4">
                    <StatusBadge status={lot.status} />
                  </td>

                  <td className="py-4">
                    <button
                      onClick={() => setSelectedLot(lot)}
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

      {/* Selected Lot Details */}
      {selectedLot && (
        <div className="mt-7 rounded-2xl border border-amber-100 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-600">
                Collection Lot Detail
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-800">
                {selectedLot.id}
              </h2>
            </div>

            <button
              onClick={() => setSelectedLot(null)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label="Close details"
            >
              <X size={20} />
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem
              label="Lot ID"
              value={selectedLot.id}
            />

            <DetailItem
              label="Source Harvest"
              value={selectedLot.harvests}
            />

            <DetailItem
              label="Honey Type"
              value={selectedLot.honeyType}
            />

            <DetailItem
              label="Quantity"
              value={`${selectedLot.quantity} kg`}
            />

            <DetailItem
              label="Location"
              value={selectedLot.location}
            />

            <DetailItem
              label="Collection Date"
              value={selectedLot.date}
            />
          </div>

          <div className="mt-6 flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-500">
              Current Status:
            </span>

            <StatusBadge status={selectedLot.status} />
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
  status: CollectionLot["status"];
}) {
  const style =
    status === "COLLECTED"
      ? "bg-blue-50 text-blue-600"
      : status === "PROCESSING"
      ? "bg-yellow-50 text-yellow-600"
      : "bg-green-50 text-green-600";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${style}`}
    >
      {status === "COLLECTED" && <Package size={13} />}
      {status === "PROCESSING" && <LoaderCircle size={13} />}
      {status === "VERIFIED" && <CheckCircle2 size={13} />}

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