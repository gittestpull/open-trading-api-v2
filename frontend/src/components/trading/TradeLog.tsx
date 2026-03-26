"use client";

import { cn } from "@/lib/utils";
import type { TradeEvent } from "@/lib/types";

interface TradeLogProps {
  events: TradeEvent[];
  onClear: () => void;
}

function getEventDisplay(event: TradeEvent) {
  switch (event.type) {
    case "fill":
      return {
        icon: "✅",
        color: "text-accent-green",
        text: `체결 ${event.price?.toLocaleString()}₩ × ${event.qty}주 [${event.order_no}]`,
        flash: "flash-fill",
      };
    case "order":
      return {
        icon: "📝",
        color: "text-accent-blue",
        text: `주문접수 ${event.price?.toLocaleString()}₩ × ${event.qty}주 [${event.order_no}]`,
        flash: "",
      };
    case "cancel":
      return {
        icon: "❌",
        color: "text-accent-yellow",
        text: `취소 ${event.price?.toLocaleString()}₩ × ${event.qty}주 [${event.order_no}]`,
        flash: "flash-cancel",
      };
    case "error":
      return {
        icon: "⚠",
        color: "text-accent-red",
        text: `에러 ${event.reason || "unknown"} [${event.order_no}]`,
        flash: "",
      };
    default:
      return {
        icon: "📌",
        color: "text-gray-400",
        text: JSON.stringify(event),
        flash: "",
      };
  }
}

export function TradeLog({ events, onClear }: TradeLogProps) {
  return (
    <div className="bg-dark-800 border border-dark-600 rounded-xl p-4">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          📜 Trade Log (Real-time)
        </h2>
        <button
          onClick={onClear}
          className="text-xs text-gray-500 hover:text-white transition"
        >
          Clear
        </button>
      </div>
      <div className="space-y-1 max-h-72 overflow-y-auto text-xs font-mono">
        {events.length === 0 ? (
          <div className="text-gray-600 text-center py-4">
            Waiting for events...
          </div>
        ) : (
          events.map((event, i) => {
            const { icon, color, text, flash } = getEventDisplay(event);
            return (
              <div key={i} className={cn("flex gap-2", color, flash)}>
                <span className="text-gray-600 shrink-0">
                  {event.time || ""}
                </span>
                <span>{icon}</span>
                <span>{text}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
