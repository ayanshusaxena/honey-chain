/**
 * Honey Chain Centralized API Client
 * 
 * Single generic API client wrapping native fetch with:
 * - Configurable base URL from environment
 * - Automatic Authorization header injection via token provider
 * - JSON and Form-UrlEncoded body serialization
 * - Multipart file upload support
 * - Response parsing with exact ApiError preservation
 * - Zero hardcoded hosts or domain business rules
 */

import { getApiBaseUrl } from "./config";
import { ApiError, ApiErrorDetail } from "./errors";

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  skipAuth?: boolean;
}

export type TokenProvider = () => string | null | Promise<string | null>;
export type UnauthorizedHandler = (path: string) => void;

class ApiClient {
  private tokenProvider: TokenProvider | null = null;
  private unauthorizedHandler: UnauthorizedHandler | null = null;

  /**
   * Registers a token provider callback to supply the current bearer access token.
   */
  setTokenProvider(provider: TokenProvider | null): void {
    this.tokenProvider = provider;
  }

  /**
   * Registers a handler for when a 401 Unauthorized response is encountered.
   */
  setOnUnauthorized(handler: UnauthorizedHandler | null): void {
    this.unauthorizedHandler = handler;
  }

  /**
   * Builds the fully-qualified URL for a given relative path and optional query parameters.
   */
  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined | null>): string {
    const baseUrl = getApiBaseUrl();
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const fullPath = baseUrl ? `${baseUrl}${cleanPath}` : cleanPath;

    if (!params) {
      return fullPath;
    }

    const searchParams = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    }

    const queryString = searchParams.toString();
    return queryString ? `${fullPath}?${queryString}` : fullPath;
  }

  /**
   * Core request execution method
   */
  private async request<T>(
    method: HttpMethod,
    path: string,
    body?: unknown,
    options: RequestOptions = {},
    customContentType?: string | null,
  ): Promise<T> {
    const url = this.buildUrl(path, options.params);
    const headers: Record<string, string> = { ...options.headers };

    // Attach Authorization header if token is available and not explicitly skipped
    if (!options.skipAuth && this.tokenProvider) {
      const token = await this.tokenProvider();
      if (token && !headers["Authorization"]) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    let requestBody: BodyInit | undefined;

    if (body !== undefined && body !== null) {
      if (customContentType === "application/x-www-form-urlencoded") {
        headers["Content-Type"] = "application/x-www-form-urlencoded";
        if (typeof body === "string") {
          requestBody = body;
        } else if (body instanceof URLSearchParams) {
          requestBody = body.toString();
        } else if (typeof body === "object") {
          const formParams = new URLSearchParams();
          for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
            if (v !== undefined && v !== null) {
              formParams.append(k, String(v));
            }
          }
          requestBody = formParams.toString();
        }
      } else if (customContentType === null) {
        // Multipart/form-data: let the browser set boundary header automatically
        requestBody = body as FormData;
      } else {
        // Default: JSON serialization
        headers["Content-Type"] = "application/json";
        requestBody = JSON.stringify(body);
      }
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body: requestBody,
        signal: options.signal,
      });
    } catch (networkError) {
      throw new ApiError({
        message: networkError instanceof Error ? networkError.message : "Network request failed",
        status: 0,
        statusText: "Network Error",
        endpoint: path,
      });
    }

    // Handle non-2xx HTTP responses
    if (!response.ok) {
      let errorDetail: ApiErrorDetail | undefined;
      let errorMessage = `HTTP ${response.status} ${response.statusText}`;

      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === "object") {
          if ("detail" in errorJson) {
            errorDetail = (errorJson as { detail: ApiErrorDetail }).detail;
            if (typeof errorDetail === "string") {
              errorMessage = errorDetail;
            }
          } else if ("message" in errorJson && typeof errorJson.message === "string") {
            errorMessage = errorJson.message;
          }
        }
      } catch {
        // Response was not JSON (e.g. 502/504 HTML or empty body)
        try {
          const text = await response.text();
          if (text) {
            errorMessage = text.slice(0, 300);
          }
        } catch {
          // Keep default message
        }
      }

      // Notify unauthorized handler for session expiry / 401 redirection
      if (response.status === 401 && !options.skipAuth && this.unauthorizedHandler) {
        try {
          this.unauthorizedHandler(path);
        } catch {
          // Prevent handler failure from suppressing the ApiError throw
        }
      }

      throw new ApiError({
        message: errorMessage,
        status: response.status,
        statusText: response.statusText,
        endpoint: path,
        detail: errorDetail,
      });
    }

    // 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    // Check response content type
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }

    // For file downloads or text responses
    return (await response.text()) as unknown as T;
  }

  // ==========================================================================
  // Public HTTP Verb Methods
  // ==========================================================================

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, undefined, options);
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, body, options);
  }

  patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("PATCH", path, body, options);
  }

  put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("PUT", path, body, options);
  }

  delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", path, undefined, options);
  }

  /**
   * Specifically for OAuth2 Form URL-encoded requests (e.g. POST /auth/login)
   */
  postForm<T>(path: string, body: Record<string, unknown> | URLSearchParams, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, body, options, "application/x-www-form-urlencoded");
  }

  /**
   * Specifically for Multipart Form uploads (e.g. POST /batches/{id}/lab-evidence)
   */
  upload<T>(path: string, formData: FormData, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, formData, options, null);
  }
}

export const apiClient = new ApiClient();

