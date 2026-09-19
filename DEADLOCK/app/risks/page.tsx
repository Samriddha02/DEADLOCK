"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, RefreshCw, AlertTriangle, FolderGit2 } from "lucide-react";
import RiskCard from "@/components/RiskCard";
import { fetchProjectRisks } from "@/lib/api";
import { Risk } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace-context";

export default function RisksPage() {
  const { activeRepo } = useWorkspace();
  const [risksList, setRisksList] = useState<Risk[]>([]);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [isLive, setIsLive] = useState(false);

  const loadRisks = useCallback(async () => {
    setLoading(true);
    try {
      if (activeRepo && activeRepo.source !== "seeded") {
        const res = await fetchProjectRisks(activeRepo.owner, activeRepo.repo);
        setRisksList(res.risks);
        setIsLive(res.isLive);
      } else {
        const res = await fetchProjectRisks();
        setRisksList(res.risks);
        setIsLive(res.isLive);
      }
    } catch {
      setIsLive(false);
      setRisksList([]);
    } finally {
      setLoading(false);
    }
  }, [activeRepo]);

  useEffect(() => {
    loadRisks();
  }, [loadRisks]);

  const filteredRisks = risksList.filter((risk) => {
    const matchesSev =
      selectedSeverity === "ALL" || risk.severity === selectedSeverity;
    const matchesSearch =
      searchQuery.trim() === "" ||
      risk.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      risk.rootCause.toLowerCase().includes(searchQuery.toLowerCase()) ||
      risk.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSev && matchesSearch;
  });

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-cyan-400">
              PROJECT INTELLIGENCE
            </p>
            <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300 border border-cyan-500/20 flex items-center gap-1">
              <FolderGit2 size={11} />
              {activeRepo ? activeRepo.fullName : "CampusConnect (Demo)"}
            </span>
            {isLive && (
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
                Live Graph
              </span>
            )}
          </div>

          <h1 className="mt-2 text-4xl font-bold tracking-tight text-white">
            Hidden Failure Risks
          </h1>

          <p className="mt-2 text-zinc-500">
            Explainable risks scored 0–100 based on causal propagation depth and evidence for{" "}
            <strong className="text-zinc-300">{activeRepo ? activeRepo.fullName : "CampusConnect"}</strong>.
          </p>
        </div>

        <button
          onClick={loadRisks}
          disabled={loading}
          className="flex items-center gap-1.5 self-start rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/10 disabled:opacity-50 md:self-end"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh Analysis
        </button>
      </div>

      {/* FILTERS & SEARCH */}
      <div className="flex flex-col gap-4 rounded-xl border border-white/10 bg-[#111113] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          {["ALL", "CRITICAL", "HIGH", "MEDIUM"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                selectedSeverity === sev
                  ? "bg-white/15 text-white"
                  : "text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        <div className="relative min-w-[240px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
          />
          <input
            type="text"
            placeholder="Search risks, root causes, IDs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-[#09090b] py-2 pl-9 pr-4 text-xs text-white placeholder:text-zinc-600 focus:border-cyan-400/50 focus:outline-none"
          />
        </div>
      </div>

      {/* RISK LIST */}
      {filteredRisks.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-[#111113] py-16 text-center">
          <AlertTriangle size={32} className="text-zinc-600" />
          <h3 className="mt-4 text-sm font-semibold text-white">
            No risks identified for {activeRepo ? activeRepo.fullName : "this repository"}
          </h3>
          <p className="mt-1 text-xs text-zinc-500 max-w-sm">
            The deterministic risk engine detected 0 blocker chains or hazards for this project topology.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {filteredRisks.map((risk) => (
            <RiskCard key={risk.id} risk={risk} />
          ))}
        </div>
      )}
    </div>
  );
}