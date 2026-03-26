"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  GridLadderInstance,
  GridLadderStatus,
  GridLadderStartParams,
  GridLadderConfigUpdate,
} from "@/lib/types";

export function useGridLadder() {
  const [instances, setInstances] = useState<GridLadderInstance[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api<GridLadderStatus>("GET", "/api/grid-ladder/status");
      setInstances(data.grid_ladders || []);
    } catch {
      setInstances([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const start = useCallback(async (params: GridLadderStartParams) => {
    await api("POST", "/api/grid-ladder/start", params);
    setTimeout(refresh, 1000);
  }, [refresh]);

  const stop = useCallback(async (ticker: string) => {
    await api("POST", `/api/grid-ladder/stop/${ticker}`);
    setTimeout(refresh, 500);
  }, [refresh]);

  const retry = useCallback(async (ticker: string) => {
    await api("POST", `/api/grid-ladder/retry/${ticker}`);
    setTimeout(refresh, 500);
  }, [refresh]);

  const skip = useCallback(async (ticker: string) => {
    await api("POST", `/api/grid-ladder/skip/${ticker}`);
    setTimeout(refresh, 500);
  }, [refresh]);

  const updateConfig = useCallback(
    async (ticker: string, envDv: string, config: GridLadderConfigUpdate) => {
      await api("PUT", `/api/grid-ladder/config/${ticker}?env_dv=${envDv}`, config);
      refresh();
    },
    [refresh]
  );

  const deleteSaved = useCallback(
    async (ticker: string, envDv: string) => {
      await api("DELETE", `/api/grid-ladder/saved/${ticker}?env_dv=${envDv}`);
      refresh();
    },
    [refresh]
  );

  // Auto-refresh every 5s
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  return {
    instances,
    loading,
    refresh,
    start,
    stop,
    retry,
    skip,
    updateConfig,
    deleteSaved,
  };
}
