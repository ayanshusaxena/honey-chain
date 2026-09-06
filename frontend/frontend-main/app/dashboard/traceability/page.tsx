"use client";

import { useState } from "react";
import {
  Search,
  Package,
  UserRound,
  MapPin,
  CheckCircle2,
  GitBranch,
  ShieldCheck,
  Database,
  QrCode,
} from "lucide-react";

export default function TraceabilityPage() {
  const [batchId, setBatchId] = useState("");

  const batches = [
    {
      id: "HC-2026-001",
      type: "Wildflower",
      beekeeper: "Rajesh Kumar",
      location: "Madhya Pradesh",
      status: "Verified",
    },
    {
      id: "HC-2026-002",
      type: "Mustard",
      beekeeper: "Amit Sharma",
      location: "Rajasthan",
      status: "Verified",
    },
    {
      id: "HC-2026-003",
      type: "Acacia",
      beekeeper: "Sandeep Singh",
      location: "Punjab",
      status: "Pending",
    },
    {
      id: "HC-2026-004",
      type: "Forest Honey",
      beekeeper: "Vikram Rawat",
      location: "Uttarakhand",
      status: "Verified",
    },
  ];

  const selectedBatch = batches.find(
    (batch) => batch.id.toLowerCase() === batchId.toLowerCase()
  );

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-amber-600">
              Honey Chain
            </p>

            <h1 className="mt-1 flex items-center gap-3 text-3xl font-bold text-slate-800">
              <GitBranch className="text-amber-500" size={30} />
              Traceability
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              Track the complete journey of your honey batch
            </p>
          </div>

          <div className="hidden h-12 w-12 items-center justify-center rounded-xl bg-amber-100 text-amber-600 sm:flex">
            <GitBranch size={24} />
          </div>
        </div>

        {/* Search */}
        <div className="mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-2 flex items-center gap-2 text-lg font-bold text-slate-800">
            <Search size={20} className="text-amber-500" />
            Track a Honey Batch
          </h2>

          <p className="mb-4 text-sm text-slate-400">
            Enter Batch ID to view its complete traceability journey.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              placeholder="Enter Batch ID e.g. HC-2026-001"
              className="flex-1 rounded-xl border border-slate-200 px-4 py-3 outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
            />

            <button
              onClick={() => {}}
              className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-6 py-3 font-bold text-white transition hover:bg-amber-600"
            >
              <Search size={18} />
              Track Batch
            </button>
          </div>
        </div>

        {/* Result */}
        {selectedBatch ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row">
              <div>
                <p className="text-sm text-slate-400">
                  Batch ID
                </p>

                <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-800">
                  <Package size={23} className="text-amber-500" />
                  {selectedBatch.id}
                </h2>
              </div>

              <span className="flex h-fit items-center gap-2 rounded-full bg-green-50 px-4 py-2 text-sm font-bold text-green-600">
                <CheckCircle2 size={16} />
                {selectedBatch.status}
              </span>
            </div>

            {/* Batch Information */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <InfoCard
                title="Honey Type"
                value={selectedBatch.type}
                icon={<Package size={20} />}
              />

              <InfoCard
                title="Beekeeper"
                value={selectedBatch.beekeeper}
                icon={<UserRound size={20} />}
              />

              <InfoCard
                title="Location"
                value={selectedBatch.location}
                icon={<MapPin size={20} />}
              />

              <InfoCard
                title="Verification"
                value={selectedBatch.status}
                icon={<ShieldCheck size={20} />}
              />
            </div>

            {/* Journey */}
            <div className="mt-8">
              <h3 className="mb-6 flex items-center gap-2 text-lg font-bold text-slate-800">
                <GitBranch size={20} className="text-amber-500" />
                Supply Chain Journey
              </h3>

              <div className="space-y-5">
                <JourneyStep
                  number="1"
                  title="Honey Collection"
                  description={`Honey collected by ${selectedBatch.beekeeper}`}
                  status="Completed"
                  icon={<Package size={18} />}
                />

                <JourneyStep
                  number="2"
                  title="Quality Verification"
                  description="Honey quality and batch information verified"
                  status="Completed"
                  icon={<ShieldCheck size={18} />}
                />

                <JourneyStep
                  number="3"
                  title="Blockchain Registration"
                  description="Batch record stored securely on blockchain"
                  status="Completed"
                  icon={<Database size={18} />}
                />

                <JourneyStep
                  number="4"
                  title="Consumer Tracking"
                  description="Consumer can verify the complete honey journey"
                  status="Active"
                  icon={<QrCode size={18} />}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-amber-500">
              <Search size={28} />
            </div>

            <h3 className="font-bold text-slate-700">
              Search for a Batch
            </h3>

            <p className="mt-1 text-sm text-slate-400">
              Try HC-2026-001 to view its traceability journey.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

/* ================= COMPONENTS ================= */

function InfoCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
        {icon}
      </div>

      <p className="text-xs text-slate-400">
        {title}
      </p>

      <p className="mt-1 font-bold text-slate-700">
        {value}
      </p>
    </div>
  );
}

function JourneyStep({
  number,
  title,
  description,
  status,
  icon,
}: {
  number: string;
  title: string;
  description: string;
  status: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
        {icon}
      </div>

      <div className="flex-1 border-b border-slate-100 pb-5">
        <div className="flex flex-col justify-between gap-1 sm:flex-row">
          <h4 className="font-bold text-slate-700">
            {number}. {title}
          </h4>

          <span className="flex items-center gap-1 text-xs font-bold text-green-600">
            <CheckCircle2 size={13} />
            {status}
          </span>
        </div>

        <p className="mt-1 text-sm text-slate-400">
          {description}
        </p>
      </div>
    </div>
  );
}