import { Evidence } from "@/lib/types";

export default function EvidencePanel({
  evidence,
}: {
  evidence: Evidence[];
}) {
  return (
    <div className="space-y-3">
      {evidence.map((item, index) => (
        <div
          key={index}
          className="rounded-lg border border-white/10 bg-[#111113] p-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-white">{item.source}</span>
            {item.status && (
              <span className="rounded-md bg-white/5 px-2 py-1 text-xs text-zinc-500">
                {item.status}
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-zinc-500">{item.detail}</p>
        </div>
      ))}
    </div>
  );
}
