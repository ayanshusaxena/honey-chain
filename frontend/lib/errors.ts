/**
 * Honey Chain Frontend Error Foundation
 *
 * Preserves exact HTTP status codes and error payloads returned by the FastAPI backend.
 * Distinguishes authentication, authorization, not found, conflict, validation, and server errors.
 */

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export type ApiErrorDetail = string | ValidationErrorItem[] | Record<string, unknown>;

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly endpoint: string;
  readonly detail?: ApiErrorDetail;

  constructor(params: {
    message: string;
    status: number;
    statusText: string;
    endpoint: string;
    detail?: ApiErrorDetail;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.status = params.status;
    this.statusText = params.statusText;
    this.endpoint = params.endpoint;
    this.detail = params.detail;

    // Maintains proper stack trace for where error was thrown (only in V8/Node/Chrome)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError);
    }
  }

  /**
   * 400 Bad Request
   */
  get isBadRequest(): boolean {
    return this.status === 400;
  }

  /**
   * 401 Unauthorized (Invalid or expired bearer token, bad credentials)
   */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /**
   * 403 Forbidden (Insufficient permissions / role boundary / cross-user access)
   */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /**
   * 404 Not Found (Resource does not exist)
   */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /**
   * 409 Conflict (Duplicate code, already finalized, or conflicting state)
   */
  get isConflict(): boolean {
    return this.status === 409;
  }

  /**
   * 422 Unprocessable Entity (FastAPI / Pydantic schema validation failure or domain rule violation)
   */
  get isValidationError(): boolean {
    return this.status === 422;
  }

  /**
   * 500+ Internal Server Error / Service Unavailable
   */
  get isServerError(): boolean {
    return this.status >= 500;
  }

  /**
   * Formats a user-friendly error message from FastAPI's detail payload
   */
  get displayMessage(): string {
    if (typeof this.detail === "string" && this.detail.trim().length > 0) {
      return this.detail;
    }

    if (Array.isArray(this.detail)) {
      // Pydantic validation error array
      const items = this.detail as ValidationErrorItem[];
      return items
        .map((item) => {
          const loc = item.loc
            ? item.loc.filter((p) => p !== "body" && p !== "query").join(".")
            : "";
          return loc ? `${loc}: ${item.msg}` : item.msg;
        })
        .join("; ");
    }

    if (this.detail && typeof this.detail === "object") {
      try {
        const obj = this.detail as Record<string, unknown>;
        if ("message" in obj && typeof obj.message === "string") {
          return obj.message;
        }
        if ("error" in obj && typeof obj.error === "string") {
          return obj.error;
        }
      } catch {
        // Fall back to message
      }
    }

    if (this.message && this.message.trim().length > 0) {
      return this.message;
    }

    return `HTTP ${this.status} ${this.statusText}`;
  }
}
