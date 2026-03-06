import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware that protects all routes with a password.
 * Set DASHBOARD_PASSWORD in Vercel environment variables.
 * Users enter it once and get a cookie that lasts 30 days.
 */
export function middleware(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;

  // If no password is configured, allow access (local dev)
  if (!password) return NextResponse.next();

  // Allow the login page and auth API through
  const path = request.nextUrl.pathname;
  if (path === "/login" || path === "/api/auth") {
    return NextResponse.next();
  }

  // Check for auth cookie
  const token = request.cookies.get("wheat_auth")?.value;
  if (token === password) {
    return NextResponse.next();
  }

  // Redirect to login
  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next (Next.js internals)
     * - favicon.ico
     */
    "/((?!_next|favicon.ico).*)",
  ],
};
