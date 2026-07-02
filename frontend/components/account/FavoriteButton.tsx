"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

/** Save/unsave control for an entity detail page. Gates on auth: signed-out
 *  users are sent to login. The favorite's id (when saved) is tracked so the
 *  same button can remove it. */
export function FavoriteButton({
  entityType,
  entityId,
}: {
  entityType: string;
  entityId: string;
}) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) {
      setFavoriteId(null);
      return;
    }
    // Cancellation drops stale responses on rapid same-type navigation —
    // otherwise the previous entity's lookup can mark this page "Saved" and
    // a click would delete the wrong favorite row.
    let cancelled = false;
    setFavoriteId(null);
    api
      .getFavorites(entityType)
      .then((favs) => {
        if (!cancelled)
          setFavoriteId(favs.find((f) => f.entity_id === entityId)?.id ?? null);
      })
      .catch(() => {
        if (!cancelled) setFavoriteId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user, entityType, entityId]);

  async function toggle() {
    if (loading) return;
    if (!user) {
      router.push("/auth/login");
      return;
    }
    setBusy(true);
    try {
      if (favoriteId) {
        await api.removeFavorite(favoriteId);
        setFavoriteId(null);
      } else {
        const fav = await api.addFavorite(entityType, entityId);
        setFavoriteId(fav.id);
      }
    } catch (err) {
      // A 401 means the session cookie expired while the tab was open —
      // re-auth instead of a click that silently does nothing.
      if (err instanceof api.APIError && err.status === 401) {
        router.push("/auth/login");
        return;
      }
      console.error("Favorite toggle failed:", err);
    } finally {
      setBusy(false);
    }
  }

  const saved = favoriteId !== null;
  return (
    <button
      type="button"
      onClick={() => void toggle()}
      disabled={busy}
      className={
        saved
          ? "rounded-md border border-coffee-700 bg-coffee-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          : "rounded-md border border-coffee-300 px-3 py-1.5 text-sm font-medium text-coffee-700 hover:bg-coffee-50 disabled:opacity-50"
      }
    >
      {saved ? "★ Saved" : "☆ Save"}
    </button>
  );
}
