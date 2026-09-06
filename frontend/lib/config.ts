/**
 * Honey Chain Frontend Configuration
 *
 * Handles reading the backend API base URL from browser-accessible environment variables.
 * Never hardcodes hostnames, ports, or protocol schemes.
 */

/**
 * Default proxy prefix for same-origin requests handled by Next.js rewrites.
 */
const DEFAULT_PROXY_API_PREFIX = "/api";

/**
 * Returns the configured base URL for the backend API.
 * In same-origin mode (default), returns "/api" which Next.js proxies to backend.
 * If NEXT_PUBLIC_API_URL is explicitly configured, it overrides this behavior.
 * Strips any trailing slashes to ensure consistent URL concatenation.
 */
export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, "");
  }
  return DEFAULT_PROXY_API_PREFIX;
}

/**
 * Immutable configuration snapshot
 */
export const API_CONFIG = {
  get baseUrl(): string {
    return getApiBaseUrl();
  },
  isConfigured(): boolean {
    return getApiBaseUrl().length > 0;
  },
} as const;
