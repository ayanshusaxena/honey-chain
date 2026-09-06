"use client";

import { useState } from "react";
import {
  Factory,
  Scale,
  CheckCircle2,
  Plus,
  Eye,
  X,
  MapPin,
  CalendarDays,
  LoaderCircle,
  Clock3,
  GitBranch,
} from "lucide-react";
import type { BatchStatus } from "../../types/contracts";

type Batch = {
  id: string;
  lotId: string;
  honeyType: string;
  quantity: number;
  processingDate: string;
  location: string;
  status: BatchStatus;
};

const batches: Batch[] = [
  {
    id: "BATCH-2026-001",
    lotId: "LOT-2026-001",
    honeyType: "Wildflower",
    quantity: 24,
    processingDate: "05 Sep 2026",
    location: "Gwalior Processing Unit",
    status: "ACTIVE",
  },
  {
    id: "BATCH-2026-002",
    lotId: "LOT-2026-002",
    honeyType: "Mustard",
    quantity: 18,
    processingDate: "04 Sep 2026",
    location: "Morena Processing Unit",
    status: "HOLD",
  },
  {
    id: "BATCH-2026-003",
    lotId: "LOT-2026-003",
    honeyType: "Forest Honey",
    quantity: 15,
    processingDate: "03 Sep 2026",
    location: "Gwalior Processing Unit",
    status: "ACTIVE",
  },
];

export default function BatchesPage() {
  const [selectedBatch, setSelectedBatch] = useState<Batch | null>(null);

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-amber-600">
            Honey Chain
          </p>

          <h1 className="mt-1 flex items-center gap-3 text-3xl font-bold text-slate-800">
            <Factory className="text-amber-500" size={30} />
            Processing Batches
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Track processing batches created from collection lots.
          </p>
        </div>

        <button
          onClick={() =>
            alert(
              "New processing batch form will be connected to the backend."
            )
          }
          className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
        >
          <Plus size={18} />
          Create Batch
        </button>
      </div>

      {/* Summary */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <SummaryCard
          title="Total Batches"
          value="3"
          icon={<Factory size={22} />}
        />

        <SummaryCard
          title="Total Quantity"
          value="57 kg"
          icon={<Scale size={22} />}
        />

        <SummaryCard
          title="Active Batches"
          value="2"
          icon={<CheckCircle2 size={22} />}
        />
      </div>

      {/* Batch Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">
            Processing Batch History
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Processing batches linked to collection lots.
          </p>
        </div>

        <div className="overflow-x-auto p-6">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-4">Batch ID</th>
                <th className="pb-4">Collection Lot</th>
                <th className="pb-4">Honey Type</th>
                <th className="pb-4">Quantity</th>
                <th className="pb-4">Processing Date</th>
                <th className="pb-4">Location</th>
                <th className="pb-4">Status</th>
                <th className="pb-4">Action</th>
              </tr>
            </thead>

            <tbody className="text-sm">
              {batches.map((batch) => (
                <tr
                  key={batch.id}
                  className="border-b border-slate-50"
                >
                  <td className="py-4 font-bold text-slate-700">
                    {batch.id}
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    {batch.lotId}
                  </td>

                  <td className="py-4 text-slate-500">
                    {batch.honeyType}
                  </td>

                  <td className="py-4 font-semibold text-slate-600">
                    <div className="flex items-center gap-2">
                      <Scale size={16} className="text-slate-400" />
                      {batch.quantity} kg
                    </div>
                  </td>

                  <td className="py-4 text-slate-500">
                    <div className="flex items-center gap-2">
                      <CalendarDays
                        size={16}
                        className="text-slate-400"
                      />
                      {batch.processingDate}
                    </div>
                  </td>

                  <td className="py-4 text-slate-500">
                    <div className="flex items-center gap-2">
                      <MapPin size={16} className="text-slate-400" />
                      {batch.location}
                    </div>
                  </td>

                  <td className="py-4">
                    <StatusBadge status={batch.status} />
                  </td>

                  <td className="py-4">
                    <button
                      onClick={() => setSelectedBatch(batch)}
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

      {/* Batch Details */}
      {selectedBatch && (
        <div className="mt-7 rounded-2xl border border-amber-100 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-600">
                <Factory size={15} />
                Processing Batch Detail
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-800">
                {selectedBatch.id}
              </h2>
            </div>

            <button
              onClick={() => setSelectedBatch(null)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label="Close details"
            >
              <X size={20} />
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem
              label="Batch ID"
              value={selectedBatch.id}
            />

            <DetailItem
              label="Collection Lot"
              value={selectedBatch.lotId}
            />

            <DetailItem
              label="Honey Type"
              value={selectedBatch.honeyType}
            />

            <DetailItem
              label="Quantity"
              value={`${selectedBatch.quantity} kg`}
            />

            <DetailItem
              label="Processing Date"
              value={selectedBatch.processingDate}
            />

            <DetailItem
              label="Processing Location"
              value={selectedBatch.location}
            />
          </div>

          <div className="mt-6 flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-500">
              Current Status:
            </span>

            <StatusBadge status={selectedBatch.status} />
          </div>

          {/* Traceability Link */}
          <div className="mt-6 rounded-xl border border-amber-100 bg-amber-50 p-5">
            <p className="flex items-center gap-2 text-sm font-bold text-amber-700">
              <GitBranch size={17} />
              Traceability
            </p>

            <p className="mt-1 text-sm text-amber-600">
              This batch is linked to {selectedBatch.lotId} and can later
              connect to laboratory evidence, blockchain records,
              packaging and consumer verification.
            </p>
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
  status: Batch["status"];
}) {
  const style =
    status === "ACTIVE"
      ? "bg-emerald-50 text-emerald-600"
      : status === "HOLD"
      ? "bg-amber-50 text-amber-700"
      : "bg-red-50 text-red-600";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${style}`}
    >
      {status === "ACTIVE" && <CheckCircle2 size={13} />}
      {status === "HOLD" && <Clock3 size={13} />}
      {status === "RECALL" && <LoaderCircle size={13} />}

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