# DEADLOCK

> **"Find failures before they become failures."**

DEADLOCK is an evidence-first software project intelligence system. It analyzes real GitHub repositories, builds an evidence-backed dependency graph across code, pull requests, issues, tests, deployments, and services, detects failure propagation paths, calculates deterministic risk scores, and enables teams to simulate "What-If" scenarios before code changes cause cascading production outages.

---

## Overview

Modern software engineering projects comprise thousands of interconnected components: source files, package dependencies, open pull requests, tracking issues, microservices, CI/CD pipelines, automated tests, and distributed developers. When a pull request stalls, an API contract changes, or an external dependency fails, engineering teams rarely have immediate visibility into which downstream services, tests, or release deadlines are at risk—or **why**.

Most AI developer tools focus on code generation ("*What code should I write?*"). **DEADLOCK focuses on project-level failure propagation and dependency intelligence ("*If this component changes or fails, what else is affected downstream, and what is the exact evidence?*").**

![DEADLOCK Project Workspace Dashboard](assets/WhatsApp%20Image%202026-09-19%20at%2015.18.54.jpeg)

```
┌────────────────────┐     ┌────────────────────────┐     ┌───────────────────────┐
│ GitHub Repository  │ ──► │  Repository Ingestion  │ ──► │  Evidence Extraction  │
│ (Live API or Demo) │     │  (Files, PRs, Issues)  │     │  (AST, Manifests, CI) │
└────────────────────┘     └────────────────────────┘     └───────────────────────┘
                                                                      │
                                                                      ▼
┌────────────────────┐     ┌────────────────────────┐     ┌───────────────────────┐
│ What-If Simulation │ ◄── │  Deterministic Risks   │ ◄── │   Dependency Graph    │
│ (Impact & Paths)   │     │  (0–100 Scored Engine) │     │  (NetworkX DiGraph)   │
└────────────────────┘     └────────────────────────┘     └───────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Frontend Workspace: Interactive Graph, Risk Prioritization & Evidence Inspector │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Problem

1. **Invisible Cascading Impact**: A breaking schema change in a shared module can silently break downstream services, integration tests, and scheduled deployment targets without immediate detection during code review.
2. **Context Fragmentation**: Dependency information is split across package manifests (`package.json`, `requirements.txt`), git commit histories, issue trackers, CI/CD workflows, and API route definitions.
3. **AI Hallucination in Project Management**: Generative AI tools frequently invent non-existent relationships, misattribute commit authors, or hallucinate dependencies when summarizing repository health.
4. **Lack of Pre-Merge Impact Testing**: Teams discover integration bottlenecks and blocked critical paths *after* merging, rather than simulating delays and failures *before* deployment.

---

## Our Solution

DEADLOCK establishes a deterministic, evidence-backed pipeline that transforms repository metadata and source code into an actionable causal intelligence graph:

1. **Live GitHub Ingestion**: Ingests repository metadata, pull requests, issues, commit history, and source manifests directly via the GitHub REST API.
2. **Multi-Layer Dependency Intelligence**: Analyzes Python imports, JavaScript/TypeScript dependencies, API endpoints, test associations, and configuration schemas.
3. **Deterministic Graph Modeling**: Constructs a multi-layer directed graph (`NetworkX DiGraph`) linking developers, pull requests, issues, files, services, test suites, and milestone deadlines.
4. **Evidence-Based Risk Detection**: Identifies critical-path bottlenecks, unreviewed high-risk PRs, single-developer workload bottlenecks, and deadline slippages with explicit provenance references.
5. **Interactive What-If Simulation**: Computes downstream impact sets for hypothetical PR review delays, dependency outages, or breaking changes without modifying repository state.

---

## Core Features

- **Real GitHub Repository Analysis**: Direct live repository ingestion with rate-limit monitoring and multi-branch support.
- **Evidence-First Dependency Graph**: Nodes and edges represent real artifacts (PRs, issues, files, modules, endpoints, deployments) with strict provenance.
- **Failure Propagation Engine**: Computes exact causal reachability chains from root causes to affected downstream artifacts.
- **Deterministic Risk Scoring**: Explainable `0–100` risk prioritization scores calculated from deterministic factors rather than generative guesswork.
- **What-If Impact Simulation**: Interactive simulation engine testing scenarios (e.g., "+3 day review delay on PR #X" or "External Payment API outage"). Downstream nodes are accurately classified into `affected`, `unaffected`, and `unknown` sets (the root node is excluded from downstream counts).
- **Multi-Repository & Combined Workspace**: Manage multiple repositories inside a single unified workspace.
- **Evidence-Backed Cross-Repository Relationships**: Links separate repositories *only* when explicit evidence exists (shared package dependencies, client/server API contracts, explicit service URLs, or cross-repo references).
- **Repository Isolation**: Repositories are stored and analyzed independently in local SQLite storage; deleting a repository removes it strictly from local state without touching GitHub.
- **Direct vs. Inferred Edge Provenance**: Every graph edge clearly identifies whether it was established via direct reference (e.g., issue keyword `Fixes #42`) or deterministic inference (e.g., AST import path match).
- **Rate-Limit Resilience**: Surfaces HTTP 429 status and reset windows gracefully; never silently substitutes fake or demo data upon live API errors.
- **Strict Demo Mode Separation**: Fully offline, deterministic demo dataset clearly marked as simulated, completely isolated from live GitHub runs.

---

## How DEADLOCK Works

![DEADLOCK Dependency Graph Topology](assets/WhatsApp%20Image%202026-09-19%20at%2015.21.52.jpeg)

```
                        ┌──────────────────────────────┐
                        │     GitHub REST API          │
                        └──────────────┬───────────────┘
                                       │ (Async HTTPX Ingestion)
                                       ▼
                        ┌──────────────────────────────┐
                        │   Project Model Normalizer   │
                        └──────────────┬───────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│ Manifest & AST Parser │  │  PR & Issue Linker    │  │ API / Schema Analyzer │
│ (Python / JS / TS)    │  │  (Regex & Metadata)   │  │ (Endpoints & Clients) │
└───────────┬───────────┘  └───────────┬───────────┘  └───────────┬───────────┘
            └──────────────────────────┼──────────────────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │   Evidence Engine            │
                        │   (Direct vs Inferred Rules) │
                        └──────────────┬───────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │   Graph Engine (NetworkX)    │
                        │   (Directed Causal Graph)    │
                        └──────────────┬───────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│  Deterministic Risk Engine   │              │  What-If Simulation Engine   │
│  (Bottlenecks & Deadlines)   │              │  (Downstream Propagation)    │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               └───────────────────────┬─────────────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │    FastAPI REST Backend      │
                        └──────────────┬───────────────┘
                                       │ (JSON over HTTP)
                                       ▼
                        ┌──────────────────────────────┐
                        │  Next.js 16 + React Flow UI  │
                        │  (Workspace & Visualizer)    │
                        └──────────────────────────────┘
```

> **Source of Truth Principle**: The directed dependency graph and deterministic rule engines are the absolute source of truth in DEADLOCK. Optional LLM layers are restricted to summarizing verified graph evidence and cannot inject unproven relationships.

---

## Evidence-First Intelligence

![DEADLOCK Evidence-First Risk Detail & Provenance Inspector](assets/WhatsApp%20Image%202026-09-19%20at%2015.20.56.jpeg)

A core design principle of DEADLOCK is **zero tolerance for synthetic hallucinations in project state**:

| Entity | What DEADLOCK Uses | What DEADLOCK NEVER Does |
| :--- | :--- | :--- |
| **Developers** | Real GitHub commit authors, PR creators, assignees | Never invents fictional team members |
| **Dependencies** | Declared manifests (`package.json`, `requirements.txt`, imports) | Never assumes dependencies based solely on project name similarity |
| **Pull Requests / Issues** | Real GitHub API entity IDs, timestamps, review states | Never fakes PRs or review statuses |
| **Graph Edges** | Direct links (PR closing issues) & inferred AST/contract links | Never creates unverified connections |
| **Deadlines & Milestones** | GitHub milestones or explicitly configured release targets | Never invents artificial project deadlines |

### Direct vs. Inferred Relationships

- **Direct Relationships (`provenance: direct`)**: Explicitly declared in repository data (e.g., PR `#104` has body `Closes #88`, or `package.json` lists `"express": "^4.19.0"`).
- **Inferred Relationships (`provenance: inferred`)**: Derived through static analysis heuristics (e.g., `services/auth.py` imports `db/session.py`, connecting endpoint `POST /login` to database migrations). Every inferred edge records the rule name that generated it.
- **Unknown Status (`UNKNOWN / NO EVIDENCE`)**: If evidence is missing, DEADLOCK marks the state as `UNKNOWN` rather than guessing.

---

## Failure Propagation Example

Consider a breaking parameter change in a core utility module:

```
[ Pull Request #142: Refactor Token Verification ]
                     │ (modifies)
                     ▼
       [ lib/auth/jwt_verifier.py ]
                     │ (imported by)
                     ▼
          [ api/routes/users.py ]
                     │ (exposes endpoint)
                     ▼
            [ POST /api/v1/login ]
                     │ (consumed by)
                     ▼
          [ frontend-web-client ]
                     │ (tested by)
                     ▼
       [ test_user_authentication_e2e ]
                     │ (blocks target)
                     ▼
          [ Staging Deployment v2.4 ]
```

When a reviewer requests changes on `PR #142` or unit tests fail in `jwt_verifier.py`:
1. DEADLOCK traverses the dependency graph downstream.
2. It tags `POST /api/v1/login`, `frontend-web-client`, `test_user_authentication_e2e`, and `Staging Deployment v2.4` as **AFFECTED**.
3. It provides the exact evidence chain: file import line numbers, route definitions, and PR review statuses.

---

## Multi-Repository & Combined Workspace

DEADLOCK allows engineering organizations to inspect multi-service architectures across independent repositories:

![DEADLOCK Combined Workspace & Cross-Repository Analysis](assets/WhatsApp%20Image%202026-09-19%20at%2015.20.01.jpeg)

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     Repository A: backend-api   │       │    Repository B: web-frontend   │
│  - FastAPI endpoints            │       │  - React / Next.js client       │
│  - requirements.txt manifests   │       │  - package.json manifests       │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │    Combined Workspace     │
                        │    Cross-Repo Analysis    │
                        └─────────────┬─────────────┘
                                      │
            (Cross-repo connections created ONLY when evidence exists)
                                      ▼
               [ Evidence: API Client calls 'POST /api/v1/users' ]
               [ Evidence: Shared Schema package 'common-types'   ]
```

Cross-repository edges are created **only** when evidence is verified via:
- Shared package dependencies / versions
- Matched API routes and consumer HTTP clients
- Shared data contract schemas / protobuf definitions
- Explicit service base URL configurations
- Inter-repository CI/CD workflow dependencies

---

## What-If Simulation

The What-If Engine allows tech leads and release managers to test hypothetical risks safely:

![DEADLOCK What-If Failure Propagation Studio](assets/WhatsApp%20Image%202026-09-19%20at%2015.22.43.jpeg)

```
Simulation Request:
  Scenario: "PR #89 review delayed by 4 business days"
  Target Node: pull_request:89
  Delay: 4 days

Propagation Output:
  ├── Root Cause: pull_request:89 (Excluded from downstream count)
  ├── Affected Downstream Nodes: 6
  │   ├── issue:45 (User Profile API Migration)
  │   ├── service:profile-service
  │   ├── test:e2e-profile-flow
  │   ├── deployment:staging-us-east
  │   └── milestone:v1.4.0-release (DEADLINE AT RISK)
  ├── Unaffected Nodes: 38
  ├── Risk Score Delta: 42 → 88 (+46 CRITICAL)
  └── Recommended Mitigation: "Reassign review of PR #89 to secondary code-owner or decouple profile-service from milestone v1.4.0."
```

---

## System Architecture

```
+-------------------------------------------------------------------------------+
|                               DEADLOCK SYSTEM                                 |
+-------------------------------------------------------------------------------+
|                                                                               |
|  FRONTEND LAYER (Next.js 16 / React 19 / Tailwind CSS / React Flow)           |
|  +-------------------------------------------------------------------------+  |
|  |  Workspace Dashboard  |  Interactive Graph  |  What-If Simulator  | UI  |  |
|  +-------------------------------------------------------------------------+  |
|                                       | (REST / JSON)                         |
|                                       v                                       |
|  BACKEND API LAYER (FastAPI / Uvicorn / Pydantic v2)                          |
|  +-------------------------------------------------------------------------+  |
|  | /api/workspace | /api/projects | /api/risks | /api/graph | /api/simulate|  |
|  +-------------------------------------------------------------------------+  |
|          |                                              |                     |
|          v                                              v                     |
|  INGESTION & INTELLIGENCE                   GRAPH & RISK ENGINE               |
|  +------------------------------------+     +-------------------------------+ |
|  | - GitHub Async Client (httpx)      |     | - NetworkX Directed Graph     | |
|  | - Python / JS AST Analyzers        | --> | - Deterministic Risk Detector | |
|  | - Manifest & Route Analyzers       |     | - Failure Propagation Engine  | |
|  | - Rate-Limit & Caching Layer       |     | - Causal Verifier Agent       | |
|  +------------------------------------+     +-------------------------------+ |
|          |                                              |                     |
|          +----------------------+-----------------------+                     |
|                                 v                                             |
|  PERSISTENCE & RUNTIME STORAGE (SQLite / deadlock.db)                         |
|  +-------------------------------------------------------------------------+  |
|  |  Projects Metadata  |  Workspace State  |  Cached Graphs  | Meta Logs   |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

---

## Tech Stack

### Frontend
- **Framework**: Next.js 16.3 (App Router, Server & Client Components)
- **Library**: React 19.2, React DOM 19.2
- **Graph Visualization**: React Flow (`@xyflow/react` / `reactflow`)
- **Styling**: Tailwind CSS v4, PostCSS
- **Icons**: Lucide React
- **Language**: TypeScript 5

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Server**: Uvicorn (ASGI)
- **Graph Engine**: NetworkX
- **Data Validation & Settings**: Pydantic v2, Pydantic-Settings
- **HTTP Client**: HTTPX (Asynchronous GitHub API integration)
- **Database / Storage**: SQLite (`deadlock.db`) via custom repository storage layer
- **Testing**: Pytest, Pytest-Asyncio

### Optional & Integrations
- **AI / LLM Layer**: Ollama (`llama3.2` / local models) for claim verification and narrative explanations
- **Webhook Testing**: Beeceptor proxy integration support
- **Automation**: n8n-compatible webhook dispatchers

---

## Project Structure

```
DEADLOCK/
├── app/                              # Next.js App Router (Frontend)
│   ├── (dashboard)/                  # Main dashboard workspace view
│   ├── graph/                        # Full-screen interactive dependency graph
│   ├── health/                       # System health & backend connectivity
│   ├── investigate/                  # Deep-dive risk investigation views
│   ├── projects/                     # Repository manager & sync interface
│   ├── risks/                        # Prioritized risk feed & breakdown
│   ├── simulate/                     # What-If simulation studio
│   ├── globals.css                   # Global styles & Tailwind configuration
│   ├── layout.tsx                    # Root layout with sidebar navigation
│   └── page.tsx                      # Landing redirect & entry point
├── backend/                          # FastAPI Application (Backend)
│   ├── app/
│   │   ├── agents/                   # Verifier & reasoning agents
│   │   ├── api/                      # FastAPI route controllers
│   │   │   ├── routes_demo.py        # Offline demo mode endpoints
│   │   │   ├── routes_graph.py       # Graph serialization endpoints
│   │   │   ├── routes_investigation.py # Deep analysis endpoints
│   │   │   ├── routes_projects.py    # Repository sync & status
│   │   │   ├── routes_risks.py       # Deterministic risk endpoints
│   │   │   ├── routes_simulation.py  # What-If simulation routes
│   │   │   └── routes_workspace.py   # Multi-repo workspace management
│   │   ├── config/                   # Pydantic Settings & environment loader
│   │   ├── database/                 # SQLite database & repository storage
│   │   ├── dependency_intelligence/  # AST parsers (Python, JS/TS, manifests, routes)
│   │   ├── graph/                    # NetworkX graph builder & path validators
│   │   ├── ingestion/                # GitHub client, normalizers, dataset loader
│   │   ├── models/                   # Pydantic models (Project, Risk, Graph, Node)
│   │   ├── risk_engine/              # Deterministic risk detectors & scoring
│   │   ├── simulation/               # Propagation policy & What-If engine
│   │   └── main.py                   # FastAPI app instance, CORS & lifecycle
│   ├── data/                         # Canonical demo datasets
│   ├── tests/                        # Pytest suite (Graph, Risk, API, Simulation)
│   ├── requirements.txt              # Backend Python dependencies
│   ├── .env.example                  # Environment variable template
│   └── deadlock.db                   # Local SQLite database
├── components/                       # Reusable React UI components
│   ├── dashboard/                    # Metric cards, repo status widgets
│   ├── graph/                        # React Flow node visualizers, edge formatters
│   ├── layout/                       # Sidebar, header, navigation shell
│   ├── risks/                        # Risk severity tags, causal chain drawers
│   └── ui/                           # Base UI primitives (buttons, badges, inputs)
├── lib/                              # Frontend utilities & API client SDK
├── package.json                      # Frontend dependencies & scripts
├── tsconfig.json                     # TypeScript compiler configuration
└── README.md                         # Project documentation
```

---

## Running Locally

### Prerequisites
- **Node.js**: `v20.0+` and `npm`
- **Python**: `v3.10+` and `pip` (or active virtual environment)

---

### 1. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Start the FastAPI server
python -m uvicorn app.main:app --reload --port 8000
```

The backend server will start at `http://localhost:8000`. Verify via `http://localhost:8000/health`.

---

### 2. Frontend Setup

In a new terminal window:

```bash
# Navigate to the project root
cd DEADLOCK

# Install frontend dependencies
npm install

# Start the Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### 3. Running Automated Tests

```bash
# Run backend test suite
cd backend
python -m pytest tests -q

# Run frontend linter and build check
npm run lint
npm run build
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`. **All sensitive tokens remain strictly on the backend and are never exposed to the client.**

| Variable | Required | Default | Purpose |
| :--- | :--- | :--- | :--- |
| `GITHUB_TOKEN` | Optional | `""` | GitHub Personal Access Token for higher rate limits (5,000 req/hr vs 60 req/hr unauthenticated) |
| `GITHUB_OWNER` | Optional | `""` | Default GitHub owner for sync routes |
| `GITHUB_REPO` | Optional | `""` | Default GitHub repo for sync routes |
| `DEADLOCK_MODE` | Optional | `demo` | `demo` (offline seeded mode) or `live` (GitHub REST mode) |
| `FRONTEND_ORIGINS` | Optional | `http://localhost:3000` | Allowed CORS origins for the FastAPI server |
| `DATABASE_URL` | Optional | `sqlite:///./deadlock.db` | Local SQLite database file location |
| `OLLAMA_URL` | Optional | `http://localhost:11434` | URL for local Ollama LLM verification server |
| `OLLAMA_MODEL` | Optional | `llama3.2` | Model tag for natural language claim explanation |
| `BEECEPTOR_BASE_URL` | Optional | `https://deadlock.proxy.beeceptor.com` | External mock proxy for simulated webhook outage tests |
| `N8N_WEBHOOK_SECRET`| Optional | `""` | Optional secret verified in `X-Deadlock-Secret` header for webhook ingestion |

> [!IMPORTANT]
> Never commit real GitHub Personal Access Tokens or API keys to version control. The application functions completely out-of-the-box in offline Demo Mode without any tokens.

---

## Demo Mode vs. Live GitHub Mode

| Mode | Trigger | Data Source | Behavior on Rate Limit / Network Loss |
| :--- | :--- | :--- | :--- |
| **Live GitHub** | Enter repository URL (e.g. `facebook/react`) | Live GitHub REST API v3 + AST Parser | Returns explicit `HTTP 429 Rate Limited` or `HTTP 502`; **never** silently substitutes fake data. |
| **Demo Mode** | Click "Load Demo Project" or use `/api/projects/demo` | Explicit Canonical Test Dataset | Runs fully offline with zero internet access, demonstrating full graph propagation on known causal chains. |

---

## Example User Workflow

1. **Add Repository**: Enter `owner/repo` or a full GitHub URL in the Workspace manager.
2. **Analyze & Ingest**: DEADLOCK fetches issues, PRs, commit records, and dependency manifests.
3. **Inspect Dependency Graph**: Navigate the multi-layer graph visualizer to inspect relationships across PRs, source files, and milestones.
4. **Review Prioritized Risks**: Examine the risk feed sorted by deterministic severity (`CRITICAL`, `HIGH`, `MEDIUM`). Inspect exact causal chains and evidence lines.
5. **Manage Multi-Repo Workspace**: Add a secondary repository (e.g., frontend client and backend API). Observe verified cross-repository contract edges.
6. **Execute What-If Simulation**: Select a PR or module, specify a simulated delay or outage, and inspect which downstream services and deadlines are impacted.
7. **Verify Evidence**: Review the exact commit hashes, file lines, and review comments backing every risk before making engineering decisions.

---

## Why DEADLOCK Is Different

| Capability | Standard AI Assistants | Project Management Boards | DEADLOCK |
| :--- | :--- | :--- | :--- |
| **Primary Question** | "What code should I write?" | "What status is this ticket in?" | **"If this changes/fails, what breaks downstream and WHY?"** |
| **Dependency Depth** | Single-file or local repo context | Manual epic/subtask links only | **Multi-hop AST, manifest, PR, issue, CI/CD, and cross-repo graph** |
| **Risk Detection** | Generative suggestion (may hallucinate) | Static deadline rules | **Deterministic graph analysis with verifiable provenance** |
| **What-If Simulation** | None | Manual timeline estimation | **Automated failure propagation engine** |
| **Evidence Guarantee** | Unverified text generation | None | **Zero synthetic hallucinations; explicit UNKNOWN state** |

---

## Reliability & Data Integrity

- **Strict Repository Isolation**: Each repository maintains isolated graph storage in SQLite.
- **Explainable Scoring**: Risk scores are deterministic calculations based on blocking review counts, path lengths to deadlines, and single-developer load percentages.
- **Fail-Safe GitHub Handling**: When GitHub rate limits are exhausted, DEADLOCK surfaces exact reset times instead of failing silently.
- **Safe Workspace Removal**: Removing a repository from DEADLOCK deletes local index cache only; it **never** makes write operations against your GitHub repository.

---

## Future Scope

- [ ] **Extended Language AST Analyzers**: Native support for Go, Rust, Java, and C# semantic import extractors.
- [ ] **CI/CD Pipeline Intelligence**: Direct ingestion of GitHub Actions workflow telemetry and test failure history.
- [ ] **Runtime Deployment Topology**: Ingestion of Kubernetes manifests and Terraform state files for live infrastructure mapping.
- [ ] **Historical Risk Trends**: Time-series tracking of project risk velocity across release sprints.
- [ ] **GitLab & Bitbucket Support**: Broader VCS provider integrations beyond GitHub.

---

## Team

- **Samriddha** ([@Samriddha02](https://github.com/Samriddha02))
- **Aritra** ([@Aritra-DSU](https://github.com/Aritra-DSU))
- **Bivob** ([@Bivobrocker](https://github.com/Bivobrocker))

---

## License

License: To be added.
