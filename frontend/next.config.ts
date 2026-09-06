import type { NextConfig } from "next";

const BACKEND_API_URL =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // Same-origin /api prefix proxies to backend root
      {
        source: "/api/:path*",
        destination: `${BACKEND_API_URL}/:path*`,
      },
      // Direct /auth rewrites (e.g. /auth/login)
      {
        source: "/auth/:path*",
        destination: `${BACKEND_API_URL}/auth/:path*`,
      },
      // OpenAPI specification rewrite
      {
        source: "/openapi.json",
        destination: `${BACKEND_API_URL}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
