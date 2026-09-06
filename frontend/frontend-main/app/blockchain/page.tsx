"use client";

import {
  Blocks,
  ShieldCheck,
  Link2,
  Clock3,
  Search,
  CheckCircle2,
  Hash,
} from "lucide-react";
import { useState } from "react";

type BlockchainRecord = {
  batchId: string;
  status: "READY" | "PENDING";
  network: string;
  recordType: string;
  createdAt: string;
};

const records: BlockchainRecord[] = [
  {
    batchId: "BATCH-2026-001",
    status: "READY",
    network: "Blockchain Network",
    recordType: "Batch Traceability",
    createdAt: "05 Sep 2026",
  },
  {
    batchId: "BATCH-2026-002",
    status: "READY",
    network: "Blockchain Network",
    recordType: "Batch Traceability",
    createdAt: "04 Sep 2026",
  },
  {
    batchId: "BATCH-2026-003",
    status: "PENDING",
    network: "Blockchain Network",
    recordType: "Batch Traceability",
    createdAt: "03 Sep 2026",
  },
];

export default function BlockchainPage() {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<BlockchainRecord | null>(null);

  const filteredRecords = records.filter((item) =>
    item.batchId.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      <div className="mx-auto max-w-7xl">

        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-medium text-amber-600">
            Honey Chain
          </p>

          <h1 className="mt-1 flex items-center gap-3 text-3xl font-bold text-slate-800">
            <Blocks className="text-amber-500" size={30} />
            Blockchain
            <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-bold text-slate-600">
              GATED PROTOTYPE
            </span>
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Downstream blockchain anchoring interface (gated in current backend baseline).
          </p>
        </div>

        {/* Info Banner */}
        <div className="mb-7 flex gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <ShieldCheck
            size={24}
            className="mt-0.5 shrink-0 text-amber-600"
          />

          <div>
            <h2 className="font-bold text-amber-800">
              Gated Capability — Prototype Surface Only
            </h2>

            <p className="mt-1 text-sm leading-6 text-amber-700">
              Blockchain anchoring and smart contract verification are downstream capabilities
              gated in the current backend baseline. This view represents the prototype interface
              design. Live on-chain transactions and hash notarization will be enabled in a future release.
            </p>
          </div>
        </div>

        {/* Summary */}
        <div className="mb-7 grid gap-5 sm:grid-cols-3">

          <SummaryCard
            title="Total Records"
            value="3"
            icon={<Blocks size={22} />}
          />

          <SummaryCard
            title="Ready for Verification"
            value="2"
            icon={<CheckCircle2 size={22} />}
          />

          <SummaryCard
            title="Pending"
            value="1"
            icon={<Clock3 size={22} />}
          />

        </div>

        {/* Search */}
        <div className="mb-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="relative">

            <Search
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Batch ID..."
              className="w-full rounded-xl border border-slate-200 py-3 pl-11 pr-4 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
            />

          </div>
        </div>

        {/* Blockchain Records */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">

          <div className="border-b border-slate-100 p-6">
            <h2 className="text-lg font-bold text-slate-800">
              Blockchain Records
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Batch records prepared for blockchain verification.
            </p>
          </div>

          <div className="overflow-x-auto p-6">

            <table className="w-full min-w-[850px]">

              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                  <th className="pb-4">Batch ID</th>
                  <th className="pb-4">Record Type</th>
                  <th className="pb-4">Network</th>
                  <th className="pb-4">Created</th>
                  <th className="pb-4">Status</th>
                  <th className="pb-4">Action</th>
                </tr>
              </thead>

              <tbody className="text-sm">

                {filteredRecords.map((item) => (
                  <tr
                    key={item.batchId}
                    className="border-b border-slate-50"
                  >

                    <td className="py-4 font-bold text-slate-700">
                      {item.batchId}
                    </td>

                    <td className="py-4 text-slate-500">
                      {item.recordType}
                    </td>

                    <td className="py-4">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Link2 size={15} />
                        {item.network}
                      </div>
                    </td>

                    <td className="py-4 text-slate-500">
                      {item.createdAt}
                    </td>

                    <td className="py-4">
                      <StatusBadge status={item.status} />
                    </td>

                    <td className="py-4">

                      <button
                        onClick={() => setSelected(item)}
                        className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
                      >
                        <Search size={15} />
                        View
                      </button>

                    </td>

                  </tr>
                ))}

              </tbody>

            </table>

            {filteredRecords.length === 0 && (
              <div className="py-12 text-center">

                <Search
                  size={30}
                  className="mx-auto mb-3 text-slate-300"
                />

                <p className="font-semibold text-slate-600">
                  No blockchain record found
                </p>

              </div>
            )}

          </div>
        </div>

        {/* Detail */}
        {selected && (
          <div className="mt-7 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

            <div className="mb-6 flex items-center justify-between">

              <div>
                <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-600">
                  <Blocks size={15} />
                  Blockchain Record
                </p>

                <h2 className="mt-1 text-2xl font-bold text-slate-800">
                  {selected.batchId}
                </h2>
              </div>

              <button
                onClick={() => setSelected(null)}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
              >
                ✕
              </button>

            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

              <DetailItem
                label="Batch ID"
                value={selected.batchId}
              />

              <DetailItem
                label="Record Type"
                value={selected.recordType}
              />

              <DetailItem
                label="Network"
                value={selected.network}
              />

              <DetailItem
                label="Created"
                value={selected.createdAt}
              />

            </div>

            <div className="mt-5 flex items-center gap-3 rounded-xl bg-slate-50 p-4">

              <Hash size={20} className="text-slate-400" />

              <div>
                <p className="text-xs font-medium text-slate-400">
                  Transaction Hash
                </p>

                <p className="mt-1 text-sm font-semibold text-slate-500">
                  Will be provided by blockchain backend
                </p>
              </div>

            </div>

            <div className="mt-5 flex items-center gap-3">
              <StatusBadge status={selected.status} />

              <button
                disabled
                className="cursor-not-allowed rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-400"
                title="Gated feature — will be enabled in downstream phase"
              >
                Verification Gated (Phase 3)
              </button>
            </div>

          </div>
        )}

      </div>
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
  status: BlockchainRecord["status"];
}) {
  const style =
    status === "READY"
      ? "bg-green-50 text-green-600"
      : "bg-yellow-50 text-yellow-600";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${style}`}
    >
      {status === "READY" ? (
        <CheckCircle2 size={13} />
      ) : (
        <Clock3 size={13} />
      )}

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

      <p className="mt-1 break-words font-bold text-slate-700">
        {value}
      </p>

    </div>
  );
}