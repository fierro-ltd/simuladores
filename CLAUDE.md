# CLAUDE.md — Simuladores

## What This Project Is

Domain-locked, Temporal-orchestrated agent system that wraps existing AI services. Inspired by [Los Simuladores](https://es.wikipedia.org/wiki/Los_simuladores), each operativo is executed by a four-agent brigada. Each instance resolves one class of task for one domain. DCE (Document Compliance Engine) is the reference domain; IDP (Intelligent Document Processing) is the second connected domain.

Simuladores adds intelligent planning (Santos), document investigation (Medina), unified execution (Lamponne), and synthesis (Ravenna) around existing backend services — without modifying them.

## Tech Stack

- **Python 3.11+** — core language
- **Temporal.io** — workflow orchestration (the only orchestration layer, no LangChain/AutoGen)
- **Anthropic Python SDK (Vertex AI)** — `anthropic[vertex]` via Google Vertex AI. Prompt caching, compaction API, cache hit monitoring all work through Vertex.
- **PostgreSQL + pgvector** — semantic memory (cross-job pattern storage)
- **Docker** — sandbox for code execution (rootless, no network, ephemeral)
- **FastAPI** — gateway API

## Architecture Invariants

These are non-negotiable. Do not introduce code that violates them:

1. **Prompt layer ordering (Thariq's Law)**: `prompt/builder.py` assembles messages in strict order — system (L0), domain (L1), semantic (L3), session (L2), working (L4). Static first, dynamic last. `PromptOrderViolation` on breach. Cache break = CI failure.

2. **Domain isolation by construction**: A DCE worker only has DCE tools registered. Cross-domain access is impossible because the tools don't exist in the worker process, not because of configuration.

3. **Security by architecture**: Injection resistance, credential isolation, and domain lockdown are enforced in code, never by prompt alone. The LLM cannot override the tool policy chain.

4. **Domain files READ-ONLY at runtime**: DCE.md and other domain memory files are never written by agents. Human-approved Temporal signal only.

5. **Always delivers**: Auto-correction loops run to max 3 attempts, then deliver with NEEDS_REVIEW flag. No silent failures.

## Key Directories

```
core/         Base classes — Operativo, permissions, registry
prompt/       MOST CRITICAL — prompt assembly, injection guard, compaction
memory/       Five-layer memory: domain, session, semantic stores
agents/       Santos, Medina, Lamponne, Ravenna implementations
sandbox/      Docker v1 backend, Monty v2 stub, stable SandboxBackend interface
domains/dce/  DCE domain: DCE.md, tools manifest, worker, operativo
domains/idp/  IDP domain: IDP.md, tools manifest, worker, operativo
workflows/    Temporal workflow definitions
activities/   Temporal activity implementations (where PolicyChain runs)
storage/      StorageBackend protocol + local/GCS implementations
gateway/      API intake and dispatch
tests/        cache_tests (CI-critical), injection_tests, fixtures, integration
```

## Agent Model

| Agent | Code | Model | Role |
|-------|------|-------|------|
| Santos | `agents/santos.py` | Opus 4.6 | Plans, QA review, auto-correction. No tool calls during planning. |
| Medina | `agents/medina.py` | Opus 4.6 | Document reading, injection scanning. Opus mandatory for injection resistance. |
| Lamponne | `agents/lamponne.py` | Sonnet 4.6 | Executes via discover_api/execute_api. Inputs always controlled. |
| Ravenna | `agents/ravenna.py` | Sonnet 4.6 | Synthesizes output. Permission-gated delivery. |

Model assignments are hardcoded in code, not configurable.

## Running Locally

```bash
docker compose up                              # Temporal + PostgreSQL + pgvector
python -m agent_harness.workers.dce        # DCE worker
python -m agent_harness.gateway            # API gateway
```

Uses `LocalStorageBackend` (filesystem). No cloud credentials needed for dev/testing.

## Testing

- `tests/cache_tests/` — prompt layer ordering validation. **CI must fail on any cache-breaking change.**
- `tests/injection_tests/` — 10+ synthetic poisoned documents. All must be flagged by Medina.
- `tests/fixtures/` — 10 sample compliance PDFs + product photos from dce-data.
- `tests/integration/` — end-to-end operativo tests per domain.

Run: `pytest tests/`

## Conventions

- **Operativo** = a single job/task processed by the harness (the core concept)
- Internal agent names (Santos, Medina, Lamponne, Ravenna) used in code and system prompts
- External names (Orchestrator, Investigator, Executor, Synthesizer) for API docs and compliance
- PROGRESS.md field reports: 3-5 sentences per phase, never raw tool output dumps
- PLAN.md: structured JSON execution plan, written by Santos in Phase 1

## Design Documents

- `docs/ARCHITECTURE.md` — full architecture design
- `docs/DATA_FLOW.md` — data flow documentation
- `docs/VISION.md` — project vision

## Related Systems

- **dispatch** — email routing service that will send jobs to Simuladores
- **DCE Backend** (fierro-ltd/genai-document-compliance) — existing DCE validation system; Simuladores wraps its 20 Temporal activities
- **IDP Platform** — document extraction platform; Simuladores wraps its 19 REST endpoints
- **Healthcare AI Suite** (fierro-ltd/healthcare-ai-suite) — future domain target
