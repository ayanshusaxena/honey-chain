"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
}

const sizeClasses = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

export function LoadingSpinner({
  size = "md",
  label = "Loading...",
  className = "",
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className={`flex items-center justify-center gap-2.5 text-slate-500 ${className}`}
    >
      <Loader2 className={`animate-spin text-amber-500 ${sizeClasses[size]}`} />
      {label && <span className="text-sm font-medium">{label}</span>}
    </div>
  );
}

