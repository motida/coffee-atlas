"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getRoastProfiles } from "@/lib/api";
import type { RoastProfile } from "@/lib/types";
import { beanColor, beanSheen, makeRoastCurve } from "@/lib/roast-curve";
import { RoastBean } from "./RoastBean";
import { RoastChart } from "./RoastChart";
import { RoastControls } from "./RoastControls";

/** Wall-clock duration of a full roast at 1× — real roasts (8-14 min) are
 *  compressed so the animation reads in a few seconds. */
const PLAYBACK_MS = 24000;

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function RoastSimulator() {
  const [profiles, setProfiles] = useState<RoastProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // 0 -> 1, the source of truth
  const [speed, setSpeed] = useState(1);

  // Read inside the rAF loop to avoid stale closures / restarting on speed change.
  const progressRef = useRef(0);
  const speedRef = useRef(1);

  useEffect(() => {
    getRoastProfiles()
      .then((all) => {
        const usable = all.filter((p) => makeRoastCurve(p) !== null);
        setProfiles(usable);
        if (usable.length > 0) setSelectedId(usable[0].id);
      })
      .catch((e) => setError(e?.message ?? String(e)));
  }, []);

  const selected = useMemo(
    () => profiles?.find((p) => p.id === selectedId) ?? null,
    [profiles, selectedId],
  );
  const curve = useMemo(() => (selected ? makeRoastCurve(selected) : null), [selected]);

  // Play loop — timestamp stepping like CoffeeMap's dash animation; depends only
  // on isPlaying, reads speed from a ref, and self-stops at the end. The cleanup
  // cancels the frame on pause, unmount, and Strict-Mode double-mount.
  useEffect(() => {
    if (!isPlaying) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      let p = progressRef.current + dt / (PLAYBACK_MS / speedRef.current);
      if (p >= 1) {
        p = 1;
        setIsPlaying(false);
      }
      progressRef.current = p;
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isPlaying]);

  const setProgressBoth = (p: number) => {
    progressRef.current = p;
    setProgress(p);
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setIsPlaying(false);
    setProgressBoth(0);
  };
  const handleTogglePlay = () => {
    if (!isPlaying && progressRef.current >= 1) setProgressBoth(0); // replay from 0
    setIsPlaying((v) => !v);
  };
  const handleReset = () => {
    setIsPlaying(false);
    setProgressBoth(0);
  };
  const handleScrub = (p: number) => {
    setIsPlaying(false);
    setProgressBoth(p);
  };
  const handleSpeed = (s: number) => {
    speedRef.current = s;
    setSpeed(s);
  };

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load roast profiles: {error}
      </div>
    );
  }
  if (!profiles || !selected || !curve) {
    return (
      <div className="rounded-lg border border-coffee-200 bg-white p-6 text-coffee-600">
        Loading roast profiles…
      </div>
    );
  }

  const currentT = progress * curve.durationSec;
  const currentTemp = curve.tempAt(currentT);
  const colorTemp = curve.colorTempAt(currentT);
  const currentPhase =
    curve.phases.find((ph) => currentT >= ph.t0 && currentT <= ph.t1) ??
    curve.phases[curve.phases.length - 1];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Bean + live readouts */}
        <div className="flex flex-col items-center gap-4 lg:w-1/3">
          <RoastBean fill={beanColor(colorTemp)} sheen={beanSheen(colorTemp)} />
          <div className="grid w-full grid-cols-3 gap-2 text-center">
            <Readout label="Time" value={fmtTime(currentT)} />
            <Readout label="Bean temp" value={`${Math.round(currentTemp)}°C`} />
            <Readout label="Phase" value={currentPhase.label} />
          </div>
          <p className="text-center text-xs text-gray-500">
            {selected.roast_level
              ? `${selected.roast_level.replace("-", " ")} roast`
              : "roast"}{" "}
            · drops at {fmtTime(curve.durationSec)}
          </p>
        </div>

        {/* Roast curve */}
        <div className="rounded-lg border border-coffee-200 bg-white p-3 lg:w-2/3">
          <RoastChart curve={curve} currentT={currentT} />
        </div>
      </div>

      <RoastControls
        profiles={profiles}
        selectedId={selected.id}
        onSelect={handleSelect}
        isPlaying={isPlaying}
        onTogglePlay={handleTogglePlay}
        onReset={handleReset}
        progress={progress}
        onScrub={handleScrub}
        speed={speed}
        onSpeed={handleSpeed}
      />

      {selected.description && (
        <p className="rounded-lg border border-coffee-200 bg-white p-4 text-sm leading-relaxed text-gray-700">
          {selected.description}
        </p>
      )}
    </div>
  );
}

function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-coffee-200 bg-white px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-sm font-semibold text-coffee-900">{value}</div>
    </div>
  );
}
