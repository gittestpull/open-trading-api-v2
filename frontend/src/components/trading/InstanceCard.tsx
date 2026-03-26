"use client";

import { cn, formatNumber } from "@/lib/utils";
import { Badge, EnvBadge } from "@/components/common/Badge";
import { StatCard } from "@/components/common/StatCard";
import { HoldingsTable } from "./HoldingsTable";
import { GridControls } from "./GridControls";
import type { GridLadderInstance } from "@/lib/types";

interface InstanceCardProps {
  instance: GridLadderInstance;
  isActive: boolean;
  onSelect: (ticker: string) => void;
  onStop: (ticker: string) => void;
  onRetry: (ticker: string) => void;
  onSkip: (ticker: string) => void;
  onEdit: (instance: GridLadderInstance) => void;
  onDelete: (ticker: string, envDv: string) => void;
}

function getStatusBadge(s: GridLadderInstance) {
  if (s.paused) return "paused" as const;
  if (s.running) return "running" as const;
  if (s.saved && !s.running) return "saved" as const;
  if (s.last_error) return "error" as const;
  if (s.executed_orders > 0) return "holding" as const;
  return "idle" as const;
}

export function InstanceCard({
  instance: s,
  isActive,
  onSelect,
  onStop,
  onRetry,
  onSkip,
  onEdit,
  onDelete,
}: InstanceCardProps) {
  const isLive = s.env_dv === "real";

  return (
    <div
      data-instance-ticker={s.ticker}
      onClick={() => onSelect(s.ticker)}
      className={cn(
        "bg-dark-800 border rounded-xl p-4 transition cursor-pointer",
        isActive
          ? "border-accent-blue"
          : isLive
          ? "border-red-900/30"
          : "border-green-900/30"
      )}
    >
      {/* Header */}
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          <EnvBadge env={s.env_dv} />
          <span className="font-bold text-white">{s.ticker}</span>
          <span className="text-xs text-gray-400">{s.name || ""}</span>
          <Badge variant={getStatusBadge(s)} />
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onStop(s.ticker);
          }}
          className="text-xs text-gray-500 hover:text-accent-red transition"
        >
          ⏹
        </button>
      </div>

      {/* Config line */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-gray-500 mb-2 px-1">
        <span>💰 총 {formatNumber(s.total_budget || 0)}원</span>
        <span>📦 1회 {formatNumber(s.order_amount || 0)}원</span>
        <span>📊 레벨 {(s.entry_tick_levels || []).join(",")}호가</span>
        <span>🎯 트리거 -{s.trigger_level || 6}호가</span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit(s);
          }}
          className="text-accent-blue hover:underline"
        >
          ✏️ 수정
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        <StatCard label="Round" value={s.round || 0} colorClass="text-accent-blue" />
        <StatCard
          label="Base"
          value={s.base_price ? formatNumber(s.base_price) : "-"}
        />
        <StatCard
          label="Invested"
          value={formatNumber(s.total_invested || 0)}
          colorClass="text-accent-green"
        />
        <StatCard
          label="Remain"
          value={formatNumber(s.budget_remaining || 0)}
          colorClass="text-accent-yellow"
        />
        <StatCard label="Fills" value={s.executed_orders || 0} />
        <StatCard
          label="Pending"
          value={s.pending_orders || 0}
          colorClass="text-accent-red"
        />
      </div>

      {/* Error / Pause controls */}
      {(s.paused || s.last_error) && (
        <GridControls
          instance={s}
          onRetry={() => onRetry(s.ticker)}
          onSkip={() => onSkip(s.ticker)}
          onStop={() => onStop(s.ticker)}
        />
      )}

      {/* Holdings table */}
      {s.holdings?.length > 0 && <HoldingsTable holdings={s.holdings} />}

      {/* Saved state footer */}
      {s.saved && !s.running && (
        <div className="mt-2 flex justify-between items-center text-[10px] text-gray-600">
          <span>저장: {s.updated_at || ""}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(s.ticker, s.env_dv);
            }}
            className="px-2 py-0.5 bg-dark-700 hover:bg-red-900/30 text-gray-500 hover:text-accent-red rounded transition"
          >
            🗑 삭제
          </button>
        </div>
      )}
    </div>
  );
}
