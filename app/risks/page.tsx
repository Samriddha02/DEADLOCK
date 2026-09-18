import RiskCard from "@/components/RiskCard";
import { risks } from "@/lib/mock-data";

export default function RisksPage() {
  return (
    <div className="space-y-8">

      <div>
        <p className="text-sm font-medium text-cyan-400">
          PROJECT INTELLIGENCE
        </p>

        <h1 className="mt-2 text-4xl font-bold text-white">
          Hidden Risks
        </h1>

        <p className="mt-2 text-zinc-500">
          Risks discovered from project dependencies and activity.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {risks.map((risk) => (
          <RiskCard
            key={risk.id}
            risk={risk}
          />
        ))}
      </div>

    </div>
  );
}
