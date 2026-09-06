/**
 * Root route handler for Honey Chain.
 *
 * Redirects to /login (unauthenticated) or /dashboard (authenticated).
 * Middleware handles the actual server-side redirect; this page is a
 * fallback for any edge case where middleware did not redirect.
 *
 * NOTE: middleware.ts already handles / redirect. This page acts as
 * a safety net for static export scenarios.
 */
import { redirect } from "next/navigation";

export default function RootPage() {
  // Middleware handles this redirect at the edge.
  // If reached (e.g. in dev without middleware), redirect to login.
  redirect("/login");
}
