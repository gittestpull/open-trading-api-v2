"use client";

import { useState, useCallback, useMemo } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { WsIndicator } from "@/components/common/WsIndicator";
import { StockSearch } from "@/components/trading/StockSearch";
import { Orderbook } from "@/components/trading/Orderbook";
import { InstanceCard } from "@/components/trading/InstanceCard";
import { TradeLog } from "@/components/trading/TradeLog";
import { EditConfigModal } from "@/components/trading/EditConfigModal";
import { useGridLadder } from "@/hooks/useGridLadder";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  OrderbookData,
  TradeEvent,
  GridLadderInstance,
  GridOrderInfo,
  StockSearchResult,
} from "@/lib/types";

type ViewMode = "all" | "live" | "demo";

const MAX_LOG = 200;

export default function GridLadderPage() {
  // Grid ladder state
  const {
    instances,
    refresh,
    start,
    stop,
    retry,
    skip,
    updateConfig,
    deleteSaved,
  } = useGridLadder();

  // UI state
  const [activeTicker, setActiveTicker] = useState("");
  const [stockName, setStockName] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [editingInstance, setEditingInstance] = useState<GridLadderInstance | null>(null);

  // Form state
  const [tickerInput, setTickerInput] = useState("");
  const [budget, setBudget] = useState(10000000);
  const [amount, setAmount] = useState(500000);
  const [trigger, setTrigger] = useState(6);
  const [levels, setLevels] = useState("6, 7, 8");
  const [env, setEnv] = useState<"real" | "demo">("demo");

  // Orderbook data
  const [orderbookData, setOrderbookData] = useState<OrderbookData | null>(null);

  // Trade events
  const [tradeEvents, setTradeEvents] = useState<TradeEvent[]>([]);

  // WebSocket: Orderbook
  const { state: obState } = useWebSocket({
    path: activeTicker ? `/ws/grid-ladder/orderbook/${activeTicker}` : "",
    enabled: !!activeTicker,
    onMessage: useCallback(
      (data: unknown) => {
        const d = data as OrderbookData;
        if (d.type === "orderbook" && d.ticker === activeTicker) {
          setOrderbookData(d);
        }
      },
      [activeTicker]
    ),
  });

  // WebSocket: Events
  const { state: evState } = useWebSocket({
    path: activeTicker ? `/ws/grid-ladder/events/${activeTicker}` : "",
    enabled: !!activeTicker,
    onMessage: useCallback((data: unknown) => {
      const event = data as TradeEvent;
      if (event.type && event.type !== "ping") {
        setTradeEvents((prev) => {
          const next = [event, ...prev];
          return next.length > MAX_LOG ? next.slice(0, MAX_LOG) : next;
        });
      }
    }, []),
  });

  // Grid order map for orderbook overlay
  const gridOrderMap = useMemo(() => {
    const map: Record<number, GridOrderInfo> = {};
    instances
      .filter((inst) => inst.ticker === activeTicker)
      .forEach((inst) => {
        (inst.pending_order_details || []).forEach((o) => {
          map[o.price] = {
            qty: o.quantity,
            level: o.tick_level,
            order_no: o.order_no,
          };
        });
      });
    return map;
  }, [instances, activeTicker]);

  // Filtered instances
  const filtered = useMemo(() => {
    if (viewMode === "live") return instances.filter((g) => g.env_dv === "real");
    if (viewMode === "demo") return instances.filter((g) => g.env_dv === "demo");
    return instances;
  }, [instances, viewMode]);

  // Select a stock
  const selectStock = useCallback((stock: StockSearchResult) => {
    setTickerInput(stock.ticker);
    setStockName(stock.name);
    switchTicker(stock.ticker);
  }, []);

  // Switch active ticker
  const switchTicker = useCallback((ticker: string) => {
    const t = ticker.toUpperCase();
    setActiveTicker(t);
    setTickerInput(t);
    setOrderbookData(null);
    // Find name from instances
    // (name is set via selectStock or from instance data)
  }, []);

  // Start grid
  const handleStart = useCallback(async () => {
    const ticker = tickerInput.trim().toUpperCase();
    if (!ticker || ticker.length < 4) {
      alert("종목코드를 입력하세요.");
      return;
    }
    const parsedLevels = levels
      .split(",")
      .map((s) => parseInt(s.trim()))
      .filter((n) => !isNaN(n));
    const envLabel = env === "real" ? "🔴 LIVE" : "🟢 DEMO";
    if (
      !confirm(
        `Start Grid Ladder [${envLabel}] for ${ticker}?\n` +
        `💰 ${budget.toLocaleString()}₩ / 📦 ${amount.toLocaleString()}₩\n` +
        `📊 Levels: ${parsedLevels.join(", ")} / 🎯 Trigger: -${trigger}\n` +
        `${env === "real" ? "⚠ LIVE orders!" : "Demo mode"}`
      )
    )
      return;

    try {
      await start({
        ticker,
        total_budget: budget,
        order_amount: amount,
        entry_tick_levels: parsedLevels,
        trigger_level: trigger,
        env_dv: env,
      });
      switchTicker(ticker);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start");
    }
  }, [tickerInput, budget, amount, levels, trigger, env, start, switchTicker]);

  // Handle stop with confirm
  const handleStop = useCallback(
    async (ticker: string) => {
      if (!confirm(`Stop ${ticker} and cancel all pending orders?`)) return;
      try {
        await stop(ticker);
      } catch (e) {
        alert(e instanceof Error ? e.message : "Failed to stop");
      }
    },
    [stop]
  );

  // Handle edit save
  const handleEditSave = useCallback(
    async (ticker: string, envDv: string, config: Parameters<typeof updateConfig>[2]) => {
      try {
        await updateConfig(ticker, envDv, config);
        setEditingInstance(null);
      } catch (e) {
        alert(e instanceof Error ? e.message : "Failed to save");
      }
    },
    [updateConfig]
  );

  // Handle delete saved
  const handleDelete = useCallback(
    async (ticker: string, envDv: string) => {
      if (!confirm(`${ticker} (${envDv}) 저장된 상태를 삭제합니까?`)) return;
      try {
        await deleteSaved(ticker, envDv);
      } catch (e) {
        alert(e instanceof Error ? e.message : "Failed to delete");
      }
    },
    [deleteSaved]
  );

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-4 overflow-auto">
          <div className="max-w-[1600px] mx-auto">
            {/* Page Header */}
            <div className="flex justify-between items-center mb-6">
              <h1 className="text-xl font-bold text-white flex items-center gap-2">
                📊 Grid Ladder Manager
              </h1>
              <div className="flex items-center gap-4">
                {/* WS Status */}
                <div className="flex items-center gap-3">
                  <WsIndicator label="Orderbook" state={obState} />
                  <WsIndicator label="Events" state={evState} />
                </div>

                {/* Mode Toggle */}
                <div className="flex bg-dark-800 border border-dark-600 rounded-lg overflow-hidden text-xs">
                  {(["all", "live", "demo"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setViewMode(mode)}
                      className={
                        viewMode === mode
                          ? "px-3 py-1.5 bg-accent-blue text-white font-bold"
                          : "px-3 py-1.5 text-gray-400 hover:text-white transition"
                      }
                    >
                      {mode === "all"
                        ? "All"
                        : mode === "live"
                        ? "🔴 Live"
                        : "🟢 Demo"}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
              {/* Col 1: Control Panel */}
              <div className="space-y-4">
                <div className="bg-dark-800 border border-dark-600 rounded-xl p-5">
                  <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                    ⚙️ Settings
                  </h2>

                  <div className="mb-3">
                    <StockSearch
                      value={tickerInput}
                      onChange={setTickerInput}
                      onSelect={selectStock}
                      stockName={stockName}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        Total Budget
                      </label>
                      <input
                        type="number"
                        value={budget}
                        onChange={(e) => setBudget(Number(e.target.value))}
                        step={1000000}
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        Order Amount
                      </label>
                      <input
                        type="number"
                        value={amount}
                        onChange={(e) => setAmount(Number(e.target.value))}
                        step={100000}
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        Trigger Level
                      </label>
                      <input
                        type="number"
                        value={trigger}
                        onChange={(e) => setTrigger(Number(e.target.value))}
                        min={1}
                        max={10}
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        Environment
                      </label>
                      <select
                        value={env}
                        onChange={(e) => setEnv(e.target.value as "real" | "demo")}
                        className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
                      >
                        <option value="real">실전투자</option>
                        <option value="demo">모의투자</option>
                      </select>
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="block text-xs text-gray-500 mb-1">
                      Entry Levels
                    </label>
                    <input
                      type="text"
                      value={levels}
                      onChange={(e) => setLevels(e.target.value)}
                      className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={handleStart}
                      className="py-2.5 bg-accent-green hover:opacity-80 text-black font-bold rounded-lg transition text-sm"
                    >
                      ▶ Start
                    </button>
                    <button
                      onClick={() => {
                        const t = tickerInput.trim().toUpperCase();
                        if (t) handleStop(t);
                      }}
                      className="py-2.5 bg-accent-red hover:opacity-80 text-white font-bold rounded-lg transition text-sm"
                    >
                      ⏹ Stop
                    </button>
                  </div>
                </div>

                {/* Logic Diagram */}
                <div className="bg-dark-800 border border-dark-600 rounded-xl p-5">
                  <h2 className="text-base font-bold text-white mb-3">📐 Logic</h2>
                  <pre className="text-xs text-gray-500 leading-relaxed font-mono bg-dark-900 rounded-lg p-3 overflow-x-auto">
{`Base 10,000₩ (initial buy)
  │
  ├── `}<span className="text-accent-green font-bold">{`-6tick 9,940₩ ← trigger`}</span>{`
  ├── -7tick 9,930₩ (standby)
  └── -8tick 9,920₩ (standby)
  │
  `}<span className="text-accent-green">{`✅ -6tick filled!`}</span>{`
  `}<span className="text-accent-red">{`❌ -7/-8 cancel`}</span>{`
  │
  New base `}<span className="text-accent-green font-bold">{`9,940₩`}</span>{` → repeat`}
                  </pre>
                </div>
              </div>

              {/* Col 2: Orderbook */}
              <div className="space-y-4">
                <Orderbook
                  data={orderbookData}
                  gridOrderMap={gridOrderMap}
                  ticker={activeTicker}
                  stockName={
                    stockName ||
                    instances.find((i) => i.ticker === activeTicker)?.name
                  }
                />
              </div>

              {/* Col 3-4: Instances + Trade Log */}
              <div className="xl:col-span-2 space-y-4">
                <div className="flex justify-between items-center">
                  <h2 className="text-base font-bold text-white">📈 Instances</h2>
                  <button
                    onClick={refresh}
                    className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 border border-dark-600 rounded-lg text-xs text-gray-400 transition"
                  >
                    🔄 Refresh
                  </button>
                </div>

                {filtered.length === 0 ? (
                  <div className="text-center text-gray-600 py-8 text-sm bg-dark-800 border border-dark-600 rounded-xl">
                    No active grid ladder. Configure and start from the left panel.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {filtered.map((inst) => (
                      <InstanceCard
                        key={`${inst.ticker}-${inst.env_dv}`}
                        instance={inst}
                        isActive={inst.ticker === activeTicker}
                        onSelect={switchTicker}
                        onStop={handleStop}
                        onRetry={retry}
                        onSkip={skip}
                        onEdit={setEditingInstance}
                        onDelete={handleDelete}
                      />
                    ))}
                  </div>
                )}

                {/* Trade Log */}
                <TradeLog
                  events={tradeEvents}
                  onClear={() => setTradeEvents([])}
                />
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Edit Modal */}
      {editingInstance && (
        <EditConfigModal
          instance={editingInstance}
          onSave={handleEditSave}
          onClose={() => setEditingInstance(null)}
        />
      )}
    </div>
  );
}
