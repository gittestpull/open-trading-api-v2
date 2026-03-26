"use client";

import type { WsState } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";

interface WsIndicatorProps {
  label: string;
  state: WsState;
}

const stateStyles: Record<WsState, string> = {
  connected: "bg-accent-green",
  connecting: "bg-accent-yellow ws-pulse",
  disconnected: "bg-accent-red",
};

const stateLabels: Record<WsState, string> = {
  connected: "✓",
  connecting: "...",
  disconnected: "✗",
};

export function WsIndicator({ label, state }: WsIndicatorProps) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-gray-500">
      <span
        className={cn("w-2 h-2 rounded-full inline-block", stateStyles[state])}
      />
      <span>
        {label}: {stateLabels[state]}
      </span>
    </div>
  );
}
