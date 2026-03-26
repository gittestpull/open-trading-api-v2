"use client";

import { useMemo } from "react";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { OrderbookData, GridOrderInfo } from "@/lib/types";

interface OrderbookProps {
  data: OrderbookData | null;
  gridOrderMap: Record<number, GridOrderInfo>;
  ticker: string;
  stockName?: string;
}

export function Orderbook({ data, gridOrderMap, ticker, stockName }: OrderbookProps) {
  const gridPrices = useMemo(
    () => new Set(Object.keys(gridOrderMap).map(Number)),
    [gridOrderMap]
  );

  const maxQty = useMemo(() => {
    if (!data) return 1;
    const allQty = [
      ...data.asks.map((a) => a.qty),
      ...data.bids.map((b) => b.qty),
    ];
    return Math.max(...allQty, 1);
  }, [data]);

  // Below-range grid orders
  const belowOrders = useMemo(() => {
    if (!data || data.bids.length === 0) return [];
    const lowestBid = data.bids[data.bids.length - 1].price;
    return Object.entries(gridOrderMap)
      .filter(([p]) => Number(p) < lowestBid)
      .sort((a, b) => Number(b[0]) - Number(a[0]));
  }, [data, gridOrderMap]);

  const priceChange = data?.price_change ?? 0;
  const curPrice = data?.current_price ?? 0;

  return (
    <div className="bg-dark-800 border border-dark-600 rounded-xl p-4">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          📋 호가창
          {ticker && (
            <>
              <span className="text-accent-blue text-sm font-normal ml-1">
                {ticker}
              </span>
              {stockName && (
                <span className="text-gray-400 text-xs">{stockName}</span>
              )}
            </>
          )}
        </h2>
        <span className="text-xs text-gray-500">{data?.time || "--:--:--"}</span>
      </div>

      {/* Ask side (매도) — reversed: highest at top */}
      <div className="text-[10px] text-gray-500 flex justify-between px-1 mb-1">
        <span>잔량</span>
        <span>매도호가</span>
      </div>
      <div className="space-y-px mb-2">
        {(data?.asks ? [...data.asks].reverse() : []).slice(0, 10).map((a, i) => {
          const pct = Math.min(100, (a.qty / maxQty) * 100);
          const isGrid = gridPrices.has(a.price);
          return (
            <div
              key={`ask-${i}`}
              className={cn(
                "flex items-center justify-between px-2 py-1 rounded text-xs ob-bar-ask",
                isGrid && "ob-grid-marker"
              )}
              style={{
                backgroundSize: `${pct}% 100%`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "left",
              }}
            >
              <span className="text-gray-400 w-20 text-right">
                {formatNumber(a.qty)}
              </span>
              <span className="text-accent-red font-mono font-bold">
                {formatNumber(a.price)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Current Price + Spread */}
      <div className="bg-dark-700 rounded px-3 py-2 mb-2 text-center">
        <div className="flex justify-center items-baseline gap-2">
          <span
            className={cn(
              "text-xl font-bold",
              priceChange > 0
                ? "text-accent-red"
                : priceChange < 0
                ? "text-accent-blue"
                : "text-white"
            )}
          >
            {curPrice ? `${formatNumber(curPrice)}원` : "-"}
          </span>
          <span
            className={cn(
              "text-xs font-bold",
              priceChange > 0
                ? "text-accent-red"
                : priceChange < 0
                ? "text-accent-blue"
                : "text-gray-500"
            )}
          >
            {priceChange > 0
              ? `▲${formatNumber(priceChange)}`
              : priceChange < 0
              ? `▼${formatNumber(Math.abs(priceChange))}`
              : "0"}
          </span>
        </div>
        <div className="flex justify-center items-center gap-3 mt-0.5">
          <span className="text-[10px] text-gray-500">
            스프레드:{" "}
            {data?.asks?.length && data?.bids?.length
              ? `${formatNumber(data.asks[0].price - data.bids[0].price)}원`
              : "-"}
          </span>
          <span className="text-[10px] text-gray-500">
            거래량: {formatNumber(data?.acml_vol ?? 0)}
          </span>
        </div>
      </div>

      {/* Bid side (매수) */}
      <div className="text-[10px] text-gray-500 flex justify-between px-1 mb-1">
        <span>매수호가</span>
        <span>잔량</span>
      </div>
      <div className="space-y-px mb-3">
        {(data?.bids || []).slice(0, 10).map((b, i) => {
          const pct = Math.min(100, (b.qty / maxQty) * 100);
          const isGrid = gridPrices.has(b.price);
          const myOrder = gridOrderMap[b.price];
          return (
            <div
              key={`bid-${i}`}
              className={cn(
                "flex items-center justify-between px-2 py-1 rounded text-xs ob-bar-bid",
                isGrid && "ob-grid-marker"
              )}
              style={{
                backgroundSize: `${pct}% 100%`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right",
              }}
            >
              <span className="flex items-center gap-1">
                <span className="text-accent-blue font-mono font-bold">
                  {formatNumber(b.price)}
                </span>
                {myOrder && (
                  <span className="text-accent-purple font-bold text-[10px] px-1 py-0.5 bg-purple-900/40 border border-purple-700/50 rounded ml-1">
                    MY {myOrder.qty}주 L{myOrder.level}
                  </span>
                )}
              </span>
              <span className="text-gray-400 w-20 text-left">
                {formatNumber(b.qty)}
              </span>
            </div>
          );
        })}

        {/* Below-range grid orders */}
        {belowOrders.length > 0 && (
          <>
            <div className="text-center text-[9px] text-gray-600 py-0.5">
              ── 호가 범위 밖 ──
            </div>
            {belowOrders.map(([price, o]) => (
              <div
                key={`below-${price}`}
                className="flex items-center justify-between px-2 py-1 rounded text-xs ob-grid-marker"
              >
                <span className="flex items-center gap-1">
                  <span className="text-accent-purple font-mono font-bold">
                    {formatNumber(Number(price))}
                  </span>
                  <span className="text-accent-purple font-bold text-[10px] px-1 py-0.5 bg-purple-900/40 border border-purple-700/50 rounded">
                    MY {o.qty}주 L{o.level}
                  </span>
                </span>
                <span className="text-gray-500 text-[10px]">대기중</span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Totals */}
      <div className="flex justify-between text-xs px-1 pt-2 border-t border-dark-600">
        <div>
          매도잔량{" "}
          <span className="text-accent-red font-bold">
            {formatNumber(data?.total_ask_qty ?? 0)}
          </span>
        </div>
        <div>
          매수잔량{" "}
          <span className="text-accent-blue font-bold">
            {formatNumber(data?.total_bid_qty ?? 0)}
          </span>
        </div>
      </div>
    </div>
  );
}
