/**
 * Honey Chain Next.js App Router Middleware
 *
 * Provides frontend route protection for authenticated routes.
 * NOTE: This is a UX convenience layer only. True authorization is
 * enforced strictly by the backend. Frontend route protection does
 * not replace backend JWT validation.
 *
 * Strategy:
 * - Protected routes: require token cookie to be present
 * - /login: always accessible; redirect authenticated users to /dashboard
 * - / (root): redirect based on token presence
 */

import { NextRequest, NextResponse } from "next/server";

const TOKEN_COOKIE = "honeychain_access_token";

/** Routes that require an authenticated session */
const PROTECTED_PREFIXES = [
  "/dashboard",
  "/hives",
  "/telemetry",
  "/risk",
  "/harvests",
  "/collection-lots",
  "/batches",
  "/lab-evidence",
  "/blockchain",
  "/analytics",
  "/users",
];

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + "/")
  );
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // Read token from cookie (set by login page via document.cookie)
  const token = request.cookies.get(TOKEN_COOKIE)?.value ?? null;
  const hasToken = Boolean(token);

  // Root route: redirect based on auth state
  if (pathname === "/") {
    if (hasToken) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Authenticated user visiting login: redirect to dashboard
  if (pathname === "/login" && hasToken) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Protected route without token: redirect to login
  if (isProtected(pathname) && !hasToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  /*
   * Match all paths except:
   * - _next/static (static files)
   * - _next/image (image optimization)
   * - favicon.ico
   * - public assets
   */
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
