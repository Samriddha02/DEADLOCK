"use client";

import { useState } from "react";
import { Evidence } from "@/lib/types";

export default function EvidencePanel({
  evidence,
}: {
  evidence: Evidence[];
}) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (!evidence || evidence.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-[#111113] p-6">
        <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">
          EVIDENCE
        </div>

        <p className="mt-3 text-sm text-zinc-500">
          No supporting evidence is available for this finding.
        </p>
      </div>
    );
  }

  const selected = evidence[selectedIndex];

  const isInferred = selected.inferred === true;

  const confidence =
    selected.confidence !== undefined
      ? Math.round(selected.confidence * 100)
      : null;

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111113]">
      {/* HEADER */}
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">
              Code Evidence
            </h2>

            <p className="mt-1 text-xs text-zinc-500">
              Supporting project evidence behind this risk
            </p>
          </div>

          <div className="rounded-md border border-cyan-400/20 bg-cyan-400/5 px-3 py-1.5 text-[10px] font-medium tracking-wide text-cyan-400">
            EVIDENCE FIRST
          </div>
        </div>

        {/* TABS */}
        <div className="mt-5 flex gap-1 overflow-x-auto">
          {evidence.map((item, index) => (
            <button
              key={index}
              onClick={() => setSelectedIndex(index)}
              className={`whitespace-nowrap rounded-md px-3 py-2 text-xs transition ${
                selectedIndex === index
                  ? "border border-cyan-400/30 bg-cyan-400/10 text-cyan-300"
                  : "border border-transparent text-zinc-500 hover:bg-white/[0.03] hover:text-zinc-300"
              }`}
            >
              {item.filePath ||
                item.source ||
                `Evidence ${index + 1}`}
            </button>
          ))}
        </div>
      </div>

      {/* CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px]">
        {/* CODE */}
        <div className="border-b border-white/10 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-zinc-300">
                {selected.filePath || selected.source}
              </span>

              {selected.startLine && (
                <span className="rounded-md bg-white/5 px-2 py-1 text-[10px] text-zinc-500">
                  Lines {selected.startLine}
                  {selected.endLine
                    ? `–${selected.endLine}`
                    : ""}
                </span>
              )}
            </div>

            {selected.code && (
              <button
                onClick={() =>
                  navigator.clipboard.writeText(
                    selected.code || ""
                  )
                }
                className="rounded-md border border-white/10 px-3 py-1.5 text-[10px] text-zinc-400 transition hover:border-white/20 hover:text-white"
              >
                Copy
              </button>
            )}
          </div>

          {selected.code ? (
            <div className="overflow-x-auto bg-[#09090b] p-5">
              <pre className="text-xs leading-6 text-zinc-300">
                {selected.code.split("\n").map(
                  (line, index) => {
                    const lineNumber =
                      (selected.startLine || 1) + index;

                    return (
                      <div
                        key={index}
                        className="flex min-w-max"
                      >
                        <span className="mr-5 w-8 select-none text-right text-zinc-700">
                          {lineNumber}
                        </span>

                        <code>{line}</code>
                      </div>
                    );
                  }
                )}
              </pre>
            </div>
          ) : (
            <div className="min-h-[260px] bg-[#09090b] p-6">
              <div className="text-xs text-zinc-600">
                Relevant source
              </div>

              <p className="mt-4 text-sm leading-6 text-zinc-400">
                {selected.detail}
              </p>
            </div>
          )}
        </div>

        {/* EVIDENCE DETAILS */}
        <div className="bg-[#0d0d0f] p-5">
          <div className="text-xs font-medium tracking-[0.14em] text-zinc-500">
            EVIDENCE DETAILS
          </div>

          <div className="mt-5 space-y-4">
            <DetailRow
              label="Source"
              value={selected.filePath || selected.source}
            />

            {selected.sourceType && (
              <DetailRow
                label="Type"
                value={selected.sourceType}
              />
            )}

            {selected.relationship && (
              <div>
                <div className="text-[10px] tracking-wide text-zinc-600">
                  RELATIONSHIP
                </div>

                <div className="mt-1 text-xs text-zinc-300">
                  {selected.relationship}
                </div>
              </div>
            )}

            <div>
              <div className="text-[10px] tracking-wide text-zinc-600">
                RELATIONSHIP TYPE
              </div>

              <div
                className={`mt-1 inline-flex rounded-md px-2 py-1 text-[10px] font-medium ${
                  isInferred
                    ? "bg-purple-500/10 text-purple-400"
                    : "bg-cyan-500/10 text-cyan-400"
                }`}
              >
                {isInferred ? "INFERRED" : "DIRECT"}
              </div>
            </div>

            {confidence !== null && (
              <DetailRow
                label="Confidence"
                value={`${confidence}%`}
              />
            )}

            {selected.status && (
              <DetailRow
                label="Status"
                value={selected.status}
              />
            )}

            {/* WHY */}
            <div className="border-t border-white/10 pt-4">
              <div className="text-[10px] tracking-wide text-zinc-600">
                WHY THIS MATTERS
              </div>

              <p className="mt-2 text-xs leading-5 text-zinc-400">
                {selected.detail}
              </p>
            </div>

            {/* INFERENCE RULE */}
            {isInferred && selected.inferenceRule && (
              <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-4">
                <div className="text-[10px] font-medium tracking-wide text-purple-400">
                  INFERENCE RULE
                </div>

                <p className="mt-2 text-xs leading-5 text-zinc-400">
                  {selected.inferenceRule}
                </p>
              </div>
            )}

            {/* SOURCE URL */}
            {selected.sourceUrl && (
              <a
                href={selected.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="block text-xs text-cyan-400 hover:text-cyan-300"
              >
                Open source →
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="text-[10px] tracking-wide text-zinc-600">
        {label}
      </div>

      <div className="mt-1 break-words text-xs text-zinc-300">
        {value}
      </div>
    </div>
  );
}