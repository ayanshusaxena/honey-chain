"use client";

import React, { useEffect, useState } from "react";
import QRCode from "qrcode";
import {
  QrCode,
  Copy,
  Check,
  Printer,
  ExternalLink,
  X,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";

interface QrCodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  verificationUrl: string;
  packageLotCode: string;
  batchCode?: string;
}

export function QrCodeModal({
  isOpen,
  onClose,
  verificationUrl,
  packageLotCode,
  batchCode,
}: QrCodeModalProps) {
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    Promise.resolve().then(() => {
      if (!active) return;
      if (!verificationUrl || !isOpen) {
        setQrDataUrl(null);
        return;
      }

      QRCode.toDataURL(verificationUrl, {
        width: 280,
        margin: 2,
        color: {
          dark: "#1e293b",
          light: "#ffffff",
        },
      })
        .then((url) => {
          if (active) {
            setQrDataUrl(url);
            setError(null);
          }
        })
        .catch((err) => {
          if (active) {
            console.error("Failed to generate QR code", err);
            setError("Could not render QR image");
          }
        });
    });

    return () => {
      active = false;
    };
  }, [verificationUrl, isOpen]);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(verificationUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      alert("Please allow popups to print certificate");
      return;
    }

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Honey Chain Packaging QR Certificate - ${packageLotCode}</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              padding: 40px;
              color: #1e293b;
            }
            .cert-card {
              border: 2px solid #f59e0b;
              border-radius: 16px;
              padding: 32px;
              text-align: center;
              max-width: 400px;
              box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }
            h2 { margin: 0 0 8px 0; color: #b45309; }
            p { margin: 4px 0; font-size: 13px; color: #64748b; }
            .code { font-family: monospace; font-weight: bold; font-size: 16px; color: #0f172a; margin: 8px 0; }
            img { margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 8px; }
            .url { font-family: monospace; font-size: 10px; word-break: break-all; color: #475569; }
          </style>
        </head>
        <body>
          <div class="cert-card">
            <h2>Honey Chain</h2>
            <p>Cryptographic Provenance Guarantee</p>
            <div class="code">Lot: ${packageLotCode}</div>
            ${batchCode ? `<p>Batch: <strong>${batchCode}</strong></p>` : ""}
            ${qrDataUrl ? `<img src="${qrDataUrl}" width="220" height="220" />` : ""}
            <p class="url">${verificationUrl}</p>
            <p style="margin-top: 16px; font-size: 11px; color: #94a3b8;">
              Scan to verify apiary origins, purity test certificates, and on-chain blockchain records.
            </p>
          </div>
          <script>
            window.onload = function() { window.print(); }
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-2xl dark:border-amber-900/50 dark:bg-slate-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-white shadow-xs">
              <QrCode className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Packaging QR Token Issued
              </h3>
              <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                Lot: {packageLotCode}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Notice Alert */}
        <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
          <ShieldCheck className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold">Single-Use Token Exposure:</span>
            <p className="text-[11px] leading-relaxed opacity-90">
              This raw token is cryptographically secure (256-bit entropy) and exposed <strong>ONLY ONCE</strong> upon generation. Only its SHA-256 hash is retained in the database.
            </p>
          </div>
        </div>

        {/* QR Code Canvas / Image Display */}
        <div className="my-4 flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-950/40">
          {error ? (
            <div className="flex items-center gap-2 text-xs text-red-500 py-8">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          ) : qrDataUrl ? (
            <div className="bg-white p-2 rounded-xl shadow-xs border border-slate-200 dark:border-slate-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrDataUrl}
                alt={`QR code for ${packageLotCode}`}
                width={200}
                height={200}
                className="rounded-lg"
              />
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-xs text-slate-400">
              Generating QR matrix...
            </div>
          )}

          <div className="mt-3 w-full text-center">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Consumer Verification URL
            </span>
            <div
              data-testid="verification-url"
              className="mt-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 break-all select-all"
            >
              {verificationUrl}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <a
            href={verificationUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-300 transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open Consumer Page</span>
          </a>

          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
            >
              <Printer className="h-3.5 w-3.5 text-slate-500" />
              <span>Print</span>
            </button>

            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-amber-600 transition-colors cursor-pointer"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy URL</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
