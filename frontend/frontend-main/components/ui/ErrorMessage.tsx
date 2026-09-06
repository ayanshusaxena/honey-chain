"use client";

import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { ApiError } from "../../lib/errors";

export interface ErrorMessageProps {
  error: ApiError | Error | string | null | undefined;
  onRetry?: () => void;
  className?: string;
}

export function ErrorMessage({ error, onRetry, className = "" }: ErrorMessageProps) {
  if (!error) {
    return null;
  }

  let message = "";
  let statusCode: number | null = null;

  if (error instanceof ApiError) {
    message = error.displayMessage;
    statusCode = error.status;
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === "string") {
    message = error;
  }

  return (
    <div
      role="alert"
      className={`flex flex-col gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between ${className}`}
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">Error</span>
            {statusCode !== null && statusCode > 0 && (
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-mono font-medium text-red-600">
                HTTP {statusCode}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-red-600 sm:text-sm">{message}</p>
        </div>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-red-100 px-3 text-xs font-semibold text-red-700 transition hover:bg-red-200"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      )}
    </div>
  );
}

