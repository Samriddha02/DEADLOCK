import Link from "next/link";
import { Risk } from "@/lib/types";

export default function RiskCard({ risk }: { risk: Risk }) {
  return (
    <Link href={`/risks/${risk.id}`}>
      <div className="rounded-xl border border-white/10 bg-[#111113] p-5 transition hover:border-red-400/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-red-400">
            {risk.severity}
          </span>

          <span className="text-sm text-zinc-400">
            {risk.probability}% probability
          </span>
        </div>

        <h3 className="mt-3 text-lg font-semibold text-white">
          {risk.title}
        </h3>

        <p className="mt-2 text-sm text-zinc-500">
          Root cause: {risk.rootCause}
        </p>

        <div className="mt-4">
          <p className="text-xs text-zinc-600">
            AFFECTED
          </p>

          <div className="mt-2 flex flex-wrap gap-2">
            {risk.affected.map((item) => (
              <span
                key={item}
                className="rounded-md bg-white/5 px-2 py-1 text-xs text-zinc-400"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
}