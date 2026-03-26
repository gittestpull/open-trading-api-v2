"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function MagaPage() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">
          <div className="max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold text-white mb-2 flex items-center gap-2">
              🇺🇸 <span className="text-accent-red">MAGA</span> Panel
            </h1>
            <p className="text-sm text-gray-500 mb-8">
              Trump beneficiary stocks analysis
            </p>

            <div className="bg-dark-800 border border-dark-600 rounded-xl p-8 text-center">
              <p className="text-gray-500 mb-4">
                MAGA panel is available in the legacy UI.
              </p>
              <a
                href="http://localhost:8080"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block px-6 py-2 bg-accent-blue hover:opacity-80 text-white font-bold rounded-lg transition text-sm"
              >
                Open Legacy UI ↗
              </a>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
