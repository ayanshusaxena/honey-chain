"use client";

import React from "react";
import { LucideIcon, ArrowRight } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconBg?: string;
  iconColor?: string;
  onClick?: () => void;
  className?: string;
  testId?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBg = "bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400",
  iconColor = "",
  onClick,
  className = "",
  testId,
}: MetricCardProps) {
  const Tag = onClick ? "button" : "div";

  return (
    <Tag
      onClick={onClick}
      data-testid={testId}
      className={`group flex flex-col justify-between rounded-xl border border-slate-200/80 bg-white p-5 text-left shadow-sm transition hover:border-amber-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-amber-500/20 dark:border-slate-800/90 dark:bg-slate-900/90 dark:hover:border-amber-500/40 ${onClick ? "cursor-pointer" : ""} ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {title}
        </span>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${iconBg}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>

      <div className="mt-4">
        <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
          {value}
        </p>
        {subtitle && (
          <div className="mt-1 flex items-center justify-between">
            <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
            {onClick && (
              <ArrowRight className="h-4 w-4 text-slate-400 opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100 dark:text-slate-500" />
            )}
          </div>
        )}
      </div>
    </Tag>
  );
}
