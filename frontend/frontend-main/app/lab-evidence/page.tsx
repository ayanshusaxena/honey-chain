"use client";

import { useState } from "react";
import {
  FileText,
  Upload,
  Search,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  X,
  ShieldCheck,
  Hash,
} from "lucide-react";
import type { LabEvidenceStatus } from "../../types/contracts";

type LabEvidence = {
  id: string;
  batchId: string;
  certificateId: string;
  testType: string;
  result: string;
  uploadedAt: string;
  status: LabEvidenceStatus;
  fileName: string;
};

const evidenceRecords: LabEvidence[] = [
  {
    id: "LAB-2026-001",
    batchId: "BATCH-2026-001",
    certificateId: "CERT-2026-001",
    testType: "Honey Quality Test",
    result: "Passed",
    uploadedAt: "05 Sep 2026",
    status: "ACTIVE",
    fileName: "honey-quality-report-001.pdf",
  },
  {
    id: "LAB-2026-002",
    batchId: "BATCH-2026-002",
    certificateId: "CERT-2026-002",
    testType: "Purity & Moisture Test",
    result: "Passed",
    uploadedAt: "04 Sep 2026",
    status: "ACTIVE",
    fileName: "purity-report-002.pdf",
  },
  {
    id: "LAB-2026-003",
    batchId: "BATCH-2026-003",
    certificateId: "CERT-2026-003",
    testType: "Quality Verification",
    result: "Under Review",
    uploadedAt: "03 Sep 2026",
    status: "SUPERSEDED",
    fileName: "quality-report-003.pdf",
  },
];

export default function LabEvidencePage() {
  const [search, setSearch] = useState("");
  const [selectedEvidence, setSelectedEvidence] =
    useState<LabEvidence | null>(null);

  const filteredEvidence = evidenceRecords.filter(
    (item) =>
      item.batchId.toLowerCase().includes(search.toLowerCase()) ||
      item.certificateId.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-amber-600">
              Honey Chain
            </p>

            <h1 className="mt-1 flex items-center gap-3 text-3xl font-bold text-slate-800">
              <FileText className="text-amber-500" size={30} />
              Lab Evidence
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              Manage laboratory reports and quality evidence linked to honey
              batches.
            </p>
          </div>

          <button
            onClick={() =>
              alert(
                "PDF upload form will be connected to the backend."
              )
            }
            className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
          >
            <Upload size={18} />
            Upload Evidence
          </button>
        </div>

        {/* Summary Cards */}
        <div className="mb-7 grid gap-5 sm:grid-cols-3">
          <SummaryCard
            title="Total Evidence"
            value="3"
            icon={<FileText size={22} />}
          />

          <SummaryCard
            title="Active Evidence"
            value="2"
            icon={<CheckCircle2 size={22} />}
          />

          <SummaryCard
            title="Superseded"
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
              placeholder="Search by Batch ID or Certificate ID..."
              className="w-full rounded-xl border border-slate-200 py-3 pl-11 pr-4 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
            />
          </div>
        </div>

        {/* Evidence Table */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-6">
            <h2 className="text-lg font-bold text-slate-800">
              Laboratory Evidence History
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Quality reports linked to processing batches.
            </p>
          </div>

          <div className="overflow-x-auto p-6">
            <table className="w-full min-w-[950px]">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-400">
                  <th className="pb-4">Evidence ID</th>
                  <th className="pb-4">Batch ID</th>
                  <th className="pb-4">Certificate</th>
                  <th className="pb-4">Test Type</th>
                  <th className="pb-4">Result</th>
                  <th className="pb-4">Uploaded</th>
                  <th className="pb-4">Status</th>
                  <th className="pb-4">Action</th>
                </tr>
              </thead>

              <tbody className="text-sm">
                {filteredEvidence.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-slate-50"
                  >
                    <td className="py-4 font-bold text-slate-700">
                      {item.id}
                    </td>

                    <td className="py-4 font-semibold text-slate-600">
                      {item.batchId}
                    </td>

                    <td className="py-4 text-slate-500">
                      {item.certificateId}
                    </td>

                    <td className="py-4 text-slate-500">
                      {item.testType}
                    </td>

                    <td className="py-4 font-semibold text-slate-600">
                      {item.result}
                    </td>

                    <td className="py-4 text-slate-500">
                      <div className="flex items-center gap-2">
                        <Clock3 size={15} className="text-slate-400" />
                        {item.uploadedAt}
                      </div>
                    </td>

                    <td className="py-4">
                      <StatusBadge status={item.status} />
                    </td>

                    <td className="py-4">
                      <button
                        onClick={() => setSelectedEvidence(item)}
                        className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
                      >
                        <Eye size={15} />
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {filteredEvidence.length === 0 && (
              <div className="py-12 text-center">
                <Search
                  size={30}
                  className="mx-auto mb-3 text-slate-300"
                />

                <p className="font-semibold text-slate-600">
                  No evidence found
                </p>

                <p className="mt-1 text-sm text-slate-400">
                  Try another Batch ID or Certificate ID.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Selected Evidence */}
        {selectedEvidence && (
          <div className="mt-7 rounded-2xl border border-amber-100 bg-white p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-600">
                  <ShieldCheck size={15} />
                  Laboratory Evidence Detail
                </p>

                <h2 className="mt-1 text-2xl font-bold text-slate-800">
                  {selectedEvidence.id}
                </h2>
              </div>

              <button
                onClick={() => setSelectedEvidence(null)}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                aria-label="Close details"
              >
                <X size={20} />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <DetailItem
                label="Evidence ID"
                value={selectedEvidence.id}
              />

              <DetailItem
                label="Batch ID"
                value={selectedEvidence.batchId}
              />

              <DetailItem
                label="Certificate ID"
                value={selectedEvidence.certificateId}
              />

              <DetailItem
                label="Test Type"
                value={selectedEvidence.testType}
              />

              <DetailItem
                label="Result"
                value={selectedEvidence.result}
              />

              <DetailItem
                label="Uploaded At"
                value={selectedEvidence.uploadedAt}
              />

              <DetailItem
                label="File"
                value={selectedEvidence.fileName}
              />

              <div className="rounded-xl bg-slate-50 p-4">
                <p className="flex items-center gap-2 text-xs font-medium text-slate-400">
                  <Hash size={14} />
                  SHA-256
                </p>

                <p className="mt-2 text-sm font-semibold text-slate-500">
                  Calculated by backend
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <StatusBadge status={selectedEvidence.status} />

              <button
                onClick={() =>
                  alert(
                    "File download will be connected to the backend."
                  )
                }
                className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
              >
                <Download size={17} />
                Download PDF
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
  status: LabEvidence["status"];
}) {
  const style =
    status === "ACTIVE"
      ? "bg-emerald-50 text-emerald-600"
      : status === "SUPERSEDED"
      ? "bg-amber-50 text-amber-700"
      : "bg-red-50 text-red-600";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${style}`}
    >
      {status === "ACTIVE" && <CheckCircle2 size={13} />}
      {status === "SUPERSEDED" && <Clock3 size={13} />}
      {status === "REVOKED" && <X size={13} />}

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