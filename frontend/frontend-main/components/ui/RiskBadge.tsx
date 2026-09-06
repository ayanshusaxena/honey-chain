"use client";

import React from "react";
import type { RiskLevel } from "../../types/contracts";

interface RiskBadgeProps {
  level: RiskLevel | string;
  score?: number | null;
  className?: string;
}

export function RiskBadge({ level, score, className = "" }: RiskBadgeProps) {
  const norm = (level || "LOW").toUpperCase();

  let colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";

  if (norm === "MEDIUM") {
    colorClasses = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
  } else if (norm === "HIGH" || norm === "CRITICAL") {
    colorClasses = "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-xs font-bold tracking-wider uppercase ${colorClasses} ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      <span>{norm}</span>
      {typeof score === "number" && (
        <span className="opacity-75 font-mono">({score.toFixed(2)})</span>
      )}
    </span>
  );
}
