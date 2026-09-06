/**
 * Honey Chain Auth Foundation Abstraction
 *
 * Technical Authority: Sealed Backend Source (commit a4d794eafa56274308e500ec99ac3cd95322ab2c)
 * Contract: POST /auth/login (application/x-www-form-urlencoded: username, password)
 * Returns: TokenResponse { access_token: string, token_type: "bearer" }
 * Verified Roles: ADMIN, BEEKEEPER, PROCESSOR
 */

import { apiClient } from "./api-client";
import { LoginCredentials, TokenResponse, UserRole } from "../types/contracts";

const TOKEN_STORAGE_KEY = "honeychain_access_token";
const TOKEN_COOKIE_NAME = "honeychain_access_token";

export interface DecodedTokenPayload {
  sub: string; // User UUID
  role: UserRole;
  exp?: number;
}

/**
 * Synchronized token storage adapter for localStorage and Next.js middleware cookie
 */
export const tokenStorage = {
  get(): string | null {
    if (typeof window === "undefined") {
      return null;
    }
    try {
      return window.localStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  },

  set(token: string): void {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
      const isSecure = window.location.protocol === "https:";
      document.cookie = `${TOKEN_COOKIE_NAME}=${token}; path=/; SameSite=Lax${isSecure ? "; Secure" : ""}`;
      window.dispatchEvent(new Event("storage"));
      window.dispatchEvent(new CustomEvent("auth-state-changed", { detail: { token } }));
    } catch {
      // Ignore local storage write errors
    }
  },

  remove(): void {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      document.cookie = `${TOKEN_COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
      window.dispatchEvent(new Event("storage"));
      window.dispatchEvent(new CustomEvent("auth-state-changed", { detail: { token: null } }));
    } catch {
      // Ignore local storage remove errors
    }
  },
};

/**
 * Parse JWT payload without cryptographic verification (for UI presentation only).
 * True authentication and authorization boundaries are enforced strictly by the backend.
 */
export function parseTokenPayload(token: string): DecodedTokenPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) {
      return null;
    }
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    );
    return JSON.parse(jsonPayload) as DecodedTokenPayload;
  } catch {
    return null;
  }
}

/**
 * Executes login against POST /auth/login using OAuth2 form encoding.
 * On success, stores the returned bearer token and configures the API client.
 */
export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.append("username", credentials.username);
  form.append("password", credentials.password);

  const tokenResponse = await apiClient.postForm<TokenResponse>("/auth/login", form, {
    skipAuth: true,
  });

  if (tokenResponse && tokenResponse.access_token) {
    tokenStorage.set(tokenResponse.access_token);
  }

  return tokenResponse;
}

/**
 * Clears the stored bearer access token and cookie.
 */
export function logout(): void {
  tokenStorage.remove();
}

/**
 * Returns the currently stored bearer access token or null if unauthenticated.
 */
export function getAccessToken(): string | null {
  return tokenStorage.get();
}

/**
 * Returns true if an access token exists and has not expired.
 */
export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) {
    return false;
  }
  const payload = parseTokenPayload(token);
  if (!payload) {
    return false;
  }
  if (payload.exp && Date.now() >= payload.exp * 1000) {
    tokenStorage.remove();
    return false;
  }
  return true;
}

/**
 * Returns the current authenticated user's role and ID if token is valid.
 */
export function getCurrentSession(): { userId: string; role: UserRole } | null {
  const token = getAccessToken();
  if (!token) {
    return null;
  }
  const payload = parseTokenPayload(token);
  if (!payload || !payload.sub || !payload.role) {
    return null;
  }
  return {
    userId: payload.sub,
    role: payload.role,
  };
}

/**
 * Handles 401 Unauthorized responses from backend by purging invalid session
 * and redirecting the browser to /login with intended return route.
 */
export function handleUnauthorized(_path?: string): void {
  logout();
  if (typeof window !== "undefined") {
    const current = _path || window.location.pathname;
    if (current !== "/login") {
      const next = encodeURIComponent(current);
      // Non-React service layer redirect to cleanly clear client state
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?next=${next}`;
    }
  }
}

// Automatically register token provider and 401 handler on the shared API client
apiClient.setTokenProvider(() => getAccessToken());
apiClient.setOnUnauthorized((path) => handleUnauthorized(path));
