"use client";

import { cn } from "@/lib/utils";

type BadgeVariant = "running" | "paused" | "saved" | "error" | "holding" | "idle";

const variantStyles: Record<BadgeVariant, string> = {
  running: "bg-green-900/30 text-accent-green border-green-800/40",
  paused: "bg-red-900/30 text-accent-red border-red-800/40 animate-pulse",
  saved: "bg-purple-900/30 text-accent-purple border-purple-800/40",
  error: "bg-red-900/30 text-accent-red border-red-800/40",
  holding: "bg-yellow-900/30 text-accent-yellow border-yellow-800/40",
  idle: "bg-dark-700 text-gray-500 border-dark-600",
};

const variantLabels: Record<BadgeVariant, string> = {
  running: "● Running",
  paused: "⏸ Paused",
  saved: "💾 Saved",
  error: "⚠ Error",
  holding: "● Holding",
  idle: "● Idle",
};

interface BadgeProps {
  variant: BadgeVariant;
  label?: string;
  className?: string;
}

export function Badge({ variant, label, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border",
        variantStyles[variant],
        className
      )}
    >
      {label || variantLabels[variant]}
    </span>
  );
}

export function EnvBadge({ env }: { env: "real" | "demo" }) {
  if (env === "real") {
    return (
      <span className="text-[10px] px-1.5 py-0.5 bg-red-900/30 text-accent-red rounded border border-red-800/40">
        LIVE
      </span>
    );
  }
  return (
    <span className="text-[10px] px-1.5 py-0.5 bg-green-900/30 text-accent-green rounded border border-green-800/40">
      DEMO
    </span>
  );
}
