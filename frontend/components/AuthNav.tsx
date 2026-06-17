"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

/** Right-hand navbar auth area: Login/Register when signed out, the display
 *  name + Logout when signed in. Kept as a small client island so the rest of
 *  the layout stays a server component. */
export function AuthNav() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <span className="text-sm text-gray-400">…</span>;
  }

  if (!user) {
    return (
      <div className="flex items-center gap-4">
        <Link
          href="/auth/login"
          className="text-sm font-medium text-gray-600 hover:text-coffee-700"
        >
          Login
        </Link>
        <Link
          href="/auth/register"
          className="rounded-md bg-coffee-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-coffee-800"
        >
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <Link
        href="/account"
        className="text-sm font-medium text-coffee-800 hover:text-coffee-900"
      >
        {user.display_name || user.email}
      </Link>
      <button
        type="button"
        onClick={() => void logout()}
        className="text-sm font-medium text-gray-600 hover:text-coffee-700"
      >
        Logout
      </button>
    </div>
  );
}
