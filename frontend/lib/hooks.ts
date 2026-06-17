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
    fetchEntity(id)
      .then(setEntity)
      .catch((e) => setError(String(e)));
    loadRelated?.(id);
    // Re-run only when the id changes; the fetch callbacks are recreated each
    // render and intentionally excluded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return { entity, error };
}
