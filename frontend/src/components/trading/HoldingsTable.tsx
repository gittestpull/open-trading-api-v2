"use client";

import { formatNumber } from "@/lib/utils";
import { calcAvgPrice, calcTotalQty } from "@/lib/utils";

interface HoldingsTableProps {
  holdings: [number, number][];
}

export function HoldingsTable({ holdings }: HoldingsTableProps) {
  const avgPrice = calcAvgPrice(holdings);
  const totalQty = calcTotalQty(holdings);

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-dark-600">
            <th className="text-left py-1 px-1">#</th>
            <th className="text-right py-1 px-1">Price</th>
            <th className="text-right py-1 px-1">Qty</th>
            <th className="text-right py-1 px-1">Amount</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map(([price, qty], i) => (
            <tr key={i} className="border-b border-dark-600/30">
              <td className="py-1 px-1 text-gray-500">{i + 1}</td>
              <td className="py-1 px-1 text-right text-accent-blue">
                {formatNumber(price)}
              </td>
              <td className="py-1 px-1 text-right">{qty}</td>
              <td className="py-1 px-1 text-right">
                {formatNumber(price * qty)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-dark-600 font-bold text-white text-xs">
            <td colSpan={2} className="py-1 px-1">
              Avg {avgPrice ? `${formatNumber(avgPrice)}₩` : "-"}
            </td>
            <td className="text-right py-1 px-1">{totalQty}주</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
