"use client";

import { useSyncExternalStore } from "react";
import { getCurrentSession, getAccessToken } from "./auth";
import type { UserRole } from "../types/contracts";

export interface SessionData {
  userId: string;
  role: UserRole;
}

let cachedSession: SessionData | null = null;
let lastToken: string | null = null;

function getSessionSnapshot(): SessionData | null {
  if (typeof window === "undefined") return null;
  const token = getAccessToken();
  if (token !== lastToken) {
    lastToken = token;
    cachedSession = getCurrentSession();
  }
  return cachedSession;
}

export const sessionStore = {
  subscribe(listener: () => void) {
    if (typeof window === "undefined") return () => {};
    const onAuth = () => {
      lastToken = null; // Invalidate cache on auth changes
      listener();
    };
    window.addEventListener("storage", onAuth);
    window.addEventListener("auth-state-changed", onAuth);
    return () => {
      window.removeEventListener("storage", onAuth);
      window.removeEventListener("auth-state-changed", onAuth);
    };
  },
  getSnapshot(): SessionData | null {
    return getSessionSnapshot();
  },
  getServerSnapshot(): SessionData | null {
    return null;
  },
};

/**
 * Hook to access authenticated user session with deterministic SSR and client hydration
 */
export function useAppSession(): SessionData | null {
  return useSyncExternalStore(
    sessionStore.subscribe,
    sessionStore.getSnapshot,
    sessionStore.getServerSnapshot
  );
}
