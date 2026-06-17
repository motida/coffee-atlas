import { NextResponse, type NextRequest } from "next/server";

// Session cookie name — must match the backend's COOKIE_NAME ("ca_session").
const SESSION_COOKIE = "ca_session";

/**
 * Lightweight presence check for protected routes. This only confirms the
 * session cookie *exists* — it canNOT verify the JWT, because JWT_SECRET lives
 * only on the backend. A forged/expired cookie still passes here; the
 * authoritative check is the backend (every /account API call 401s without a
 * valid token) plus the account page re-fetching GET /auth/me. This redirect is
 * purely a UX shortcut to avoid flashing a protected page at signed-out users.
 */
export function middleware(request: NextRequest) {
  if (!request.cookies.has(SESSION_COOKIE)) {
    const loginUrl = new URL("/auth/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/account/:path*"],
};
