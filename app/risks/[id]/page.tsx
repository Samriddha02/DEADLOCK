import { notFound } from "next/navigation";
import { risks } from "@/lib/mock-data";
import CausalChain from "@/components/CausalChain";
import EvidencePanel from "@/components/EvidencePanel";

export default async function RiskDetails({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const risk = risks.find((item) => item.id === id);

  if (!risk) {
    notFound();
  }

  return (
    <div className="max-w-5xl space-y-8">

      <div>
        <p className="text-sm font-bold text-red-400">
          {risk.severity} RISK
        </p>

        <h1 className="mt-2 text-4xl font-bold text-white">
          {risk.title}
        </h1>

        <p className="mt-3 text-zinc-500">
          {risk.description}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">

        <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
          <p className="text-xs text-zinc-500">
            FAILURE PROBABILITY
          </p>

          <p className="mt-2 text-3xl font-bold text-white">
            {risk.probability}%
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
          <p className="text-xs text-zinc-500">
            IMPACT
          </p>

          <p className="mt-2 text-3xl font-bold text-white">
            {risk.impact}
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
          <p className="text-xs text-zinc-500">
            ROOT CAUSE
          </p>

          <p className="mt-2 text-xl font-bold text-white">
            {risk.rootCause}
          </p>
        </div>

      </div>

      <section>
        <h2 className="mb-4 text-xl font-semibold text-white">
          Causal Chain
        </h2>

        <CausalChain items={risk.affected} />
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold text-white">
          Evidence
        </h2>

        <EvidencePanel evidence={risk.evidence} />
      </section>

      <section className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-6">
        <p className="text-xs font-semibold text-cyan-400">
          RECOMMENDED INTERVENTION
        </p>

        <p className="mt-3 text-white">
          {risk.recommendation}
        </p>
      </section>

    </div>
  );
}
