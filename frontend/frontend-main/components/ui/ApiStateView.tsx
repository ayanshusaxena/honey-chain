"use client";

import React from "react";
import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorMessage } from "./ErrorMessage";
import { ApiError } from "../../lib/errors";

export interface ApiStateViewProps {
  isLoading: boolean;
  error?: ApiError | Error | string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: React.ReactNode;
  loadingLabel?: string;
}

export function ApiStateView({
  isLoading,
  error,
  isEmpty = false,
  emptyMessage = "No data found.",
  onRetry,
  children,
  loadingLabel = "Loading data...",
}: ApiStateViewProps) {
  if (isLoading) {
    return (
      <div className="flex min-h-[160px] items-center justify-center p-6">
        <LoadingSpinner size="md" label={loadingLabel} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <ErrorMessage error={error} onRetry={onRetry} />
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="flex min-h-[140px] items-center justify-center rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-400">
        {emptyMessage}
      </div>
    );
  }

  return <>{children}</>;
}

