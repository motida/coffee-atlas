"use client";

import { useEffect, useState } from "react";

/** Load a detail entity by id (plus any related data), mirroring the
 *  fetch-on-mount / refetch-on-id-change pattern shared by every
 *  /explore/<type>/[id] page. `loadRelated` runs alongside the main fetch and
 *  is where a page kicks off its related list/edge fetches. */
export function useEntityDetail<T>(
  id: string,
  fetchEntity: (id: string) => Promise<T>,
  loadRelated?: (id: string) => void,
): { entity: T | null; error: string | null } {
  const [entity, setEntity] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Reset on id change so a same-type navigation (variety -> variety) shows
    // the loading state instead of the previous entity, and a past failure
    // doesn't stick the page on its error view. The cancelled flag drops
    // out-of-order responses from an earlier id.
    let cancelled = false;
    setEntity(null);
    setError(null);
    fetchEntity(id)
      .then((e) => {
        if (!cancelled) setEntity(e);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    loadRelated?.(id);
    return () => {
      cancelled = true;
    };
    // Re-run only when the id changes; the fetch callbacks are recreated each
    // render and intentionally excluded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return { entity, error };
}
