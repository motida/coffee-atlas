"use client";

import { useEffect, useState } from "react";
import { getApiVersion } from "@/lib/api";

/**
 * Fetches the live backend API version (GET /api/v1/version) on mount. Renders
 * a placeholder while loading and a graceful "unavailable" if the API can't be
 * reached, so the otherwise-static Help page never breaks on a backend hiccup.
 */
export function ApiVersion() {
  const [version, setVersion] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getApiVersion()
      .then((r) => {
        if (active) setVersion(r.version);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <span className="font-medium text-coffee-800">
      {version ? `v${version}` : failed ? "unavailable" : "…"}
    </span>
  );
}
