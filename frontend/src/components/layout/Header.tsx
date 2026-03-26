"use client";

export function Header() {
  return (
    <header className="bg-dark-800 border-b border-dark-600 px-4 py-2 flex items-center justify-between">
      <div className="flex items-center gap-6 text-xs">
        <IndexItem label="KOSPI" />
        <IndexItem label="KOSDAQ" />
        <IndexItem label="USD/KRW" />
        <IndexItem label="BTC" />
      </div>
      <div className="text-xs text-gray-500">
        {new Date().toLocaleDateString("ko-KR")}
      </div>
    </header>
  );
}

function IndexItem({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-500">{label}</span>
      <span className="font-bold text-white">-</span>
    </div>
  );
}
