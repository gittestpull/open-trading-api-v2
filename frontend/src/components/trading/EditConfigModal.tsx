"use client";

import { useState, useEffect } from "react";
import type { GridLadderInstance, GridLadderConfigUpdate } from "@/lib/types";

interface EditConfigModalProps {
  instance: GridLadderInstance | null;
  onSave: (ticker: string, envDv: string, config: GridLadderConfigUpdate) => void;
  onClose: () => void;
}

export function EditConfigModal({
  instance,
  onSave,
  onClose,
}: EditConfigModalProps) {
  const [budget, setBudget] = useState(10000000);
  const [amount, setAmount] = useState(500000);
  const [levels, setLevels] = useState("6,7,8");
  const [trigger, setTrigger] = useState(6);

  useEffect(() => {
    if (instance) {
      setBudget(instance.total_budget || 10000000);
      setAmount(instance.order_amount || 500000);
      setLevels((instance.entry_tick_levels || []).join(","));
      setTrigger(instance.trigger_level || 6);
    }
  }, [instance]);

  if (!instance) return null;

  const handleSave = () => {
    onSave(instance.ticker, instance.env_dv, {
      total_budget: budget,
      order_amount: amount,
      entry_tick_levels: levels
        .split(",")
        .map((s) => parseInt(s.trim()))
        .filter((n) => !isNaN(n)),
      trigger_level: trigger,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-dark-800 w-full max-w-md p-6 rounded-xl border border-dark-600 shadow-2xl">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-white">✏️ 설정 수정</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition text-xl"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">총 투자금</label>
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
                1회 주문금액
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
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                진입 레벨 (쉼표 구분)
              </label>
              <input
                type="text"
                value={levels}
                onChange={(e) => setLevels(e.target.value)}
                className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded-lg focus:border-accent-blue focus:outline-none text-white text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                트리거 레벨
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
          </div>
        </div>

        <div className="flex gap-3 mt-5">
          <button
            onClick={handleSave}
            className="flex-1 py-2.5 bg-accent-blue hover:opacity-80 text-white font-bold rounded-lg transition text-sm"
          >
            💾 저장
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2.5 bg-dark-700 hover:bg-dark-600 text-gray-400 font-bold rounded-lg transition text-sm border border-dark-600"
          >
            취소
          </button>
        </div>
      </div>
    </div>
  );
}
