"use client";

import { useRef, useEffect } from "react";
import { useStockSearch } from "@/hooks/useStockSearch";
import type { StockSearchResult } from "@/lib/types";

interface StockSearchProps {
  value: string;
  onChange: (value: string) => void;
  onSelect: (stock: StockSearchResult) => void;
  stockName?: string;
}

export function StockSearch({
  value,
  onChange,
  onSelect,
  stockName,
}: StockSearchProps) {
  const { results, isOpen, search, close } = useStockSearch();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        close();
      }
    }
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [close]);

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-xs text-gray-500 mb-1">Ticker</label>
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            search(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (results.length > 0) {
                onSelect(results[0]);
                close();
              }
            }
            if (e.key === "Escape") close();
          }}
          placeholder="Search stock..."
          className="w-full pl-10 pr-4 py-2.5 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white placeholder-gray-500 text-sm"
          autoComplete="off"
        />
        <span className="absolute left-3 top-2.5 text-gray-500">🔍</span>
        {isOpen && results.length > 0 && (
          <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-dark-800 border border-dark-600 rounded-lg shadow-xl max-h-60 overflow-y-auto">
            {results.map((s) => (
              <div
                key={`${s.ticker}-${s.market}`}
                onClick={() => {
                  onSelect(s);
                  close();
                }}
                className="flex justify-between items-center p-2.5 hover:bg-dark-700 cursor-pointer transition text-sm"
              >
                <div>
                  <span className="font-bold text-white">{s.name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    {s.ticker} · {s.market}
                  </span>
                </div>
                <span className="text-accent-blue text-xs">Select</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {stockName && (
        <div className="text-xs text-accent-blue mt-1">{stockName}</div>
      )}
    </div>
  );
}
