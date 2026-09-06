"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

interface BackNavigationProps {
  fallbackUrl?: string;
  label?: string;
  className?: string;
}

export function BackNavigation({
  fallbackUrl = "/dashboard",
  label = "Back",
  className = "",
}: BackNavigationProps) {
  const router = useRouter();

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push(fallbackUrl);
    }
  };

  return (
    <button
      onClick={handleBack}
      type="button"
      aria-label={`Navigate back${fallbackUrl ? ` to ${fallbackUrl}` : ""}`}
      className={`inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-slate-800 dark:bg-slate-900/90 dark:text-slate-300 dark:hover:border-slate-700 dark:hover:bg-slate-800 ${className}`}
    >
      <ArrowLeft className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400" />
      <span>{label}</span>
    </button>
  );
}
