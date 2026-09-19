"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Play, ShieldAlert, CheckCircle2 } from "lucide-react";

import CausalChain from "@/components/CausalChain";
import EvidencePanel from "@/components/EvidencePanel";
import { fetchRiskById } from "@/lib/api";
import { Risk } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace-context";

export default function RiskDetailPage() {
  const params = useParams();
  const id = decodeURIComponent(String(params.id));
  const { activeRepo } = useWorkspace();

  const [risk, setRisk] = useState<Risk | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      const res = await fetchRiskById(
        id,
        activeRepo?.source !== "seeded" ? activeRepo?.owner : undefined,
        activeRepo?.source !== "seeded" ? activeRepo?.repo : undefined
      );
      if (active) {
        setRisk(res.risk);
        setIsLive(res.isLive);
        setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [id, activeRepo]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
        <p className="text-xs text-zinc-500">Loading risk intelligence and causal graph proof...</p>
      </div>
    );
  }

  if (!risk) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="text-center">
          <ShieldAlert size={40} className="mx-auto text-zinc-600" />
          <h1 className="mt-4 text-xl font-semibold text-white">Risk Not Found</h1>
          <p className="mt-1 text-xs text-zinc-500">
            No risk identified matching &ldquo;{id}&rdquo;.
          </p>
          <Link
            href="/risks"
            className="mt-5 inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-cyan-300 hover:bg-white/10"
          >
            <ArrowLeft size={14} />
            Back to Hidden Risks
          </Link>
        </div>
      </div>
    );
  }

  const score = risk.score ?? risk.probability;
  const chain =
    risk.affected && risk.affected.length > 0
      ? risk.affected
      : [risk.rootCause, "Deployment", "Milestone"];

  return (
    <div className="space-y-6 pb-12">
      {/* TOP BAR */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Link href="/risks" className="flex items-center gap-1 hover:text-zinc-300">
            <ArrowLeft size={13} />
            Hidden Risks
          </Link>
          <span className="text-zinc-700">/</span>
          <span className="font-mono text-zinc-400">{risk.id}</span>
        </div>

        <div className="flex items-center gap-3">
          {isLive && (
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-medium text-emerald-400">
              Deterministic Proof Verified
            </span>
          )}

          <Link
            href={`/what-if?node=${encodeURIComponent(risk.rootCause)}`}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-medium text-cyan-300 transition hover:bg-cyan-400/20"
          >
            <Play size={12} />
            Simulate Propagation
          </Link>
        </div>
      </div>

      {/* HERO */}
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_330px]">
        <div className="rounded-xl border border-white/10 bg-[#111113] p-6">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-md px-3 py-1 text-xs font-bold ${
                risk.severity === "CRITICAL"
                  ? "bg-red-500/15 text-red-400 border border-red-500/30"
                  : risk.severity === "HIGH"
                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                  : "bg-yellow-500/15 text-yellow-400 border border-yellow-500/30"
              }`}
            >
              {risk.severity}
            </span>

            {risk.verified && (
              <span className="inline-flex items-center gap-1 rounded-md bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300">
                <CheckCircle2 size={12} />
                Graph Reachability Verified
              </span>
            )}
          </div>

          <h1 className="mt-4 text-2xl font-bold tracking-tight text-white lg:text-3xl">
            {risk.title}
          </h1>

          <p className="mt-3 text-sm leading-6 text-zinc-300">
            {risk.description}
          </p>

          <div className="mt-4 flex items-center gap-2 border-t border-white/10 pt-3 text-sm">
            <span className="text-xs font-medium text-zinc-500">ROOT CAUSE:</span>
            <span className="font-semibold text-cyan-400">{risk.rootCause}</span>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-[10px] tracking-wide text-zinc-600">AFFECTED NODES:</span>
            {chain.map((item, idx) => (
              <span
                key={`${item}-${idx}`}
                className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-300"
              >
                {item}
              </span>
            ))}
          </div>
        </div>

        {/* SCORE CARD */}
        <div className="flex flex-col justify-between rounded-xl border border-white/10 bg-[#111113] p-6">
          <div>
            <div className="text-xs font-medium tracking-wider text-zinc-500">
              PRIORITIZATION RISK SCORE
            </div>

            <div className="mt-3 flex items-baseline">
              <span
                className={`text-5xl font-extrabold ${
                  score >= 75
                    ? "text-red-400"
                    : score >= 45
                    ? "text-orange-400"
                    : "text-yellow-400"
                }`}
              >
                {score}
              </span>
              <span className="ml-2 text-sm text-zinc-600">/ 100</span>
            </div>

            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  score >= 75
                    ? "bg-red-500"
                    : score >= 45
                    ? "bg-orange-500"
                    : "bg-yellow-500"
                }`}
                style={{ width: `${Math.min(score, 100)}%` }}
              />
            </div>
          </div>

          {/* FACTOR CONTRIBUTIONS */}
          {risk.factors && risk.factors.length > 0 && (
            <div className="mt-6 border-t border-white/10 pt-4">
              <div className="text-[10px] font-semibold tracking-wider text-zinc-500">
                SCORE BREAKDOWN
              </div>
              <div className="mt-2 space-y-1.5">
                {risk.factors.map((f, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-zinc-400">{f.name}</span>
                    <span className="font-mono text-zinc-300">+{f.contribution.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* SUMMARY & CAUSAL CHAIN */}
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* SUMMARY */}
        <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
          <h2 className="text-base font-semibold text-white">Impact Analysis</h2>
          <div className="mt-4 divide-y divide-white/5">
            <SummaryRow label="Severity" value={risk.severity} badge />
            <SummaryRow label="Risk Score" value={`${score} / 100`} />
            <SummaryRow label="Potential Impact" value={risk.impact} />
            <SummaryRow label="Root Cause Node" value={risk.rootCause} />
            <SummaryRow label="Evidence Items" value={`${risk.evidence.length} sources confirmed`} />
          </div>
        </div>

        {/* DEPENDENCY CHAIN */}
        <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
          <h2 className="text-base font-semibold text-white">Verified Causal Chain</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Deterministic failure propagation order
          </p>

          <div className="mt-5">
            <CausalChain items={chain} />
          </div>
        </div>
      </section>

      {/* CODE EVIDENCE PANEL */}
      <section>
        <EvidencePanel evidence={risk.evidence} />
      </section>

      {/* RECOMMENDED ACTION */}
      <section className="rounded-xl border border-white/10 bg-[#111113] p-6">
        <div className="text-xs font-semibold tracking-wider text-cyan-400">
          RECOMMENDED MITIGATION
        </div>
        <h3 className="mt-2 text-lg font-semibold text-white">
          Resolution Strategy
        </h3>
        <p className="mt-2 text-sm leading-6 text-zinc-300">
          {risk.recommendation}
        </p>

        <div className="mt-5 flex items-center gap-3">
          <Link
            href={`/what-if?node=${encodeURIComponent(risk.rootCause)}`}
            className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-medium text-cyan-300 transition hover:bg-cyan-400/20"
          >
            <Play size={13} />
            Test What-If Delay on {risk.rootCause}
          </Link>
          <Link
            href="/graph"
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/10"
          >
            Locate in Dependency Graph
          </Link>
        </div>
      </section>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  badge = false,
}: {
  label: string;
  value: string;
  badge?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <span className="text-xs text-zinc-500">{label}</span>
      {badge ? (
        <span className="rounded bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400">
          {value}
        </span>
      ) : (
        <span className="text-right text-xs font-medium text-zinc-200">{value}</span>
      )}
    </div>
  );
}