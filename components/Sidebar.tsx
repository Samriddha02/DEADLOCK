"use client";

import Link from "next/link";
import {
  LayoutDashboard,
  ShieldAlert,
  Network,
  FlaskConical,
} from "lucide-react";

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 border-r border-white/10 bg-[#09090b] p-5">
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-white">DEADLOCK</h1>
        <p className="text-xs text-zinc-500">
          Project Intelligence Engine
        </p>
      </div>

      <nav className="space-y-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-3 rounded-lg px-3 py-3 text-zinc-300 hover:bg-white/5"
        >
          <LayoutDashboard size={18} />
          Dashboard
        </Link>

        <Link
          href="/risks"
          className="flex items-center gap-3 rounded-lg px-3 py-3 text-zinc-300 hover:bg-white/5"
        >
          <ShieldAlert size={18} />
          Hidden Risks
        </Link>

        <Link
          href="/graph"
          className="flex items-center gap-3 rounded-lg px-3 py-3 text-zinc-300 hover:bg-white/5"
        >
          <Network size={18} />
          Dependency Graph
        </Link>

        <Link
          href="/what-if"
          className="flex items-center gap-3 rounded-lg px-3 py-3 text-zinc-300 hover:bg-white/5"
        >
          <FlaskConical size={18} />
          What-If
        </Link>
      </nav>
    </aside>
  );
}
