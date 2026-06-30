"use client";

import type { RoastProfile } from "@/lib/types";

const LEVEL_ORDER = ["light", "medium-light", "medium", "medium-dark", "dark"];
const SPEEDS = [0.5, 1, 2, 4] as const;

/** Shared pill styling, matching the roasters page chips. */
function chipClass(active: boolean): string {
  return active
    ? "rounded-full bg-coffee-700 px-3 py-1 text-sm font-medium text-white"
    : "rounded-full border border-coffee-200 bg-white px-3 py-1 text-sm text-gray-600 hover:border-coffee-400";
}

export function RoastControls({
  profiles,
  selectedId,
  onSelect,
  isPlaying,
  onTogglePlay,
  onReset,
  progress,
  onScrub,
  speed,
  onSpeed,
}: {
  profiles: RoastProfile[];
  selectedId: string;
  onSelect: (id: string) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onReset: () => void;
  progress: number;
  onScrub: (p: number) => void;
  speed: number;
  onSpeed: (s: number) => void;
}) {
  const groups = LEVEL_ORDER.map((level) => ({
    level,
    items: profiles.filter((p) => p.roast_level === level),
  })).filter((g) => g.items.length > 0);
  const ungrouped = profiles.filter(
    (p) => !p.roast_level || !LEVEL_ORDER.includes(p.roast_level),
  );

  return (
    <div className="space-y-4">
      {/* Profile picker, grouped by roast level (light -> dark) */}
      <div className="space-y-2">
        {groups.map((g) => (
          <div key={g.level} className="flex flex-wrap items-center gap-2">
            <span className="w-24 shrink-0 text-xs font-semibold uppercase tracking-wide text-coffee-600">
              {g.level.replace("-", " ")}
            </span>
            {g.items.map((p) => (
              <button
                key={p.id}
                type="button"
                className={chipClass(p.id === selectedId)}
                onClick={() => onSelect(p.id)}
              >
                {p.name}
              </button>
            ))}
          </div>
        ))}
        {ungrouped.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-24 shrink-0 text-xs font-semibold uppercase tracking-wide text-coffee-600">
              Other
            </span>
            {ungrouped.map((p) => (
              <button
                key={p.id}
                type="button"
                className={chipClass(p.id === selectedId)}
                onClick={() => onSelect(p.id)}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Transport: play/pause, reset, scrub, speed */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onTogglePlay}
          className="rounded-md bg-coffee-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-coffee-800"
        >
          {isPlaying ? "Pause" : progress >= 1 ? "Replay" : "Play"}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-coffee-200 bg-white px-3 py-1.5 text-sm text-gray-600 hover:border-coffee-400"
        >
          Reset
        </button>

        <input
          type="range"
          min={0}
          max={1}
          step={0.001}
          value={progress}
          onChange={(e) => onScrub(Number(e.target.value))}
          aria-label="Scrub roast timeline"
          className="h-1.5 min-w-[140px] flex-1 cursor-pointer accent-coffee-700"
        />

        <div className="flex items-center gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              className={chipClass(s === speed)}
              onClick={() => onSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
