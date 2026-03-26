"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">
          <div className="max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold text-accent-blue mb-2">
              Dashboard
            </h1>
            <p className="text-sm text-gray-500 mb-8">
              AI-Powered Investment Analysis Platform
            </p>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              <DashCard
                title="⚡ Scalper"
                desc="자동 스캘핑 트레이딩"
                href="http://localhost:8080"
              />
              <DashCard
                title="📊 Grid Ladder"
                desc="그리드 래더 매매"
                href="/grid-ladder"
                internal
              />
              <DashCard
                title="🔍 Screener"
                desc="종목 검색 & 필터"
                href="http://localhost:8080"
              />
              <DashCard
                title="🔬 Deep Dive"
                desc="종목 심층 분석"
                href="http://localhost:8080"
              />
              <DashCard
                title="🧠 Human Index"
                desc="인간지표 (관심도/FOMO)"
                href="http://localhost:8080"
              />
              <DashCard
                title="🇺🇸 MAGA"
                desc="트럼프 수혜주 분석"
                href="/maga"
                internal
              />
            </div>

            <div className="mt-8 p-4 bg-dark-800 border border-dark-600 rounded-xl text-center text-gray-500 text-sm">
              Other tabs are available in the{" "}
              <a
                href="http://localhost:8080"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-blue hover:underline"
              >
                Legacy UI ↗
              </a>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function DashCard({
  title,
  desc,
  href,
  internal,
}: {
  title: string;
  desc: string;
  href: string;
  internal?: boolean;
}) {
  const Tag = internal ? "a" : "a";
  return (
    <Tag
      href={href}
      target={internal ? undefined : "_blank"}
      rel={internal ? undefined : "noopener noreferrer"}
      className="block bg-dark-800 border border-dark-600 rounded-xl p-5 hover:border-accent-blue/50 transition group"
    >
      <h3 className="text-base font-bold text-white group-hover:text-accent-blue transition mb-1">
        {title}
      </h3>
      <p className="text-xs text-gray-500">{desc}</p>
    </Tag>
  );
}
