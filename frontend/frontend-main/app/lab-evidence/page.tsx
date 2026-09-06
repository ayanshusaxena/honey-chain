"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  FileText,
  Upload,
  CheckCircle2,
  ShieldCheck,
  Search,
  Download,
  X,
  Plus,
  Loader2,
  AlertCircle,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react";
import { apiClient } from "../../lib/api-client";
import { ApiError } from "../../lib/errors";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import type {
  BatchResponse,
  LabEvidenceResponse,
  LabEvidenceVerifyResponse,
} from "../../types/contracts";

export default function LabEvidencePage() {
  const session = useAppSession();

  const [batches, setBatches] = useState<BatchResponse[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string>("");
  const [evidenceList, setEvidenceList] = useState<LabEvidenceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Hash verification drawer / modal
  const [verificationResult, setVerificationResult] =
    useState<LabEvidenceVerifyResponse | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Upload modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadBatchId, setUploadBatchId] = useState("");
  const [certId, setCertId] = useState("");
  const [testSummary, setTestSummary] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // 1. Load Batches
  useEffect(() => {
    let active = true;
    apiClient
      .get<BatchResponse[]>("/batches")
      .then((data) => {
        if (!active) return;
        const list = data || [];
        setBatches(list);
        if (list.length > 0) {
          setSelectedBatchId(list[0].id);
          setUploadBatchId(list[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load batches.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // 2. Load Evidence when selectedBatchId changes
  useEffect(() => {
    if (!selectedBatchId) return;
    let active = true;
    apiClient
      .get<LabEvidenceResponse[]>(`/batches/${selectedBatchId}/lab-evidence`)
      .then((data) => {
        if (!active) return;
        setEvidenceList(data || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Failed to load lab evidence for batch."
        );
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedBatchId]);

  const reloadData = useCallback(async () => {
    if (!selectedBatchId) return;
    try {
      setError(null);
      setLoading(true);
      const data = await apiClient.get<LabEvidenceResponse[]>(
        `/batches/${selectedBatchId}/lab-evidence`
      );
      setEvidenceList(data || []);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to load lab evidence for batch."
      );
    } finally {
      setLoading(false);
    }
  }, [selectedBatchId]);

  const handleVerifyHash = async (evidenceId: string) => {
    try {
      setVerifyingId(evidenceId);
      const res = await apiClient.get<LabEvidenceVerifyResponse>(
        `/lab-evidence/${evidenceId}/verify`
      );
      setVerificationResult(res);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to verify evidence cryptographic hash."
      );
    } finally {
      setVerifyingId(null);
    }
  };

  const handleDownload = async (evidenceId: string, fileName: string) => {
    try {
      setDownloadingId(evidenceId);
      const token = typeof window !== "undefined" ? localStorage.getItem("honey_token") : null;
      const res = await fetch(`http://localhost:8000/api/v1/lab-evidence/${evidenceId}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("File download failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName || `evidence-${evidenceId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloadingId(null);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadBatchId) {
      setModalError("Please select a target batch.");
      return;
    }
    if (!certId.trim()) {
      setModalError("Certificate ID is required.");
      return;
    }
    if (!testSummary.trim()) {
      setModalError("Test summary is required.");
      return;
    }
    if (!selectedFile) {
      setModalError("Please select a PDF file.");
      return;
    }

    try {
      setSubmitting(true);
      setModalError(null);

      const formData = new FormData();
      formData.append("certificate_id", certId.trim());
      formData.append("test_summary", testSummary.trim());
      formData.append("file", selectedFile);

      const token = typeof window !== "undefined" ? localStorage.getItem("honey_token") : null;
      const res = await fetch(
        `http://localhost:8000/api/v1/batches/${uploadBatchId}/lab-evidence`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );

      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({}));
        throw new Error(errorJson.detail || "Upload failed");
      }

      setIsUploadModalOpen(false);
      setCertId("");
      setTestSummary("");
      setSelectedFile(null);
      if (uploadBatchId === selectedBatchId) {
        reloadData();
      } else {
        setSelectedBatchId(uploadBatchId);
      }
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to upload evidence.");
    } finally {
      setSubmitting(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const filteredEvidence = useMemo(() => {
    if (!searchQuery.trim()) return evidenceList;
    const q = searchQuery.toLowerCase();
    return evidenceList.filter(
      (e) =>
        e.certificate_id.toLowerCase().includes(q) ||
        e.test_summary.toLowerCase().includes(q) ||
        e.file_hash_sha256.toLowerCase().includes(q)
    );
  }, [evidenceList, searchQuery]);

  const canUpload =
    !session?.role || session.role === "ADMIN" || session.role === "PROCESSOR";

  const selectedBatch = batches.find((b) => b.id === selectedBatchId);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <AppHeader
          title="Lab Evidence & Quality Verification"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Verification" },
            { label: "Lab Evidence" },
          ]}
          session={session}
          onRefresh={reloadData}
          refreshing={loading}
          actions={
            <div className="flex items-center gap-2">
              {batches.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="hidden text-xs font-semibold text-slate-500 sm:inline dark:text-slate-400">
                    Target Batch:
                  </span>
                  <select
                    value={selectedBatchId}
                    onChange={(e) => setSelectedBatchId(e.target.value)}
                    className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 shadow-sm transition focus:border-amber-500 focus:outline-none dark:border-slate-800 dark:bg-[#0c1527] dark:text-slate-200"
                  >
                    {batches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.batch_code} ({b.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {canUpload && (
                <button
                  onClick={() => {
                    setModalError(null);
                    setIsUploadModalOpen(true);
                  }}
                  className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                >
                  <Plus className="h-4 w-4" />
                  <span>Upload Certificate</span>
                </button>
              )}
            </div>
          }
        />

        {/* Global Error Banner */}
        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-medium text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800 dark:text-red-400"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Summary Metrics */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="CERTIFICATES FILED"
            value={evidenceList.length}
            icon={FileText}
            subtitle="Attached to active batch"
          />
          <MetricCard
            title="VERIFIED CERTIFICATES"
            value={evidenceList.filter((e) => e.status === "ACTIVE").length}
            icon={ShieldCheck}
            subtitle="Cryptographically authenticated"
          />
          <MetricCard
            title="HASH STANDARD"
            value="SHA-256"
            icon={CheckCircle2}
            subtitle="256-bit immutable integrity"
          />
          <MetricCard
            title="ACTIVE BATCH SCOPE"
            value={selectedBatch?.batch_code || "None"}
            icon={ExternalLink}
            subtitle={selectedBatch ? `Status: ${selectedBatch.status}` : "No batches in registry"}
          />
        </div>

        {/* Certificate Registry Table */}
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-[#0c1527]">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Laboratory Certificate Repository
              </h2>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Official third-party test reports validating purity, pollen spectrum, and moisture content.
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter certificate or hash..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-8.5 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-amber-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-200 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              <span className="ml-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                Loading laboratory evidence...
              </span>
            </div>
          )}

          {!loading && filteredEvidence.length === 0 && evidenceList.length === 0 && (
            <EmptyState
              icon={FileText}
              title="No laboratory evidence uploaded"
              description={
                selectedBatch
                  ? `No certificates have been attached to batch ${selectedBatch.batch_code} yet.`
                  : "Create batches to begin attaching laboratory test evidence."
              }
              actionLabel={canUpload && batches.length > 0 ? "Upload Certificate" : undefined}
              onAction={canUpload && batches.length > 0 ? () => setIsUploadModalOpen(true) : undefined}
              className="py-12"
            />
          )}

          {!loading && filteredEvidence.length === 0 && evidenceList.length > 0 && (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              No evidence records match &quot;{searchQuery}&quot;.
            </div>
          )}

          {!loading && filteredEvidence.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
                  <tr>
                    <th className="px-5 py-3">Certificate ID</th>
                    <th className="px-5 py-3">Test Summary</th>
                    <th className="px-5 py-3">Cryptographic SHA-256 Hash</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Uploaded</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredEvidence.map((ev) => (
                    <tr
                      key={ev.id}
                      className="transition-colors hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
                    >
                      <td className="px-5 py-3.5 font-bold text-slate-900 dark:text-white">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-amber-500" />
                          <span>{ev.certificate_id}</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 max-w-xs truncate text-slate-600 dark:text-slate-300">
                        {ev.test_summary}
                      </td>

                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1.5">
                          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                            {ev.file_hash_sha256.slice(0, 10)}...{ev.file_hash_sha256.slice(-8)}
                          </code>
                          <button
                            onClick={() => copyToClipboard(ev.file_hash_sha256, ev.id)}
                            title="Copy full hash"
                            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                          >
                            {copiedHash === ev.id ? (
                              <Check className="h-3.5 w-3.5 text-emerald-500" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      </td>

                      <td className="px-5 py-3.5">
                        <StatusBadge
                          status={ev.status}
                        />
                      </td>

                      <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                        {new Date(ev.uploaded_at).toLocaleDateString("en-GB", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </td>

                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleVerifyHash(ev.id)}
                            disabled={verifyingId === ev.id}
                            className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                          >
                            {verifyingId === ev.id ? (
                              <Loader2 className="h-3 w-3 animate-spin text-amber-500" />
                            ) : (
                              <ShieldCheck className="h-3 w-3 text-emerald-500" />
                            )}
                            <span>Verify Hash</span>
                          </button>

                          <button
                            onClick={() => handleDownload(ev.id, ev.file_name)}
                            disabled={downloadingId === ev.id}
                            className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                          >
                            {downloadingId === ev.id ? (
                              <Loader2 className="h-3 w-3 animate-spin text-amber-500" />
                            ) : (
                              <Download className="h-3 w-3 text-blue-500" />
                            )}
                            <span>PDF</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Verification Result Drawer */}
        {verificationResult && (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5 shadow-sm dark:border-emerald-900/60 dark:bg-[#071912]">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Cryptographic Hash Authentication
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Certificate ID: <span className="font-mono font-bold text-emerald-700 dark:text-emerald-400">{verificationResult.certificate_id}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setVerificationResult(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
              <div className="rounded-xl border border-emerald-200/80 bg-white/80 p-3 dark:border-emerald-800/40 dark:bg-slate-900/60">
                <span className="font-bold text-slate-500 dark:text-slate-400">AUTHENTICATION STATUS</span>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{verificationResult.is_hash_verified ? "SHA-256 Hash Match Verified" : "Hash Verification Mismatch"}</span>
                </div>
              </div>

              <div className="rounded-xl border border-emerald-200/80 bg-white/80 p-3 dark:border-emerald-800/40 dark:bg-slate-900/60">
                <span className="font-bold text-slate-500 dark:text-slate-400">LEGAL AUDIT CLAIM</span>
                <p className="mt-1 font-medium text-slate-700 dark:text-slate-300">
                  {verificationResult.claim_statement || verificationResult.claim}
                </p>
              </div>
            </div>

            <div className="mt-3 rounded-xl border border-emerald-200/80 bg-white/80 p-3 text-xs dark:border-emerald-800/40 dark:bg-slate-900/60">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-bold text-slate-500 dark:text-slate-400">VERIFIED HASH DIGEST:</span>
                <code className="font-mono text-[11px] text-slate-800 dark:text-slate-200 break-all">
                  {verificationResult.computed_hash_sha256}
                </code>
              </div>
            </div>
          </div>
        )}

        {/* Upload Modal */}
        {isUploadModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-[#0c1527]">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Upload className="h-5 w-5 text-amber-500" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Upload Lab Certificate PDF
                  </h3>
                </div>
                <button
                  onClick={() => setIsUploadModalOpen(false)}
                  className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={handleUploadSubmit} className="mt-4 space-y-4 text-xs">
                {modalError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                    {modalError}
                  </div>
                )}

                <div>
                  <label className="mb-1 block font-bold text-slate-700 dark:text-slate-300">
                    Target Processing Batch
                  </label>
                  <select
                    value={uploadBatchId}
                    onChange={(e) => setUploadBatchId(e.target.value)}
                    required
                    className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 font-semibold text-slate-700 focus:border-amber-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  >
                    {batches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.batch_code} ({b.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block font-bold text-slate-700 dark:text-slate-300">
                    Certificate ID (e.g. CERT-2026-001)
                  </label>
                  <input
                    type="text"
                    value={certId}
                    onChange={(e) => setCertId(e.target.value)}
                    placeholder="CERT-2026-XXX"
                    required
                    className="h-10 w-full rounded-lg border border-slate-200 px-3 text-slate-800 placeholder-slate-400 focus:border-amber-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  />
                </div>

                <div>
                  <label className="mb-1 block font-bold text-slate-700 dark:text-slate-300">
                    Test Summary / Scope
                  </label>
                  <textarea
                    rows={2}
                    value={testSummary}
                    onChange={(e) => setTestSummary(e.target.value)}
                    placeholder="Purity, moisture 17.2%, HMF 12 mg/kg, zero antibiotics."
                    required
                    className="w-full rounded-lg border border-slate-200 p-3 text-slate-800 placeholder-slate-400 focus:border-amber-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  />
                </div>

                <div>
                  <label className="mb-1 block font-bold text-slate-700 dark:text-slate-300">
                    Certificate PDF Document
                  </label>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setSelectedFile(e.target.files[0]);
                      }
                    }}
                    required
                    className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-800 focus:border-amber-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  />
                </div>

                <div className="mt-6 flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsUploadModalOpen(false)}
                    className="h-9 rounded-lg border border-slate-200 px-4 font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-4 font-bold text-white shadow-sm transition hover:bg-amber-600 disabled:opacity-50"
                  >
                    {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    <span>Upload Certificate</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
