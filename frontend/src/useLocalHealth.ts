import { useEffect, useState } from "react";
import { api } from "./api";
import type { Health } from "./types";

export function useLocalHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [checking, setChecking] = useState(true);
  const [hasChecked, setHasChecked] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    async function refresh() {
      if (inFlight) return;
      inFlight = true;
      setChecking(true);
      try {
        const next = await api.health(controller.signal);
        if (!controller.signal.aborted) setHealth(next);
      } catch {
        if (!controller.signal.aborted) setHealth(null);
      } finally {
        inFlight = false;
        if (!controller.signal.aborted) {
          setHasChecked(true);
          setChecking(false);
        }
      }
    }
    void refresh();
    const interval = setInterval(() => void refresh(), 10000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [revision]);

  return {
    health,
    checking,
    hasChecked,
    refresh: () => setRevision((value) => value + 1),
  };
}
