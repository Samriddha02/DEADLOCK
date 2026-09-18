"use client";

import { FormEvent, useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Risk = {
  id?: string;
  risk_id?: string;
  title?: string;
  name?: string;
  severity?: string;
  probability?: number | string;
  confidence?: number | string;
  impact?: string;
  description?: string;
  explanation?: string;
  root_cause?: string;
  evidence?: unknown;
  [key: string]: unknown;
};

type Health = {
  status?: string;
  service?: string;
};

type SyncResponse = {
  message?: string;
  owner?: string;
  repo?: string;
  project?: unknown;
};

type ApiError = {
  detail?: unknown;
};

function cleanRepositoryInput(value: string): string {
  let cleaned = value.trim();

  if (!cleaned) {
    return "";
  }

  cleaned = cleaned.replace(/\/+$/, "");

  const githubMatch = cleaned.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/?#]+)/
  );

  if (githubMatch) {
    return githubMatch[2].replace(/\.git$/, "");
  }

  return cleaned.replace(/\.git$/, "");
}

function cleanOwnerInput(value: string): string {
  let cleaned = value.trim();

  if (!cleaned) {
    return "";
  }

  const githubMatch = cleaned.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/?#]+)/
  );

  if (githubMatch) {
    return githubMatch[1];
  }

  return cleaned.replace(/^@/, "").replace(/\/+$/, "");
}

function riskId(risk: Risk): string {
  return String(risk.risk_id ?? risk.id ?? "RISK");
}

function riskTitle(risk: Risk): string {
  return String(
    risk.title ??
      risk.name ??
      risk.description ??
      risk.explanation ??
      "Detected project risk"
  );
}

function getSeverity(risk: Risk): string {
  return String(risk.severity ?? "UNKNOWN").toUpperCase();
}

function normalizeRisks(data: unknown): Risk[] {
  if (Array.isArray(data)) {
    return data.filter(
      (item): item is Risk =>
        typeof item === "object" &&
        item !== null &&
        !Array.isArray(item)
    );
  }

  if (typeof data === "object" && data !== null) {
    const object = data as Record<string, unknown>;

    for (const key of ["risks", "results", "items", "data"]) {
      if (Array.isArray(object[key])) {
        return object[key].filter(
          (item): item is Risk =>
            typeof item === "object" &&
            item !== null &&
            !Array.isArray(item)
        );
      }
    }

    return [object as Risk];
  }

  return [];
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
  });

  const text = await response.text();

  let data: unknown = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data
    ) {
      const apiError = data as ApiError;

      throw new Error(
        String(apiError.detail ?? `HTTP ${response.status}`)
      );
    }

    if (typeof data === "string" && data.trim()) {
      throw new Error(data);
    }

    throw new Error(`HTTP ${response.status}`);
  }

  return data as T;
}

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);

  const [owner, setOwner] = useState("Aritra-DSU");
  const [repo, setRepo] = useState("RF-SENTINEL");

  const [project, setProject] = useState<unknown>(null);

  const [risks, setRisks] = useState<Risk[]>([]);
  const [selectedRisk, setSelectedRisk] = useState<Risk | null>(null);

  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [simulating, setSimulating] = useState(false);

  const [error, setError] = useState("");

  useEffect(() => {
    void checkHealth();

    const interval = window.setInterval(() => {
      void checkHealth();
    }, 10000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  async function checkHealth() {
    try {
      const data = await request<Health>("/health");
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }

  async function loadResults(
    cleanOwner: string,
    cleanRepo: string
  ) {
    const encodedOwner = encodeURIComponent(cleanOwner);
    const encodedRepo = encodeURIComponent(cleanRepo);

    const [projectData, riskData] = await Promise.all([
      request<unknown>(
        `/api/projects/${encodedOwner}/${encodedRepo}`
      ),
      request<unknown>(
        `/api/risks/${encodedOwner}/${encodedRepo}`
      ),
    ]);

    setProject(projectData);

    const discoveredRisks = normalizeRisks(riskData);

    setRisks(discoveredRisks);

    setSelectedRisk(
      discoveredRisks.length > 0
        ? discoveredRisks[0]
        : null
    );
  }

  async function analyzeProject(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (loading || syncing) {
      return;
    }

    const cleanOwner = cleanOwnerInput(owner);
    const cleanRepo = cleanRepositoryInput(repo);

    if (!cleanOwner || !cleanRepo) {
      setError(
        "Enter both the repository owner and repository name."
      );
      return;
    }

    setOwner(cleanOwner);
    setRepo(cleanRepo);

    setLoading(true);
    setError("");
    setProject(null);
    setRisks([]);
    setSelectedRisk(null);

    const encodedOwner = encodeURIComponent(cleanOwner);
    const encodedRepo = encodeURIComponent(cleanRepo);

    try {
      await request<SyncResponse>(
        `/api/projects/${encodedOwner}/${encodedRepo}/sync`,
        {
          method: "POST",
        }
      );

      await loadResults(cleanOwner, cleanRepo);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze project."
      );
    } finally {
      setLoading(false);
    }
  }

  async function syncProject() {
    if (syncing || loading) {
      return;
    }

    const cleanOwner = cleanOwnerInput(owner);
    const cleanRepo = cleanRepositoryInput(repo);

    if (!cleanOwner || !cleanRepo) {
      setError("Enter owner and repository first.");
      return;
    }

    setOwner(cleanOwner);
    setRepo(cleanRepo);

    setSyncing(true);
    setError("");

    const encodedOwner = encodeURIComponent(cleanOwner);
    const encodedRepo = encodeURIComponent(cleanRepo);

    try {
      await request<SyncResponse>(
        `/api/projects/${encodedOwner}/${encodedRepo}/sync`,
        {
          method: "POST",
        }
      );

      await loadResults(cleanOwner, cleanRepo);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Sync failed."
      );
    } finally {
      setSyncing(false);
    }
  }

  async function runSimulation() {
    if (simulating || loading || syncing) {
      return;
    }

    const cleanOwner = cleanOwnerInput(owner);
    const cleanRepo = cleanRepositoryInput(repo);

    if (!cleanOwner || !cleanRepo) {
      setError("Enter owner and repository first.");
      return;
    }

    setOwner(cleanOwner);
    setRepo(cleanRepo);

    setSimulating(true);
    setError("");

    const encodedOwner = encodeURIComponent(cleanOwner);
    const encodedRepo = encodeURIComponent(cleanRepo);

    try {
      const data = await request<unknown>(
        `/api/simulate/${encodedOwner}/${encodedRepo}`,
        {
          method: "POST",
        }
      );

      const possibleRisks =
        typeof data === "object" &&
        data !== null &&
        "risks" in data
          ? (data as { risks: unknown }).risks
          : data;

      const simulationRisks =
        normalizeRisks(possibleRisks);

      setRisks(simulationRisks);

      setSelectedRisk(
        simulationRisks.length > 0
          ? simulationRisks[0]
          : null
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Simulation failed."
      );
    } finally {
      setSimulating(false);
    }
  }

  function severityClass(value: string): string {
    switch (value) {
      case "CRITICAL":
        return "critical";

      case "HIGH":
        return "high";

      case "MEDIUM":
        return "medium";

      case "LOW":
        return "low";

      default:
        return "unknown";
    }
  }

  return (
    <main className="dashboard">
      {/* HEADER */}

      <header className="header">
        <div>
          <div className="eyebrow">
            AGENTIC SOFTWARE RISK DISCOVERY
          </div>

          <h1>DEADLOCK</h1>

          <p className="subtitle">
            Discover hidden software-project risks
            before they become production failures.
          </p>
        </div>

        <div
          className={`connection ${
            health?.status === "ok"
              ? "online"
              : "offline"
          }`}
        >
          <span />

          {health?.status === "ok"
            ? "BACKEND ONLINE"
            : "BACKEND OFFLINE"}
        </div>
      </header>

      {/* PROJECT ANALYSIS */}

      <section className="control">
        <div>
          <div className="eyebrow">
            PROJECT ANALYSIS
          </div>

          <h2>Analyze a repository</h2>

          <p>
            Connect DEADLOCK to the project exposed
            by the API.
          </p>
        </div>

        <form onSubmit={analyzeProject}>
          <input
            value={owner}
            onChange={(event) =>
              setOwner(event.target.value)
            }
            placeholder="Owner"
            autoComplete="off"
            disabled={loading || syncing}
          />

          <input
            value={repo}
            onChange={(event) =>
              setRepo(event.target.value)
            }
            placeholder="Repository"
            autoComplete="off"
            disabled={loading || syncing}
          />

          <button
            type="submit"
            disabled={loading || syncing}
          >
            {loading ? "ANALYZING..." : "ANALYZE"}
          </button>
        </form>
      </section>

      {/* ERROR */}

      {error !== "" && (
        <div className="error">
          <strong>API ERROR</strong>

          <span>{error}</span>
        </div>
      )}

      {/* METRICS */}

      <section className="metrics">
        <div>
          <small>BACKEND</small>

          <strong>
            {health?.status === "ok"
              ? "ONLINE"
              : "—"}
          </strong>
        </div>

        <div>
          <small>PROJECT</small>

          <strong>
            {project !== null
              ? "LOADED"
              : "—"}
          </strong>
        </div>

        <div>
          <small>RISKS</small>

          <strong>
            {risks.length > 0
              ? risks.length
              : "—"}
          </strong>
        </div>

        <div>
          <small>ENGINE</small>

          <strong>READY</strong>
        </div>
      </section>

      {/* MAIN WORKSPACE */}

      <section className="workspace">
        {/* FIND */}

        <div className="risksPanel">
          <div className="panelHeader">
            <div>
              <div className="eyebrow">
                FIND
              </div>

              <h2>Detected Risks</h2>
            </div>

            <div className="actions">
              <button
                onClick={syncProject}
                disabled={
                  syncing ||
                  loading ||
                  !owner.trim() ||
                  !repo.trim()
                }
              >
                {syncing
                  ? "SYNCING..."
                  : "SYNC"}
              </button>

              <button
                onClick={runSimulation}
                disabled={
                  simulating ||
                  loading ||
                  syncing ||
                  !owner.trim() ||
                  !repo.trim()
                }
              >
                {simulating
                  ? "RUNNING..."
                  : "WHAT IF?"}
              </button>
            </div>
          </div>

          {risks.length === 0 ? (
            <div className="empty">
              <div>◎</div>

              <h3>No risks loaded</h3>

              <p>
                Enter an owner and repository,
                then click ANALYZE.
              </p>
            </div>
          ) : (
            <div className="riskList">
              {risks.map((risk, index) => {
                const level = getSeverity(risk);

                return (
                  <button
                    key={`${riskId(risk)}-${index}`}
                    className="risk"
                    onClick={() =>
                      setSelectedRisk(risk)
                    }
                  >
                    <div className="riskHeader">
                      <span>
                        {riskId(risk)}
                      </span>

                      <b
                        className={severityClass(
                          level
                        )}
                      >
                        {level}
                      </b>
                    </div>

                    <h3>
                      {riskTitle(risk)}
                    </h3>

                    <div className="riskMeta">
                      {risk.impact !== undefined && (
                        <span>
                          Impact:{" "}
                          {String(risk.impact)}
                        </span>
                      )}

                      {risk.probability !==
                        undefined && (
                        <span>
                          Probability:{" "}
                          {String(
                            risk.probability
                          )}
                        </span>
                      )}

                      {risk.confidence !==
                        undefined && (
                        <span>
                          Confidence:{" "}
                          {String(
                            risk.confidence
                          )}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* PROVE IT */}

        <aside className="evidencePanel">
          <div className="eyebrow">
            PROVE IT
          </div>

          {selectedRisk === null ? (
            <div className="empty">
              <div>◈</div>

              <h3>Select a risk</h3>

              <p>
                Select a detected risk to inspect
                its evidence and explanation.
              </p>
            </div>
          ) : (
            <>
              <div className="riskHeader">
                <span>
                  {riskId(selectedRisk)}
                </span>

                <b
                  className={severityClass(
                    getSeverity(selectedRisk)
                  )}
                >
                  {getSeverity(selectedRisk)}
                </b>
              </div>

              <h2>
                {riskTitle(selectedRisk)}
              </h2>

              {selectedRisk.root_cause !==
                undefined && (
                <section className="detail">
                  <label>ROOT CAUSE</label>

                  <p>
                    {String(
                      selectedRisk.root_cause
                    )}
                  </p>
                </section>
              )}

              {selectedRisk.explanation !==
                undefined && (
                <section className="detail">
                  <label>EXPLANATION</label>

                  <p>
                    {String(
                      selectedRisk.explanation
                    )}
                  </p>
                </section>
              )}

              {selectedRisk.description !==
                undefined && (
                <section className="detail">
                  <label>DESCRIPTION</label>

                  <p>
                    {String(
                      selectedRisk.description
                    )}
                  </p>
                </section>
              )}

              {selectedRisk.evidence !==
                undefined && (
                <section className="detail">
                  <label>EVIDENCE</label>

                  <pre>
                    {JSON.stringify(
                      selectedRisk.evidence,
                      null,
                      2
                    )}
                  </pre>
                </section>
              )}

              <section className="detail">
                <label>RISK DATA</label>

                <pre>
                  {JSON.stringify(
                    selectedRisk,
                    null,
                    2
                  )}
                </pre>
              </section>
            </>
          )}
        </aside>
      </section>

      {/* PROJECT CONTEXT */}

      {project !== null && (
        <section className="project">
          <div className="eyebrow">
            PROJECT CONTEXT
          </div>

          <h2>Project API Response</h2>

          <pre>
            {JSON.stringify(
              project,
              null,
              2
            )}
          </pre>
        </section>
      )}

      {/* FOOTER */}

      <footer>
        <span>DEADLOCK v0.1.0</span>

        <span>
          FIND → PROVE IT → WHAT IF?
        </span>
      </footer>
    </main>
  );
}