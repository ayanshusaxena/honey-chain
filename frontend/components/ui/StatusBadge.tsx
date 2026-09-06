"use client";

import React from "react";

export type DomainStatus =
  | "ACTIVE"
  | "INACTIVE"
  | "MAINTENANCE"
  | "HOLD"
  | "RECALL"
  | "REVOKED"
  | "FAILED"
  | "COLLECTED"
  | "PROCESSING"
  | "PENDING"
  | "VERIFIED"
  | "NOMINAL"
  | "PASSED"
  | "SUPERSEDED"
  | string;

interface StatusBadgeProps {
  status: DomainStatus;
  className?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, className = "", size = "md" }: StatusBadgeProps) {
  const norm = (status || "").toUpperCase();

  let colorClasses = "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";

  if (["ACTIVE", "VERIFIED", "NOMINAL", "PASSED"].includes(norm)) {
    colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";
  } else if (["MAINTENANCE", "HOLD", "REVIEW"].includes(norm)) {
    colorClasses = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
  } else if (["RECALL", "REVOKED", "FAILED", "SUSPENDED"].includes(norm)) {
    colorClasses = "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60";
  } else if (["COLLECTED", "PROCESSING", "PENDING"].includes(norm)) {
    colorClasses = "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/60";
  }

  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center font-bold tracking-wider uppercase rounded-md border shadow-xs transition-colors ${sizeClasses} ${colorClasses} ${className}`}
    >
      {norm}
    </span>
  );
}
