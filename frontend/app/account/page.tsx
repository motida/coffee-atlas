"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CardGrid, EntityCard, Section } from "@/components/explore/EntityPage";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { entityHref } from "@/lib/entity-config";
import type { CuppingNote, Favorite } from "@/lib/types";

export default function AccountPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [notes, setNotes] = useState<CuppingNote[]>([]);

  // Authoritative gate: GET /auth/me decided `user`. Redirect once we know.
  useEffect(() => {
    if (!loading && !user) router.replace("/auth/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.getFavorites().then(setFavorites).catch(() => setFavorites([]));
    api.getNotes().then(setNotes).catch(() => setNotes([]));
  }, [user]);

  if (loading || !user) {
    return <p className="mx-auto max-w-5xl px-4 py-8 text-sm text-gray-500">Loading…</p>;
  }

  async function removeFavorite(id: string) {
    await api.removeFavorite(id);
    setFavorites((cur) => cur.filter((f) => f.id !== id));
  }

  async function removeNote(id: string) {
    await api.deleteNote(id);
    setNotes((cur) => cur.filter((n) => n.id !== id));
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-8 border-b border-coffee-200 pb-4">
        <div className="text-xs uppercase tracking-wide text-coffee-600">Account</div>
        <h1 className="mt-1 text-3xl font-bold text-coffee-900">
          {user.display_name || user.email}
        </h1>
      </header>

      <div className="space-y-8">
        <Section title="Saved" count={favorites.length} empty="Nothing saved yet.">
          <CardGrid>
            {favorites.map((fav) => {
              const href = entityHref(fav.entity_type, fav.entity_id);
              const title = fav.entity_type;
              return (
                <div key={fav.id} className="relative">
                  {href ? (
                    <EntityCard href={href} title={title} subtitle={fav.entity_id} />
                  ) : (
                    <div className="rounded-lg border border-coffee-200 bg-white px-4 py-3">
                      <div className="text-sm font-medium text-coffee-900">{title}</div>
                      <div className="mt-0.5 text-xs text-gray-500">{fav.entity_id}</div>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => void removeFavorite(fav.id)}
                    className="absolute right-2 top-2 z-10 text-xs text-gray-400 hover:text-red-600"
                    aria-label="Remove"
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </CardGrid>
        </Section>

        <Section title="Cupping notes" count={notes.length} empty="No tasting notes yet.">
          <div className="space-y-3">
            {notes.map((note) => {
              const href = entityHref(note.entity_type, note.entity_id);
              return (
                <div
                  key={note.id}
                  className="rounded-lg border border-coffee-200 bg-white px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium text-coffee-900">
                      {href ? (
                        <a href={href} className="hover:underline">
                          {note.entity_type}
                        </a>
                      ) : (
                        note.entity_type
                      )}
                      {note.score != null && (
                        <span className="ml-2 text-xs font-normal text-coffee-600">
                          {note.score}/100
                        </span>
                      )}
                      {note.brew_method && (
                        <span className="ml-2 text-xs font-normal text-gray-500">
                          {note.brew_method}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeNote(note.id)}
                      className="text-xs text-gray-400 hover:text-red-600"
                      aria-label="Delete note"
                    >
                      ✕
                    </button>
                  </div>
                  <p className="mt-1 whitespace-pre-line text-sm text-gray-700">{note.notes}</p>
                </div>
              );
            })}
          </div>
        </Section>
      </div>
    </div>
  );
}
