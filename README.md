# DEADLOCK

DEADLOCK is an evidence-first project failure-propagation tool. It answers: if a pull request, task, or external dependency is delayed or fails, which project work is affected next, why, and what should the team do?

It is not a general AI coding assistant or a probability model. The MVP uses a deterministic NetworkX dependency graph; its Risk Score is an explainable `0–100` prioritization score, not a predicted probability. The optional agent layer summarizes and verifies claims from graph evidence only.

## Architecture

`GitHub / demo data / webhook → normalization → dependency graph → deterministic risk engine → evidence + verifier → dashboard and what-if simulation`

The same graph powers risk detection, graph inspection, simulations, dependency-failure events, and n8n-compatible webhooks.

## Run locally

Backend (PowerShell):

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend (another terminal):

```powershell
npm run dev
```

Open http://localhost:3000. `NEXT_PUBLIC_API_URL` defaults to `http://127.0.0.1:8000`.

## Demo mode

Demo mode needs no internet, API keys, Beeceptor, n8n, or LLM. It serves the explicitly labelled **CampusConnect DEMO PROJECT** and an explicit causal chain:

`PR-47 → Authentication API → Integration testing → Deployment → Friday Production Release → Client Demo`

The What If action sends a controlled three-day delay for `PR-47` to the backend and displays the calculated downstream set. `POST /api/dependencies/test-failure` also creates a **CONTROLLED DEMO SIMULATION** when Beeceptor is not configured; it never claims an external outage occurred.

## Configuration

Copy `backend/.env.example` to `backend/.env`. GitHub credentials are optional. The supplied Beeceptor endpoint is prefilled as `BEECEPTOR_BASE_URL=https://deadlock.proxy.beeceptor.com`; the backend posts a controlled event to that URL and reports delivery status before doing its local graph propagation. Configure `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO` for the existing GitHub sync endpoint. `N8N_WEBHOOK_SECRET`, when set, is required in the `X-Deadlock-Secret` header for webhook events. Secrets remain backend-only.

## API

- `GET /health`
- `GET /api/projects/demo`, `GET /api/projects/current`, `POST /api/projects/analyze`
- `GET /api/risks`, `GET /api/risks/{risk_id}`, `GET /api/graph`
- `POST /api/simulate`
- `POST /api/dependencies/test-failure`
- `POST /api/webhooks/events`
- `GET /api/evidence/{source_id}`

The legacy GitHub sync endpoints remain available under `/api/projects/{owner}/{repo}` for compatibility.

## Verification

```powershell
..\.venv\Scripts\python.exe -m pytest backend\tests -q
npm run lint
npm run build
```

## Limitations

GitHub exposes only the relationships present in its API/text; inferred edges must be marked with their rule. The included CampusConnect chain is an explicit, controlled demo scenario. Beeceptor and n8n are optional integrations, not required services.
