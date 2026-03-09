# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.8.0] - 2026-02-23

Sprint 23: Citation Matrix Excel Export + Santos Parser Resilience

### Added
- Citation matrix Excel exporter (`export/citation_matrix_excel.py`) — generates `.xlsx` matching DCE Backend format with Santos-QA review columns.
- `--output-xlsx` flag in e2e script to copy citation matrix Excel to user-specified path.
- Santos plan JSON parser resilience — handles trailing commas, `//` comments, surrounding prose, with fallback to default DCE plan.

### Changed
- E2E fast mode timeouts bumped: `investigate_timeout_seconds` and `qa_timeout_seconds` 120→300s (DCE Backend needs ~3 min).

### Fixed
- Santos plan parser no longer crashes on malformed JSON from Sonnet 4.6 (graceful fallback instead of ValueError).
- `//` comment stripping regex anchored to line-start to avoid corrupting URLs in params.

## [1.7.0] - 2026-02-23

Sprint 22: DCE Citation Completeness + Web Verification

### Added
- Deterministic DCE citation registry with canonical normalization, alias handling, and citation-type semantics.
- DCE product profile extraction (`extract_product_profile`) for age/category-driven citation applicability.
- Citation completeness report generation with required/covered/missing/invalid/non-operational categories.
- GCP-native DCE web verification activity (`cpc_web_verify`) using Gemini with Google Search grounding when ambiguity is detected.
- QA citation classification categories:
  - `MISSING_CPC_CITATION`
  - `INVALID_CPC_CITATION`
  - `NON_CPC_OPERATIONAL_REQUIREMENT`
  - `AMBIGUOUS_REQUIRES_REVIEW`

### Changed
- DCE workflow now computes citation completeness before QA and conditionally runs web verification.
- QA and synthesis activities now receive citation completeness + web verification evidence context.
- Structured output now includes web verification evidence and recommendation flags when applicable.
- Bumped package and gateway version to 1.7.0.

## [1.6.0] - 2026-02-22

Sprint 21: DCE Runtime Optimization Pass

### Added
- DCE e2e fast-mode control (`e2e_fast_mode`) for deterministic, input-driven runtime reductions
- `--e2e-fast-mode` flag in `scripts/run_dce_e2e.py`

### Changed
- DCE workflow now applies per-run runtime config and skips post-job learning in e2e fast mode
- QA retry loop now re-executes only when blocking checks are auto-correctable
- Gemini vision extraction now processes pages in concurrent batches
- DCE Backend polling checks extraction earlier and uses faster initial poll cadence
- Domain memory and memory-recall initialization optimized to reduce repeated overhead
- Bumped package and gateway version to 1.6.0

## [1.4.0] - 2026-02-22

Sprint 20: DCE Production Readiness (PRs #39, #40)

### Added
- Real PDF text extraction via `pdfplumber` with local fallback for DCE documents
- Heuristic DCE field extraction using regex parser
- `extract_pdf_text` wired to DCE Backend Temporal activities via REST API
- `cortex_generate_bulletin` activity implemented and registered in DCE worker
- End-to-end integration test with real compliance PDFs
- `httpx` dependency for DCE Backend REST API communication

### Changed
- Replaced PDF extraction and DCE parsing placeholders with real implementations
- Bumped version to 1.4.0

## [1.3.0] - 2026-02-22

Sprint 19: Vertex AI Migration (PRs #37, #38)

### Added
- `AsyncAnthropicVertex` client replacing direct `AsyncAnthropic`
- `VertexConfig` with `project_id` and `region` fields
- Google Cloud ADC (Application Default Credentials) support — no API key needed

### Changed
- Migrated LLM client from Anthropic API to Vertex AI
- Replaced `AnthropicConfig` with `VertexConfig` throughout codebase
- Updated all documentation references from direct Anthropic API to Vertex AI
- Aligned gateway version with pyproject.toml (1.3.0)

### Removed
- Direct Anthropic API key requirement

## [1.2.0] - 2026-02-22

Sprints 16-18: Production Hardening (PRs #31-#35)

### Added
- GCS storage backend (`GCSStorageBackend`) for production deployments (PR #31)
- Gateway authentication, rate limiting, and audit logging (PR #32)
- Error envelope response format for gateway API
- Cache hit rate monitor per domain and agent (PR #33)
- Temporal connectivity check in health endpoint (PR #33)
- Callback delivery service with retry logic (PR #34)
- Callback delivery activity wired into DCE workflow
- Cache stats API endpoint (PR #33)
- Graceful shutdown with signal handling for workers (PR #34)
- Semantic pattern injection from memory recall into all DCE agents (PR #35)
- Cache hit rate recording from all DCE activities (PR #35)

### Changed
- `post_job_learn` activity wired to `extract_patterns` for real pattern extraction (PR #35)
- Memory recall and bulletin store use factory functions (PR #35)
- Callback delivery integrated into DCE workflow end-of-job (PR #35)

## [1.1.0] - 2026-02-22

Sprints 14-15: Multi-Domain Expansion (PRs #29, Sprint 15)

### Added
- Cortex Bulletin cross-session memory summaries (PR #28)
- IDP verification checklist and Temporal workflow (PR #29)
- Complete HAS domain implementation with tools manifest and worker
- Multi-domain gateway routing for DCE, HAS, and IDP

### Changed
- Gateway updated to dispatch to multiple domain workers

## [1.0.0] - 2026-02-22

Sprints 7-13: Runtime Implementation (PRs #17-#28)

### Added
- `AnthropicClient` with `ToolHandler` multi-turn execution loop (Sprint 7, PR #17)
- `TokenUsage`, `MessageResult`, `ToolCall` SDK-aligned types (Sprint 7)
- Santos `plan()` and `SantosQAReviewer.review()` executors (Sprint 7)
- `MedinaInvestigator`, `LamponneExecutor`, `RavennaSynthesizer` executors (Sprint 7)
- Activity factory and all 6 Temporal activity implementations with `@activity.defn` (Sprint 8)
- `@workflow.defn` on `CPCOperativoWorkflow` with Phase 0-6 run and QA retry loop (Sprint 8)
- DCE Temporal worker process (Sprint 9, PR #17)
- FastAPI gateway with health endpoints (Sprint 9, PR #17)
- Docker Compose stack for local development (Sprint 9)
- CI workflow, `.dockerignore`, `.env.example` (PR #19)
- Deterministic verification checklist for QA review (PR #20)
- `ResourceEditTracker` loop detection to prevent doom loops (PR #21)
- PDF metadata injection scanning in Medina's guard (PR #22)
- Per-phase reasoning effort configuration (PR #23)
- PostgreSQL migration for memory graph with hybrid search (PR #24)
- Typed memory graph with `InMemoryGraphStore` and recall layer (PR #26)
- Post-job pattern extraction and Voyage AI embedding client (PR #25)
- `OperativoWorkspace` for per-operativo directory isolation (PR #27)
- Workspace mounts wired into `DockerSandboxBackend` (PR #27)

### Fixed
- Critical runtime gaps: `@activity.defn` decorators, Ravenna handlers, exports, `SandboxRouter` (PR #18)
- Merge conflict between checklist and reasoning effort tests

## [0.6.0] - 2026-02-22

Sprint 6: Production Readiness (PRs #15, #16)

### Added
- Structured logging with correlation IDs (PR #15)
- Metrics collection and benchmark harness (PR #15)
- Security test suite with injection attack scenarios (PR #16)
- Temporal search attributes for operativo tracking (PR #16)
- Production configuration templates (PR #16)

## [0.5.0] - 2026-02-22

Sprint 5: Multi-Domain Foundation (PRs #12-#14)

### Added
- HAS domain stub with domain memory file and tools manifest (PR #12)
- IDP domain stub with domain memory file (PR #12)
- Email intake endpoint for `dispatch` integration (PR #13)
- Domain router for automatic domain detection and dispatch (PR #13)
- Brigada B `SimpleOrchestrator` for lightweight task routing (PR #13)
- Multi-domain routing in gateway with domain package exports (PR #14)

## [0.4.0] - 2026-02-22

Sprint 4: Synthesis and Compaction (PRs #9-#11)

### Added
- Ravenna synthesizer agent with permission-gated delivery (PR #9)
- Activity types for synthesis phase (PR #9)
- Compaction client wrapping Anthropic compaction API (PR #10)
- Session bridge fallback for compaction (PR #10)
- Heartbeat monitor for long-running activities (PR #10)
- Phase 5 (synthesis) wired into workflow builder (PR #11)

## [0.3.0] - 2026-02-22

Sprint 3: Investigation and QA (PRs #6-#8)

### Added
- Medina investigator agent for document reading and injection scanning (PR #6)
- Investigation activity types (PR #6)
- QA review types with severity levels (PR #7)
- Post-job learning activity types for pattern capture (PR #7)
- Full operativo lifecycle implementation covering Phases 0-6 (PR #8)

## [0.2.0] - 2026-02-21

Sprint 2: Planning and Execution (PRs #3-#5)

### Added
- `BaseAgent` abstract class with `AgentConfig` and `AGENT_MODELS` registry (PR #3)
- Santos planner agent with JSON plan parser (PR #3)
- `PlannerInput` and `PlannerOutput` activity types (PR #3)
- `AgentLoopInput` and `AgentLoopOutput` activity types (PR #3)
- Lamponne executor agent with system identity and tool schemas (PR #4)
- DCE tools manifest with 28 operations across 5 categories (PR #4)
- DCE operativo input and output frozen dataclasses (PR #4)
- `ToolExecutor` wrapping `PolicyChain` for permission checks (PR #4)
- `CPCWorkflow` with Phases 0-3 for operativo orchestration (PR #5)
- Gateway dispatch for DCE operativo intake (PR #5)

## [0.1.0] - 2026-02-21

Sprint 1: Foundation (PRs #1, #2)

### Added
- Project scaffolding with `pyproject.toml` and `docker-compose.yml`
- `PromptBuilder` enforcing Thariq's Law (L0-L4 prompt layer ordering)
- Medina injection scanner for prompt injection detection
- `CompactionConfig` with threshold checks
- `SandboxRequest`/`SandboxResult` types, `SandboxRouter`, and `DockerBackend`
- Core types: `Phase`, `OperativoStatus`, `Severity`, `QAIssue`, `OperativoResult`
- Plan types and `PolicyChain` permission enforcement
- `OperativoRegistry` for domain-to-queue mapping
- `StorageBackend` protocol with `LocalStorageBackend` implementation
- Read-only `DomainStore` for domain memory files
- `SessionStore` for per-operativo plan and progress tracking
- In-memory `SemanticStore` stub for pattern retrieval
- DCE domain memory file (`DCE.md`)
