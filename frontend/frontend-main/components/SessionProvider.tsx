/**
 * Honey Chain Session Context
 *
 * Provides client-side session state (userId, role) derived from the stored
 * JWT payload. This is for UI presentation and visibility only.
 * True authorization is enforced by the backend on every API call.
 *
 * Verified roles (backend/app/models/enums.py):
 *   ADMIN, BEEKEEPER, PROCESSOR
 */
"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { getCurrentSession, isAuthenticated } from "../lib/auth";
import type { UserRole } from "../types/contracts";

export interface SessionState {
  userId: string | null;
  role: UserRole | null;
  authenticated: boolean;
}

const SessionContext = createContext<SessionState>({
  userId: null,
  role: null,
  authenticated: false,
});

function readCurrentSession(): SessionState {
  if (typeof window === "undefined") {
    return { userId: null, role: null, authenticated: false };
  }
  if (!isAuthenticated()) {
    return { userId: null, role: null, authenticated: false };
  }
  const s = getCurrentSession();
  return {
    userId: s?.userId ?? null,
    role: s?.role ?? null,
    authenticated: Boolean(s),
  };
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(readCurrentSession);

  const refreshSession = useCallback(() => {
    setSession(readCurrentSession());
  }, []);

  useEffect(() => {
    window.addEventListener("storage", refreshSession);
    window.addEventListener("auth-state-changed", refreshSession);
    return () => {
      window.removeEventListener("storage", refreshSession);
      window.removeEventListener("auth-state-changed", refreshSession);
    };
  }, [refreshSession]);

  return (
    <SessionContext.Provider value={session}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  return useContext(SessionContext);
}
