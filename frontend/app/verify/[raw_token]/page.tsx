"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  ShieldAlert,
  FileCheck,
  Blocks,
  MapPin,
  Calendar,
  Package,
  Layers,
  Sun,
  Moon,
  Copy,
  Check,
  Sparkles,
} from "lucide-react";
import { apiClient } from "../../../lib/api-client";
import { ApiError } from "../../../lib/errors";
import { useTheme } from "../../../components/ThemeProvider";
import type { ConsumerVerificationResponse } from "../../../types/contracts";

export default function ConsumerVerificationPage() {
  const params = useParams();
  const rawToken = Array.isArray(params?.raw_token)
    ? params.raw_token[0]
    : (params?.raw_token as string) || "";

  const { theme, toggleTheme } = useTheme();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ConsumerVerificationResponse | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.resolve().then(() => {
      if (!isMounted) return;

      if (!rawToken) {
        setLoading(false);
        setErrorStatus(404);
        setErrorMessage("No verification token provided");
        return;
      }

      setLoading(true);
      setErrorStatus(null);
      setErrorMessage(null);

      apiClient
        .verifyConsumerToken(rawToken)
        .then((res) => {
          if (isMounted) {
            setData(res);
            setLoading(false);
          }
        })
        .catch((err) => {
          if (!isMounted) return;
          setLoading(false);
          if (err instanceof ApiError) {
            setErrorStatus(err.status);
            setErrorMessage(err.message);
          } else {
            setErrorStatus(500);
            setErrorMessage("Failed to load verification record from network");
          }
        });
    });

    return () => {
      isMounted = false;
    };
  }, [rawToken]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return "N/A";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-honey-bg)] text-[var(--color-honey-text)] transition-colors duration-200">
      {/* Top Consumer Header */}
      <header className="border-b border-[var(--color-honey-border)] bg-[var(--color-honey-card)]/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 shadow-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-lg text-[var(--color-honey-text)] tracking-tight">
                Honey Chain
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                Consumer Provenance
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="p-2 rounded-lg border border-[var(--color-honey-border)] bg-[var(--color-honey-card)] hover:bg-[var(--color-honey-border)]/20 text-[var(--color-honey-text-muted)] hover:text-[var(--color-honey-text)] transition-colors cursor-pointer"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* 1. Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-12 h-12 rounded-full border-4 border-amber-500/20 border-t-amber-500 animate-spin mb-4" />
            <h2 className="text-lg font-semibold text-[var(--color-honey-text)]">
              Verifying Record...
            </h2>
            <p className="text-sm text-[var(--color-honey-text-muted)] mt-1 max-w-sm">
              Querying cryptographic provenance certificates and blockchain verification records.
            </p>
          </div>
        )}

        {/* 2. 410 Revoked State */}
        {!loading && errorStatus === 410 && (
          <div className="max-w-2xl mx-auto bg-rose-500/10 border-2 border-rose-500/30 rounded-2xl p-6 sm:p-8 text-center shadow-lg">
            <div className="w-16 h-16 rounded-2xl bg-rose-500/20 text-rose-600 dark:text-rose-400 flex items-center justify-center mx-auto mb-4">
              <ShieldAlert className="w-9 h-9" />
            </div>
            <h1 className="text-2xl font-bold text-rose-700 dark:text-rose-300">
              QR Code Revoked
            </h1>
            <p className="mt-3 text-sm sm:text-base text-rose-600/90 dark:text-rose-400/90 leading-relaxed">
              This verification QR token has been revoked by platform administrators and is no longer valid.
            </p>
            <div className="mt-6 p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400 text-left">
              <strong>Notice:</strong> If you purchased this product with an active guarantee, please contact the retailer or distributor immediately quoting the packaging lot reference.
            </div>
          </div>
        )}

        {/* 3. 404 Not Found State */}
        {!loading && errorStatus === 404 && (
          <div className="max-w-2xl mx-auto bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 sm:p-8 text-center shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-[var(--color-honey-text)]">
              Verification Record Not Found
            </h1>
            <p className="mt-3 text-sm text-[var(--color-honey-text-muted)] max-w-md mx-auto">
              The verification token provided is unrecognized, invalid, or expired.
            </p>
          </div>
        )}

        {/* 4. Other Error State */}
        {!loading && errorStatus && errorStatus !== 404 && errorStatus !== 410 && (
          <div className="max-w-2xl mx-auto bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6 sm:p-8 text-center shadow-sm">
            <AlertTriangle className="w-10 h-10 text-amber-600 dark:text-amber-400 mx-auto mb-3" />
            <h1 className="text-xl font-bold text-[var(--color-honey-text)]">
              Verification Unavailable
            </h1>
            <p className="text-sm text-[var(--color-honey-text-muted)] mt-2">
              {errorMessage || "Could not complete verification. Please check your internet connection and try again."}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="mt-5 px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-medium text-sm transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* 5. Verified / Response Content */}
        {!loading && data && (
          <div className="space-y-8 animate-in fade-in duration-300">
            {/* Status Hero Banner */}
            {data.verification_status === "VERIFIED" && (
              <div className="bg-gradient-to-r from-emerald-500/15 via-emerald-500/10 to-transparent border-2 border-emerald-500/30 rounded-3xl p-6 sm:p-8 shadow-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
                  <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 shadow-inner">
                    <ShieldCheck className="w-9 h-9" />
                  </div>
                  <div className="space-y-1">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                      Verification Successful
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-[var(--color-honey-text)] tracking-tight">
                      Product Traceability Verified
                    </h1>
                    <p className="text-sm text-[var(--color-honey-text-muted)] max-w-2xl">
                      Recorded batch information has passed end-to-end cryptographic verification, documented apiary harvests, laboratory test records, and immutable on-chain recordation.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {data.verification_status === "HOLD" && (
              <div className="bg-amber-500/15 border-2 border-amber-500/40 rounded-3xl p-6 sm:p-8 shadow-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
                  <div className="w-16 h-16 rounded-2xl bg-amber-500/20 border border-amber-500/30 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                    <AlertTriangle className="w-9 h-9" />
                  </div>
                  <div className="space-y-1">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                      Notice: Batch On Hold
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-amber-700 dark:text-amber-300 tracking-tight">
                      Distribution Temporarily Paused
                    </h1>
                    <p className="text-sm text-amber-800/90 dark:text-amber-200/90 max-w-2xl leading-relaxed font-medium">
                      {data.warning || "Notice: This honey batch is currently on administrative HOLD. Distribution is temporarily paused."}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {data.verification_status === "RECALLED" && (
              <div className="bg-rose-500/15 border-2 border-rose-500/40 rounded-3xl p-6 sm:p-8 shadow-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
                  <div className="w-16 h-16 rounded-2xl bg-rose-500/20 border border-rose-500/30 text-rose-600 dark:text-rose-400 flex items-center justify-center shrink-0">
                    <AlertOctagon className="w-9 h-9" />
                  </div>
                  <div className="space-y-1">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/30">
                      Safety Alert: Batch Recalled
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-rose-700 dark:text-rose-300 tracking-tight">
                      DO NOT CONSUME
                    </h1>
                    <p className="text-sm text-rose-800/90 dark:text-rose-200/90 max-w-2xl font-medium leading-relaxed">
                      {data.warning || "WARNING: This honey batch has been RECALLED. Do not consume this product."}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Product & Batch Summary Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Packaging Lot Card */}
              <div className="bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 font-semibold text-sm">
                  <Package className="w-4 h-4" />
                  <span>Packaging Unit & Lot</span>
                </div>

                <div className="space-y-3">
                  <div>
                    <div className="text-xs text-[var(--color-honey-text-muted)] uppercase tracking-wider font-semibold">
                      Package Lot Code
                    </div>
                    <div className="text-lg font-bold text-[var(--color-honey-text)] font-mono mt-0.5">
                      {data.packaging_lot.package_lot_code}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[var(--color-honey-border)]/60">
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Package Size</div>
                      <div className="text-sm font-semibold text-[var(--color-honey-text)] mt-0.5">
                        {data.packaging_lot.package_size_grams}g ({data.packaging_lot.unit})
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Packaged Qty</div>
                      <div className="text-sm font-semibold text-[var(--color-honey-text)] mt-0.5">
                        {data.packaging_lot.quantity} units ({data.packaging_lot.packaged_quantity_kg} kg)
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Packaging Date</div>
                      <div className="text-sm font-semibold text-[var(--color-honey-text)] mt-0.5">
                        {formatDate(data.packaging_lot.created_at)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Batch Processing Card */}
              <div className="bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 font-semibold text-sm">
                  <Layers className="w-4 h-4" />
                  <span>Processing Batch</span>
                </div>

                <div className="space-y-3">
                  <div>
                    <div className="text-xs text-[var(--color-honey-text-muted)] uppercase tracking-wider font-semibold">
                      Batch Code
                    </div>
                    <div className="text-lg font-bold text-[var(--color-honey-text)] font-mono mt-0.5">
                      {data.batch.batch_code}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[var(--color-honey-border)]/60">
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Batch Status</div>
                      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold mt-1 bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                        {data.batch.status}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Finalization</div>
                      <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Finalized
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-[var(--color-honey-text-muted)]">Finalized Date</div>
                      <div className="text-sm font-semibold text-[var(--color-honey-text)] mt-0.5">
                        {formatDate(data.batch.finalized_at || data.batch.created_at)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Geographic Provenance / Harvests */}
            <div className="bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 font-semibold text-sm">
                  <MapPin className="w-4 h-4" />
                  <span>Geographic Origin & Apiary Harvests</span>
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--color-honey-border)]/40 text-[var(--color-honey-text-muted)]">
                  {data.provenance.length} Harvest Source{data.provenance.length === 1 ? "" : "s"}
                </span>
              </div>

              {data.provenance.length === 0 ? (
                <p className="text-xs text-[var(--color-honey-text-muted)]">
                  No specific geographic harvest records linked.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {data.provenance.map((prov, i) => (
                    <div
                      key={i}
                      className="p-3.5 rounded-xl border border-[var(--color-honey-border)]/70 bg-[var(--color-honey-bg)] space-y-2"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono font-bold text-[var(--color-honey-text)]">
                          {prov.harvest_code}
                        </span>
                        <span className="text-[var(--color-honey-text-muted)] flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {prov.harvest_date}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1 pt-1">
                        {prov.regions && prov.regions.length > 0 ? (
                          prov.regions.map((reg, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20"
                            >
                              <MapPin className="w-2.5 h-2.5" /> {reg}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-[var(--color-honey-text-muted)] italic">
                            Verified Origin Region
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Laboratory Certification Evidence */}
            <div className="bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 font-semibold text-sm">
                  <FileCheck className="w-4 h-4" />
                  <span>Accredited Laboratory Evidence</span>
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--color-honey-border)]/40 text-[var(--color-honey-text-muted)]">
                  {data.lab_evidence.length} Report{data.lab_evidence.length === 1 ? "" : "s"}
                </span>
              </div>

              {data.lab_evidence.length === 0 ? (
                <p className="text-xs text-[var(--color-honey-text-muted)]">
                  No public laboratory reports registered for this batch.
                </p>
              ) : (
                <div className="space-y-3">
                  {data.lab_evidence.map((lab, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-xl border border-[var(--color-honey-border)] bg-[var(--color-honey-bg)] flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="space-y-1 max-w-xl">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-sm text-[var(--color-honey-text)]">
                            {lab.certificate_id}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                            {lab.status}
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-[var(--color-honey-text)] font-medium">
                          {lab.test_summary}
                        </p>
                        <div className="text-xs text-[var(--color-honey-text-muted)] flex items-center gap-2 pt-1 font-mono">
                          <span>SHA-256: {lab.file_hash_sha256.slice(0, 16)}...{lab.file_hash_sha256.slice(-16)}</span>
                          <button
                            onClick={() => handleCopy(lab.file_hash_sha256, `lab-${i}`)}
                            title="Copy complete SHA-256 hash"
                            className="p-1 text-[var(--color-honey-text-muted)] hover:text-[var(--color-honey-text)] cursor-pointer"
                          >
                            {copiedHash === `lab-${i}` ? (
                              <Check className="w-3 h-3 text-emerald-500" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </div>
                      <div className="text-xs text-[var(--color-honey-text-muted)] sm:text-right shrink-0">
                        <div>File: {lab.file_name}</div>
                        <div>Uploaded: {formatDate(lab.uploaded_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Blockchain Notarization Records */}
            <div className="bg-[var(--color-honey-card)] border border-[var(--color-honey-border)] rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 font-semibold text-sm">
                  <Blocks className="w-4 h-4" />
                  <span>On-Chain Blockchain Audit Records</span>
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--color-honey-border)]/40 text-[var(--color-honey-text-muted)]">
                  {data.blockchain_records.length} Record{data.blockchain_records.length === 1 ? "" : "s"}
                </span>
              </div>

              {data.blockchain_records.length === 0 ? (
                <p className="text-xs text-[var(--color-honey-text-muted)]">
                  Batch recorded on platform audit trail; on-chain notarization pending network block confirmation.
                </p>
              ) : (
                <div className="space-y-3">
                  {data.blockchain_records.map((bc, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-xl border border-[var(--color-honey-border)] bg-[var(--color-honey-bg)] flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[var(--color-honey-text)] uppercase">
                            {bc.event_type}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                            {bc.status}
                          </span>
                          <span className="text-xs text-[var(--color-honey-text-muted)] font-mono">
                            Block #{bc.block_number ?? "-"}
                          </span>
                        </div>

                        {bc.transaction_hash && (
                          <div className="text-xs font-mono text-[var(--color-honey-text-muted)] flex items-center gap-2 break-all">
                            <span>Tx: {bc.transaction_hash.slice(0, 18)}...{bc.transaction_hash.slice(-12)}</span>
                            <button
                              onClick={() => handleCopy(bc.transaction_hash!, `bc-${i}`)}
                              title="Copy full transaction hash"
                              className="p-1 text-[var(--color-honey-text-muted)] hover:text-[var(--color-honey-text)] cursor-pointer"
                            >
                              {copiedHash === `bc-${i}` ? (
                                <Check className="w-3 h-3 text-emerald-500" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        )}
                      </div>

                      <div className="text-xs text-[var(--color-honey-text-muted)] sm:text-right shrink-0">
                        <div className="font-medium text-[var(--color-honey-text)]">{bc.network}</div>
                        <div>Notarized: {formatDate(bc.recorded_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--color-honey-border)] bg-[var(--color-honey-card)]/50 mt-16 py-8 text-center text-xs text-[var(--color-honey-text-muted)]">
        <div className="max-w-5xl mx-auto px-4">
          <p>
            Honey Chain Cryptographic Provenance Platform • Secured by Ethereum Smart Contracts & IoT Honey Quality Verification
          </p>
          <p className="mt-1 text-[11px] opacity-70">
            Zero-Knowledge Consumer Verification • No User PII or Apiary GPS Coordinates Stored
          </p>
        </div>
      </footer>
    </div>
  );
}
