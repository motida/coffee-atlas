"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

/** "Add cupping note" affordance for product/variety detail pages. Collapsed to
 *  a button until opened; gates on auth (signed-out users go to login). */
export function AddCuppingNote({
  entityType,
  entityId,
}: {
  entityType: "product" | "variety";
  entityId: string;
}) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [score, setScore] = useState("");
  const [brewMethod, setBrewMethod] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  function onClick() {
    if (loading) return;
    if (!user) {
      router.push("/auth/login");
      return;
    }
    setOpen((v) => !v);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addNote({
        entity_type: entityType,
        entity_id: entityId,
        notes,
        score: score === "" ? null : Number(score),
        brew_method: brewMethod || null,
      });
      setNotes("");
      setScore("");
      setBrewMethod("");
      setOpen(false);
      setSaved(true);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="rounded-md border border-coffee-300 px-3 py-1.5 text-sm font-medium text-coffee-700 hover:bg-coffee-50"
      >
        {saved ? "✓ Note added" : "+ Cupping note"}
      </button>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="absolute right-0 top-full z-20 mt-2 w-72 space-y-2 rounded-lg border border-coffee-200 bg-white p-3 shadow-lg"
    >
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        required
        placeholder="Tasting notes…"
        rows={3}
        className="w-full rounded-md border border-coffee-200 px-2 py-1 text-sm focus:border-coffee-500 focus:outline-none"
      />
      <div className="flex gap-2">
        <input
          type="number"
          min={0}
          max={100}
          step={0.25}
          value={score}
          onChange={(e) => setScore(e.target.value)}
          placeholder="Score"
          className="w-20 rounded-md border border-coffee-200 px-2 py-1 text-sm focus:border-coffee-500 focus:outline-none"
        />
        <input
          type="text"
          value={brewMethod}
          onChange={(e) => setBrewMethod(e.target.value)}
          placeholder="Brew method"
          className="min-w-0 flex-1 rounded-md border border-coffee-200 px-2 py-1 text-sm focus:border-coffee-500 focus:outline-none"
        />
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-coffee-700 px-3 py-1 text-sm font-medium text-white hover:bg-coffee-800 disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </form>
  );
}
