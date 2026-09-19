"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  ShieldAlert,
  Network,
  FlaskConical,
  FolderGit2,
  ChevronDown,
  Sparkles,
} from "lucide-react";
import { checkBackendHealth } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/risks", label: "Hidden Risks", icon: ShieldAlert },
  { href: "/graph", label: "Dependency Graph", icon: Network },
  { href: "/what-if", label: "What-If", icon: FlaskConical },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const { repositories, activeRepo, activeRepoId, setActiveRepoId, loadDemoProject } = useWorkspace();

  useEffect(() => {
    let mounted = true;
    const verify = async () => {
      const ok = await checkBackendHealth();
      if (mounted) setIsOnline(ok);
    };

    verify();
    const interval = setInterval(verify, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <aside className="fixed left-0 top-0 flex h-screen w-64 flex-col justify-between border-r border-white/10 bg-[#09090b] p-5 z-50">
      <div className="space-y-6">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.2em] text-cyan-400">
            EVIDENCE-FIRST
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white">
            DEADLOCK
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Project Intelligence Engine
          </p>
        </div>

        {/* ACTIVE WORKSPACE REPO SELECTOR */}
        <div className="relative">
          <div className="text-[10px] font-semibold tracking-wider text-zinc-500 uppercase mb-1.5 flex items-center justify-between">
            <span>Active Repository</span>
            <span className="text-[9px] text-cyan-400">{repositories.length} in Workspace</span>
          </div>

          <button
            onClick={() => setSelectorOpen(!selectorOpen)}
            className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] p-2.5 text-left text-xs transition hover:bg-white/[0.07] focus:outline-none"
          >
            <div className="flex items-center gap-2 truncate">
              <FolderGit2 size={15} className="text-cyan-400 shrink-0" />
              <div className="truncate">
                <div className="truncate font-medium text-zinc-200">
                  {activeRepo ? activeRepo.fullName : "No Repo Selected"}
                </div>
                <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      activeRepo?.status === "READY"
                        ? "bg-emerald-400"
                        : activeRepo?.status === "ANALYZING" || activeRepo?.status === "SYNCING"
                        ? "bg-amber-400 animate-pulse"
                        : activeRepo?.status === "ERROR"
                        ? "bg-red-400"
                        : "bg-zinc-500"
                    }`}
                  />
                  <span>
                    {activeRepo?.source === "seeded"
                      ? "DEMO DATASET"
                      : activeRepo?.status || "READY"}
                  </span>
                </div>
              </div>
            </div>
            <ChevronDown size={14} className="text-zinc-500 shrink-0" />
          </button>

          {/* DROPDOWN MENU */}
          {selectorOpen && (
            <div className="absolute left-0 right-0 top-full mt-1.5 z-50 rounded-xl border border-white/15 bg-[#111113] p-1.5 shadow-2xl backdrop-blur-xl">
              <div className="max-h-52 overflow-y-auto space-y-1">
                {repositories.length === 0 ? (
                  <div className="p-2 text-center text-xs text-zinc-500">
                    No repositories analyzed yet
                  </div>
                ) : (
                  repositories.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => {
                        setActiveRepoId(r.id);
                        setSelectorOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition ${
                        activeRepoId === r.id
                          ? "bg-cyan-500/15 text-cyan-300 font-medium"
                          : "text-zinc-300 hover:bg-white/5"
                      }`}
                    >
                      <div className="truncate pr-2">
                        <div className="truncate">{r.fullName}</div>
                        <div className="text-[9px] text-zinc-500">
                          {r.riskCount ?? 0} risks • {r.nodeCount ?? 0} nodes
                        </div>
                      </div>
                      <span
                        className={`h-2 w-2 rounded-full shrink-0 ${
                          r.status === "READY"
                            ? "bg-emerald-400"
                            : r.status === "ERROR"
                            ? "bg-red-400"
                            : "bg-amber-400 animate-pulse"
                        }`}
                      />
                    </button>
                  ))
                )}
              </div>

              <div className="border-t border-white/10 mt-1 pt-1 space-y-1">
                <button
                  onClick={() => {
                    loadDemoProject();
                    setSelectorOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-purple-300 transition hover:bg-purple-500/10"
                >
                  <Sparkles size={13} />
                  Load CampusConnect Demo
                </button>
              </div>
            </div>
          )}
        </div>

        <nav className="space-y-1.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive =
              pathname === href || (href !== "/dashboard" && pathname.startsWith(href));

            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "border border-cyan-400/20 bg-cyan-400/10 text-cyan-300"
                    : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
                }`}
              >
                <Icon
                  size={18}
                  className={isActive ? "text-cyan-400" : "text-zinc-500"}
                />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* BACKEND STATUS FOOTER */}
      <div className="border-t border-white/10 pt-4 space-y-2">
        <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              {isOnline && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                  isOnline === true
                    ? "bg-emerald-500"
                    : isOnline === false
                    ? "bg-amber-500"
                    : "bg-zinc-600"
                }`}
              />
            </span>
            <span className="text-xs font-medium text-zinc-300">
              {isOnline === true
                ? "Backend Online"
                : isOnline === false
                ? "Backend Offline"
                : "Checking..."}
            </span>
          </div>
          <span className="text-[10px] text-zinc-500">:8000</span>
        </div>
        {/* DEADLOCK_CANONICAL marker — confirms correct frontend is running */}
        <div className="text-[9px] text-zinc-700 text-center select-none">
          DEADLOCK_CANONICAL · {process.env.NODE_ENV}
        </div>
      </div>
    </aside>
  );
}

