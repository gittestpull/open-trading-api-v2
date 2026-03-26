"use client";

import type { GridLadderInstance } from "@/lib/types";

interface GridControlsProps {
  instance: GridLadderInstance;
  onRetry: () => void;
  onSkip: () => void;
  onStop: () => void;
}

export function GridControls({
  instance,
  onRetry,
  onSkip,
  onStop,
}: GridControlsProps) {
  return (
    <div className="mt-3 p-2 bg-red-900/20 border border-red-800/30 rounded-lg">
      <div className="text-xs text-accent-red mb-2">
        ⚠ {instance.last_error || instance.pause_reason}
      </div>
      {instance.paused && (
        <div className="flex gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRetry();
            }}
            className="px-3 py-1 bg-accent-blue hover:opacity-80 text-white text-xs font-bold rounded transition"
          >
            🔄 Retry
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSkip();
            }}
            className="px-3 py-1 bg-accent-yellow hover:opacity-80 text-black text-xs font-bold rounded transition"
          >
            ⏭ Skip
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStop();
            }}
            className="px-3 py-1 bg-accent-red hover:opacity-80 text-white text-xs font-bold rounded transition"
          >
            ⏹ Stop
          </button>
        </div>
      )}
    </div>
  );
}
