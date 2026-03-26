"use client";

import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  colorClass?: string;
}

export function StatCard({ label, value, colorClass }: StatCardProps) {
  return (
    <div className="bg-dark-900 rounded p-2 text-center">
      <div className="text-[9px] text-gray-500">{label}</div>
      <div className={cn("text-sm font-bold", colorClass || "text-white")}>
        {value}
      </div>
    </div>
  );
}
