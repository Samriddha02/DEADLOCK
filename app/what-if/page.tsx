"use client";

import { useState } from "react";

export default function WhatIfPage() {
  const [scenario, setScenario] = useState("");
  const [result, setResult] = useState(false);

  function simulate() {
    if (!scenario) return;
    setResult(true);
  }

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <p className="text-sm font-medium text-cyan-400">
          PREDICTIVE SIMULATION
        </p>

        <h1 className="mt-2 text-4xl font-bold text-white">
          What-If Simulation
        </h1>

        <p className="mt-2 text-zinc-500">
          Simulate project changes and observe how risk propagates.
        </p>
      </div>

      <div className="rounded-xl border border-white/10 bg-[#111113] p-6">
        <label className="text-sm text-zinc-400">
          Select a scenario
        </label>

        <select
          value={scenario}
          onChange={(e) => {
            setScenario(e.target.value);
            setResult(false);
          }}
          className="mt-3 w-full rounded-lg border border-white/10 bg-[#09090b] p-3 text-white outline-none"
        >
          <option value="">Choose a scenario</option>
          <option value="delay">
            PR #47 delayed by 3 days
          </option>
          <option value="developer">
            Authentication developer becomes unavailable
          </option>
          <option value="dependency">
            Authentication dependency becomes blocked
          </option>
        </select>

        <button
          onClick={simulate}
          disabled={!scenario}
          className="mt-4 rounded-lg bg-cyan-400 px-5 py-3 font-semibold text-black transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Run Simulation
        </button>
      </div>

      {result && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
          <p className="text-sm font-semibold text-red-400">
            SIMULATION RESULT
          </p>

          <h2 className="mt-2 text-2xl font-bold text-white">
            Risk propagation detected
          </h2>

          <p className="mt-2 text-sm text-zinc-500">
            The selected change creates additional downstream project risk.
          </p>

          <div className="mt-6 grid grid-cols-3 gap-4">
            <div className="rounded-lg bg-black/30 p-4">
              <p className="text-xs text-zinc-500">INTEGRATION TESTING</p>
              <p className="mt-2 font-semibold text-yellow-400">HIGH</p>
            </div>

            <div className="rounded-lg bg-black/30 p-4">
              <p className="text-xs text-zinc-500">DEPLOYMENT</p>
              <p className="mt-2 font-semibold text-orange-400">HIGH</p>
            </div>

            <div className="rounded-lg bg-black/30 p-4">
              <p className="text-xs text-zinc-500">CLIENT DEMO</p>
              <p className="mt-2 font-semibold text-red-400">CRITICAL</p>
            </div>
          </div>

          <div className="mt-6 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-4">
            <p className="text-xs font-semibold text-cyan-400">
              RECOMMENDED ACTION
            </p>

            <p className="mt-2 text-sm text-white">
              Resolve PR #47 immediately or reassign the authentication task.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
