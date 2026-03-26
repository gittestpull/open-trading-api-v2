"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: string;
  external?: boolean;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    title: "Trading",
    items: [
      { label: "Scalper", href: "/dashboard", icon: "⚡" },
      { label: "Grid Ladder", href: "/grid-ladder", icon: "📊" },
    ],
  },
  {
    title: "Analysis",
    items: [
      { label: "Screener", href: "/dashboard?tab=screener", icon: "🔍" },
      { label: "Deep Dive", href: "/dashboard?tab=deepdive", icon: "🔬" },
      { label: "Human Index", href: "/dashboard?tab=human", icon: "🧠" },
    ],
  },
  {
    title: "Strategy",
    items: [
      { label: "MAGA", href: "/maga", icon: "🇺🇸" },
      { label: "Backtest", href: "/dashboard?tab=backtest", icon: "📈" },
      { label: "Simulator", href: "/dashboard?tab=simulator", icon: "🎮" },
    ],
  },
  {
    title: "Management",
    items: [
      { label: "Journal", href: "/dashboard?tab=journal", icon: "📝" },
      { label: "Admin", href: "/dashboard?tab=admin", icon: "⚙️" },
      { label: "Reports", href: "/dashboard?tab=report", icon: "📋" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 bg-dark-800 border-r border-dark-600 min-h-screen p-4 hidden lg:block">
      <Link href="/" className="block mb-6">
        <h1 className="text-lg font-bold text-accent-blue">Deep Dive</h1>
        <p className="text-[10px] text-gray-500">AI Investment Platform</p>
      </Link>

      <nav className="space-y-5">
        {navGroups.map((group) => (
          <div key={group.title}>
            <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2 px-2">
              {group.title}
            </h3>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const isActive =
                  item.href === pathname ||
                  (item.href === "/dashboard" && pathname === "/dashboard");
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition",
                        isActive
                          ? "bg-accent-blue/10 text-accent-blue font-medium"
                          : "text-gray-400 hover:text-white hover:bg-dark-700"
                      )}
                    >
                      <span className="text-base">{item.icon}</span>
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Link to legacy UI */}
      <div className="mt-8 pt-4 border-t border-dark-600">
        <a
          href="http://localhost:8080"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-2 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition"
        >
          ↗ Legacy UI
        </a>
      </div>
    </aside>
  );
}
