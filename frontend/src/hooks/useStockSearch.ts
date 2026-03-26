"use client";

import { useState, useRef, useCallback } from "react";
import type { StockSearchResult } from "@/lib/types";

export function useStockSearch(debounceMs = 300) {
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback(
    (query: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (query.length < 2) {
        setResults([]);
        setIsOpen(false);
        return;
      }
      timerRef.current = setTimeout(async () => {
        try {
          setLoading(true);
          const res = await fetch(
            `/api/stocks/search?q=${encodeURIComponent(query)}&limit=10`
          );
          const data = await res.json();
          setResults(data.stocks || []);
          setIsOpen(true);
        } catch {
          setResults([]);
        } finally {
          setLoading(false);
        }
      }, debounceMs);
    },
    [debounceMs]
  );

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  return { results, isOpen, loading, search, close };
}
