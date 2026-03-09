# Data Flow — Agent Harness (DCE Domain)

How data moves through the Agent Harness during a DCE operativo, from API intake to final result delivery.

> Diagrams use [Mermaid](https://mermaid.js.org/) syntax and render natively on GitHub.

> Latest workflow update: after Medina/Vision extraction, the DCE flow computes a deterministic citation completeness report and conditionally runs a GCP-native web verification step before QA.

---

## 1. End-to-End Flow

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as Gateway (FastAPI)
    participant Temporal
    participant Santos as Santos (Opus 4.6)
    participant Medina as Medina (Opus 4.6)
    participant Lamponne as Lamponne (Sonnet 4.6)
    participant Ravenna as Ravenna (Sonnet 4.6)
    participant CPCRobot as DCE Backend API
    participant Memory as Memory (pgvector)

    Client->>Gateway: POST /operativo/dce
    Gateway->>Gateway: Auth + Rate Limit + Validate
    Gateway->>Temporal: start_workflow(CPCOperativoWorkflow)
    Gateway-->>Client: 201 {operativo_id, status: PENDING}

    Note over Temporal: Phase 1 — Plan
    Temporal->>Santos: santos_plan activity
    Santos->>Memory: retrieve_patterns(domain, query)
    Memory-->>Santos: semantic patterns (L3)
    Santos->>Santos: PromptBuilder → LLM call (no tools)
    Santos-->>Temporal: PlannerOutput {plan_json}

    Note over Temporal: Phase 2 — Investigate
    Temporal->>Medina: medina_investigate activity
    Medina->>Memory: retrieve_patterns(domain, query)
    Memory-->>Medina: semantic patterns (L3)
    Medina->>CPCRobot: extract_pdf_text → POST /jobs/upload
    CPCRobot-->>Medina: extraction + validation data
    Medina->>Medina: scan_content (injection guard)
    Medina->>Medina: extract_cpc_data (structured fields)
    Medina-->>Temporal: InvestigatorOutput {input_snapshot_json, injection_risk}

    alt injection_risk == "high"
        Temporal-->>Client: HALTED (NEEDS_REVIEW)
    end

    Note over Temporal: Phase 3 — Execute
    Temporal->>Lamponne: lamponne_execute activity
    Lamponne->>Memory: retrieve_patterns(domain, query)
    Memory-->>Lamponne: semantic patterns (L3)
    Lamponne->>Lamponne: ToolHandler.run_loop() with discover_api / execute_api
    Lamponne-->>Temporal: AgentLoopOutput {final_response, tool_calls_made}

    Note over Temporal: Phase 4 — QA Review (retry loop)
    loop up to 3 attempts
        Temporal->>Santos: santos_qa_review activity
        Santos->>Memory: retrieve_patterns(domain, query)
        Memory-->>Santos: semantic patterns (L3)
        Santos->>Santos: Compare input_snapshot vs raw_output
        Santos-->>Temporal: QAReviewOutput {qa_report_json, final_status}
        alt final_status == "COMPLETED"
            Note over Temporal: Break — QA passed
        else blocking issues found
            Temporal->>Lamponne: lamponne_execute (corrections)
            Lamponne-->>Temporal: corrected output
        end
    end

    Note over Temporal: Phase 5 — Synthesize
    Temporal->>Ravenna: ravenna_synthesize activity
    Ravenna->>Ravenna: read_progress, load_artifact, check_caller_permission
    Ravenna->>Ravenna: write_structured_result
    Ravenna-->>Temporal: SynthesizerOutput {structured_result_json}

    opt callback_url provided
        Temporal->>Client: POST callback_url with result
    end

    Note over Temporal: Phase 6 — Post-Job Learn
    Temporal->>Memory: extract_patterns → graph store
    Memory-->>Temporal: PostJobOutput {patterns_extracted}

    Temporal-->>Client: CPCOperativoOutput (via status poll or callback)
```

---

## 2. API Intake

```mermaid
flowchart LR
    subgraph Client
        A[POST /operativo/dce]
    end

    subgraph Gateway["Gateway (FastAPI)"]
        B[RequestIdMiddleware<br/>assigns X-Request-ID]
        C[ApiKeyAuth.authenticate<br/>validates X-API-Key header]
        D[InMemoryRateLimiter.check<br/>per-caller rate limiting]
        E[dispatch_dce_operativo<br/>validates input, generates ID]
        F[Temporal client.start_workflow]
    end

    subgraph Response
        G["201 Created<br/>{operativo_id, status, task_queue}"]
    end

    A --> B --> C --> D --> E --> F --> G
```

### Request Body (`CPCRequest`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pdf_path` | `str` | Yes | Absolute path to the DCE PDF file |
| `pdf_filename` | `str` | Yes | Original filename (must end with `.pdf`) |
| `caller_id` | `str` | Yes | Caller identifier for audit and permissions |
| `callback_url` | `str` | No | URL for result delivery callback |
| `skip_navigation` | `bool` | No | Skip Amazon/marketplace navigation step |
| `skip_lab_check` | `bool` | No | Skip lab accreditation verification |
| `skip_photos` | `bool` | No | Skip product photo comparison |

### Dispatch Logic (`gateway/dispatch.py`)

1. Validate required fields (`pdf_path`, `pdf_filename`, `caller_id`)
2. Validate `pdf_filename` ends with `.pdf`
3. Generate `operativo_id` as `dce-{uuid_hex[:12]}`
4. Build `CPCOperativoInput` dataclass
5. Return `DispatchResult(operativo_id, PENDING, workflow_input)`

### Temporal Submission (`gateway/app.py`)

The gateway calls `client.start_workflow(CPCOperativoWorkflow.run, workflow_input, id=operativo_id, task_queue="dce-task-queue")` and returns immediately. The workflow runs asynchronously on the DCE worker.

---

## 3. Phase-by-Phase Data Flow

### Phase 1: Santos Plan

```mermaid
flowchart TD
    subgraph Input
        A[PlannerInput<br/>operativo_id, domain, pdf_description]
    end

    subgraph Processing
        B[get_anthropic_client]
        C[load_domain_memory → DCE.md]
        D[retrieve_patterns → MemoryRecall + BulletinStore]
        E[SantosPlanner.plan]
        F[BaseAgent.build_prompt<br/>L0→L1→L3→L2→L4]
        G["client.send_message<br/>(Opus 4.6, reasoning=high, NO tools)"]
        H[parse_plan_json → ExecutionPlan]
    end

    subgraph Output
        I["PlannerOutput<br/>plan_json: {steps: [{agent, action, params}]}"]
    end

    A --> B --> C --> D --> E
    E --> F --> G --> H --> I
```

| Aspect | Detail |
|--------|--------|
| **Agent** | Santos (Opus 4.6, reasoning effort: high) |
| **Input** | `operativo_id`, `domain="dce"`, `pdf_description` |
| **LLM call** | Single `send_message` (no tool loop). No tools registered. |
| **Output** | `PlannerOutput` with `plan_json` containing ordered steps |
| **Storage** | `PLAN.md` written to session store (via progress_entries) |
| **Timeout** | 120 seconds |

---

### Phase 2: Medina Investigate

```mermaid
flowchart TD
    subgraph Input
        A[InvestigatorInput<br/>operativo_id, domain, pdf_path, pdf_filename]
    end

    subgraph Processing
        B[load_domain_memory → DCE.md]
        C[retrieve_patterns → semantic L3]
        D[build_tool_handler with DCE tools]
        E[MedinaInvestigator.investigate]
        F[ToolHandler.run_loop<br/>Opus 4.6, reasoning=high]
    end

    subgraph "Tool Calls (multi-turn)"
        G["1. extract_pdf_text(pdf_path)<br/>→ DCE Backend API or local pdfplumber"]
        H["2. scan_content(text)<br/>→ injection_guard.scan_content"]
        I["3. extract_cpc_data(pdf_text)<br/>→ DCE Backend extraction or regex heuristics"]
    end

    subgraph Output
        J["InvestigatorOutput<br/>input_snapshot_json, injection_risk, halted"]
    end

    A --> B --> C --> D --> E --> F
    F --> G --> H --> I
    I --> J

    style H fill:#ff9999
```

| Aspect | Detail |
|--------|--------|
| **Agent** | Medina (Opus 4.6, reasoning effort: high) |
| **Tools** | `extract_pdf_text`, `scan_content`, `extract_cpc_data` |
| **Input** | `operativo_id`, `domain`, `pdf_path`, `pdf_filename` |
| **LLM call** | Multi-turn tool loop via `ToolHandler.run_loop()` |
| **Output** | `InvestigatorOutput` with `input_snapshot_json`, `injection_risk`, `halted` flag |
| **Halt condition** | `injection_scan_risk == "high"` stops the entire workflow |
| **Timeout** | 120 seconds |

---

### Phase 3: Lamponne Execute

```mermaid
flowchart TD
    subgraph Input
        A["AgentLoopInput<br/>agent=lamponne, domain=dce<br/>task_message=plan_json, max_turns=10"]
    end

    subgraph Processing
        B[load_domain_memory → DCE.md]
        C[retrieve_patterns → semantic L3]
        D[build_tool_handler with DCE tools]
        E[LamponneExecutor.execute]
        F["ToolHandler.run_loop<br/>Sonnet 4.6, reasoning=medium"]
    end

    subgraph "Tool Calls (multi-turn)"
        G["discover_api(category?)<br/>→ list available DCE operations"]
        H["execute_api(operation, params)<br/>→ validate + execute DCE operation"]
    end

    subgraph Output
        I["AgentLoopOutput<br/>final_response, tool_calls_made, turns_used"]
    end

    A --> B --> C --> D --> E --> F
    F --> G --> H
    H --> I
```

| Aspect | Detail |
|--------|--------|
| **Agent** | Lamponne (Sonnet 4.6, reasoning effort: medium) |
| **Tools** | `discover_api`, `execute_api` |
| **Input** | Plan JSON from Santos (Phase 1) |
| **LLM call** | Multi-turn tool loop, max 10 turns |
| **Output** | `AgentLoopOutput` with final response and tool call log |
| **Timeout** | 600 seconds (10 minutes, longest phase) |

---

### Phase 4: Santos QA Review

```mermaid
flowchart TD
    subgraph Input
        A["QAReviewInput<br/>operativo_id, domain<br/>input_snapshot_json, raw_output_json<br/>max_correction_attempts=3"]
    end

    subgraph Processing
        B[load_domain_memory → DCE.md]
        C[retrieve_patterns → semantic L3]
        D[SantosQAReviewer.review]
        E["BaseAgent.build_prompt<br/>includes CPC_VERIFICATION_CHECKLIST"]
        F["client.send_message<br/>(Opus 4.6, reasoning=high, NO tools)"]
        G[_parse_qa_json → QAReport]
    end

    subgraph Output
        H["QAReviewOutput<br/>qa_report_json, corrections_applied<br/>final_status: COMPLETED | NEEDS_REVIEW"]
    end

    subgraph "Retry Logic (workflow level)"
        I{has_blocking?}
        J{attempt < 3?}
        K[lamponne_execute with correction instructions]
        L[Return NEEDS_REVIEW]
    end

    A --> B --> C --> D --> E --> F --> G --> H
    H --> I
    I -->|Yes| J
    I -->|No| M[Return COMPLETED]
    J -->|Yes| K --> A
    J -->|No| L
```

| Aspect | Detail |
|--------|--------|
| **Agent** | Santos (Opus 4.6, reasoning effort: high) |
| **Input** | `input_snapshot_json` (Medina ground truth), `raw_output_json` (Lamponne result) |
| **LLM call** | Single `send_message` (no tool loop). Compares fields via checklist. |
| **Checklist** | `CPC_VERIFICATION_CHECKLIST` injected into prompt for deterministic checking |
| **Output** | `QAReviewOutput` with checks array, severity per check (BLOCKING/WARNING/INFO) |
| **Retry** | Workflow-level loop: if blocking issues, re-execute Lamponne with corrections, up to 3 times |
| **Timeout** | 300 seconds per QA attempt |

---

### Phase 5: Ravenna Synthesize

```mermaid
flowchart TD
    subgraph Input
        A["SynthesizerInput<br/>operativo_id, domain<br/>progress_entries, raw_output_json<br/>qa_report_json, caller_id"]
    end

    subgraph Processing
        B[load_domain_memory → DCE.md]
        C[retrieve_patterns → semantic L3]
        D[build_tool_handler with Ravenna tools]
        E[RavennaSynthesizer.synthesize]
        F["ToolHandler.run_loop<br/>Sonnet 4.6, reasoning=medium"]
    end

    subgraph "Tool Calls (multi-turn)"
        G["read_progress(operativo_id)<br/>→ SessionStore.read_progress()"]
        H["load_artifact(operativo_id, name)<br/>→ StorageBackend.read()"]
        I["check_caller_permission(caller_id)<br/>→ ACL check (currently always permits)"]
        J["write_structured_result(operativo_id, json)<br/>→ StorageBackend.write()"]
    end

    subgraph Output
        K["SynthesizerOutput<br/>structured_result_json, report_url<br/>delivery_permitted"]
    end

    A --> B --> C --> D --> E --> F
    F --> G --> H --> I --> J --> K
```

| Aspect | Detail |
|--------|--------|
| **Agent** | Ravenna (Sonnet 4.6, reasoning effort: medium) |
| **Tools** | `read_progress`, `load_artifact`, `write_structured_result`, `check_caller_permission` |
| **Input** | Progress entries from all phases, raw output, QA report, caller ID |
| **Output** | `SynthesizerOutput` with `structured_result_json` and `report_url` |
| **Storage** | Writes `structured_result.json` to session storage |
| **Timeout** | 120 seconds |

---

### Phase 6: Post-Job Learn

```mermaid
flowchart TD
    subgraph Input
        A["PostJobInput<br/>operativo_id, domain<br/>session_progress (full log)"]
    end

    subgraph Processing
        B["extract_patterns()"]
        C["Parse PROGRESS.md sections<br/>regex: ^## Phase — Agent"]
        D{For each section}
        E["Classify memory type:<br/>NEEDS_REVIEW → ERROR (0.7)<br/>COMPLETED → PATTERN (0.5)<br/>other → FACT (0.4)"]
        F["graph_store.store()<br/>domain, content, type, importance, source"]
    end

    subgraph Output
        G["PostJobOutput<br/>patterns_extracted, archived=True"]
    end

    A --> B --> C --> D --> E --> F --> G
```

| Aspect | Detail |
|--------|--------|
| **Agent** | None (no LLM call) |
| **Input** | Full session progress log from all phases |
| **Processing** | Regex parsing of PROGRESS.md sections, classify by memory type |
| **Output** | `PostJobOutput` with count of patterns extracted |
| **Storage** | Patterns stored in `InMemoryGraphStore` (production: `PostgresGraphStore` + pgvector) |
| **Timeout** | 60 seconds |

---

## 4. Tool Handler Loop

```mermaid
flowchart TD
    A[Agent builds prompt via PromptBuilder] --> B[ToolHandler.run_loop starts]
    B --> C["turn = 0"]

    C --> D["client.send_message(prompt, model, tools)"]
    D --> E{stop_reason == tool_use?}

    E -->|No| F["Return ToolLoopResult<br/>final_content, turns, tool_calls"]

    E -->|Yes| G[Append assistant message<br/>with text + tool_use blocks]
    G --> H[For each tool_call in response]

    H --> I{Handler registered?}
    I -->|No| J["Return tool_result<br/>is_error=True: Unknown tool"]
    I -->|Yes| K["Execute handler(tc.input)"]

    K --> L{Exception?}
    L -->|Yes| M["Return tool_result<br/>is_error=True: Tool error"]
    L -->|No| N{Loop detection enabled?}

    N -->|Yes| O["ResourceEditTracker.record(tool, args)"]
    O --> P{Threshold exceeded?}
    P -->|Yes| Q["Append guidance:<br/>[HARNESS] Reconsider approach"]
    P -->|No| R[Return tool_result]
    Q --> R

    N -->|No| R

    J --> S[Append user message<br/>with all tool_results]
    M --> S
    R --> S

    S --> T{turn < max_turns?}
    T -->|Yes| U["turn += 1"] --> D
    T -->|No| V["Return ToolLoopResult<br/>max_turns_reached=True"]

    style Q fill:#ffcc00
    style J fill:#ff9999
    style M fill:#ff9999
```

### ResourceEditTracker

The loop detection mechanism tracks per-resource invocation counts. When the same resource (e.g., a specific `execute_api` operation) is called more than `threshold` times (default: 5), guidance text is appended to the tool result:

```
[HARNESS] You have called execute_api on 'validate_cpc' 5 times.
Consider stepping back and reconsidering your approach entirely.
```

This prevents the LLM from entering doom loops on a single resource.

### Key Data Structures

```python
@dataclass(frozen=True)
class ToolLoopResult:
    final_content: str           # Last text response from the LLM
    turns: int                   # Number of send-execute-respond cycles
    tool_calls_made: list[ToolCall]  # All tool calls across all turns
    tool_errors: int             # Count of failed tool executions
    loop_warnings: int           # Count of loop detection warnings
    max_turns_reached: bool      # True if stopped by turn limit
    total_usage: TokenUsage      # Accumulated token usage
```

---

## 5. DCE Backend Dispatch Flow

```mermaid
sequenceDiagram
    participant Harness as Agent Harness<br/>(extract_pdf_text handler)
    participant API as DCE Backend API<br/>(REST)
    participant TW as DCE Backend<br/>Temporal Workflow
    participant Act as DCE Backend Activities<br/>(20 activities)

    Harness->>API: POST /jobs/upload<br/>{file: dce.pdf}
    API->>TW: Start DCE workflow
    API-->>Harness: {job_id}

    loop Poll every 5s (max 60 iterations = 5 min)
        Harness->>API: GET /jobs/{job_id}
        API-->>Harness: {status: "running"}
    end

    Note over TW, Act: DCE Backend internal workflow
    TW->>Act: extract_pdf_text
    TW->>Act: extract_cpc_data
    TW->>Act: navigate marketplace
    TW->>Act: validate fields
    TW->>Act: merge assessment

    Harness->>API: GET /jobs/{job_id}
    API-->>Harness: {status: "completed"}

    Harness->>API: GET /jobs/{job_id}/extraction
    API-->>Harness: {extraction: {...}}

    Harness->>API: GET /jobs/{job_id}
    API-->>Harness: Full result:<br/>{item_id, isam_product,<br/>validation, merged_assessment}

    Note over Harness: Combine extraction + full result

    alt DCE Backend unavailable (ConnectError)
        Note over Harness: Fallback to local pdfplumber
        Harness->>Harness: pdfplumber.open(pdf_path)
        Harness-->>Harness: {text, pages_extracted,<br/>total_pages, char_count}
    end
```

### Response Structure (DCE Backend path)

```json
{
  "job_id": "abc123",
  "status": "completed",
  "extraction": { "...structured DCE fields..." },
  "item_id": "...",
  "isam_product": "...",
  "validation": { "...validation results..." },
  "merged_assessment": { "...merged assessment..." }
}
```

### Response Structure (local fallback path)

```json
{
  "text": "...raw PDF text...",
  "pages_extracted": 3,
  "total_pages": 3,
  "char_count": 12450,
  "source": "local_pdfplumber"
}
```

---

## 6. Prompt Assembly Flow

```mermaid
flowchart TD
    subgraph "PromptBuilder.build()"
        direction TB

        L0["<b>L0 — System Identity</b><br/>(static, cached across ALL sessions)<br/><br/>e.g. 'You are Santos, the planning agent...'"]
        L1["<b>L1 — Domain Memory</b><br/>(static, cached across domain sessions)<br/><br/>DCE.md — domain rules, field definitions"]
        CB1["--- Cache Breakpoint ---<br/>system_cache: True"]
        L3["<b>L3 — Semantic Patterns</b><br/>(semi-static, changes across sessions)<br/><br/>MemoryRecall patterns + Bulletin summaries<br/>Injected as user message in &lt;semantic_patterns&gt; tags"]
        L2["<b>L2 — Session State</b><br/>(dynamic, changes within session)<br/><br/>PLAN.md / PROGRESS.md<br/>Injected as user message in &lt;session_state&gt; tags"]
        L4["<b>L4 — Working Messages</b><br/>(most dynamic, current turn only)<br/><br/>User task message + tool results"]

        L0 --> L1 --> CB1 --> L3 --> L2 --> L4
    end

    style L0 fill:#2d5016,color:#fff
    style L1 fill:#2d5016,color:#fff
    style CB1 fill:#cc6600,color:#fff
    style L3 fill:#1a4d80,color:#fff
    style L2 fill:#4d3380,color:#fff
    style L4 fill:#800000,color:#fff
```

### Layer Ordering (Thariq's Law)

The order is `L0 -> L1 -> L3 -> L2 -> L4` (not sequential by index). L3 comes before L2 because semantic patterns are more stable than session state across turns.

| Layer | Name | Where in API Call | Stability | Content |
|-------|------|-------------------|-----------|---------|
| L0 | System Identity | `system` prompt (first part) | Static (never changes) | Agent identity string |
| L1 | Domain Memory | `system` prompt (appended) | Static per domain | DCE.md content |
| L3 | Semantic Patterns | `messages[0]` (user) + `messages[1]` (assistant ack) | Semi-static | `<semantic_patterns>` XML tags |
| L2 | Session State | `messages[2]` (user) + `messages[3]` (assistant ack) | Dynamic per phase | `<session_state>` XML tags |
| L4 | Working Messages | `messages[4+]` | Most dynamic | Task message, tool results |

### Enforcement

`PromptBuilder._check_order()` raises `PromptOrderViolation` if:
- A layer is set out of order
- A layer is set twice
- A preceding required layer is missing

This is validated in `tests/cache_tests/` and is a CI-blocking failure.

### Assembled Prompt Structure

```python
{
    "system": "You are Santos... \n\n# DCE Domain Memory...",  # L0 + L1
    "messages": [
        # L3: Semantic patterns
        {"role": "user", "content": "<semantic_patterns>\n- [fact] ...\n</semantic_patterns>"},
        {"role": "assistant", "content": "Understood. I'll apply these learned patterns."},
        # L2: Session state
        {"role": "user", "content": "<session_state>\n## Progress...\n</session_state>"},
        {"role": "assistant", "content": "Session state received. Continuing from last checkpoint."},
        # L4: Working message
        {"role": "user", "content": "Create an execution plan for..."},
    ],
    "cache_control": {
        "system_cache": True,
        "system_token_estimate": 1500.0,
    },
}
```

---

## 7. Memory Flow

```mermaid
flowchart TD
    subgraph "Write Path (Post-Job Learn)"
        A["Phase 6: extract_patterns()"]
        B["Parse PROGRESS.md sections"]
        C["Classify: ERROR / PATTERN / FACT"]
        D["InMemoryGraphStore.store()<br/>(prod: PostgresGraphStore → pgvector)"]
    end

    subgraph "Read Path (Activity Startup)"
        E["_retrieve_semantic_patterns()"]
        F["MemoryRecall.retrieve_patterns()<br/>→ graph_store.search(domain, query, top_k=5)"]
        G["BulletinStore.get_pattern_strings(domain)"]
        H["Merge patterns + bulletin patterns"]
        I["→ PromptBuilder.set_semantic_patterns()"]
    end

    subgraph "Bulletin Generation (Cortex)"
        J["CortexBulletinWorkflow<br/>(scheduled, e.g. every 60 min)"]
        K["cortex_generate_bulletin activity"]
        L["MemoryRecall.retrieve_patterns()<br/>top_k=20"]
        M["LLM summarisation<br/>(Sonnet 4.6)"]
        N["Bulletin(domain, summary, pattern_count)"]
        O["BulletinStore"]
    end

    A --> B --> C --> D

    D -.->|"similarity search"| F
    E --> F
    E --> G
    F --> H
    G --> H
    H --> I

    J --> K --> L
    D -.->|"similarity search"| L
    L --> M --> N --> O
    O -.->|"cached bulletins"| G

    style D fill:#336699,color:#fff
    style O fill:#336699,color:#fff
```

### Memory Types

| Type | Importance | Trigger | Example |
|------|-----------|---------|---------|
| `ERROR` | 0.7 (high) | Phase report contains `NEEDS_REVIEW` | "QA found blocking issues in field X" |
| `PATTERN` | 0.5 (medium) | Phase report contains `status=COMPLETED` | "DCE for toys requires ASTM F963" |
| `FACT` | 0.4 (low) | All other phase reports | "Medina investigated document.pdf" |

### Data Flow Detail

1. **Write (post-job):** After each operativo completes, `extract_patterns()` parses the session progress log. Each phase section is stored as a `MemoryNode` in the graph store with domain, content, memory type, importance score, and source operativo ID.

2. **Read (per-activity):** Every activity calls `_retrieve_semantic_patterns()` which:
   - Calls `MemoryRecall.retrieve_patterns(domain, query, top_k=5)` for similarity search against the graph store
   - Calls `BulletinStore.get_pattern_strings(domain)` for cached cross-session summaries
   - Merges both lists and passes them to `PromptBuilder.set_semantic_patterns()` (L3)

3. **Bulletin generation (Cortex):** The `CortexBulletinWorkflow` runs on a schedule. It retrieves up to 20 recent patterns from the graph store, sends them to the LLM for summarisation, and stores the resulting `Bulletin` in the `BulletinStore`. This compressed summary is then available to all future activities via the read path.

### Storage Backends

| Environment | Graph Store | Embedding | Bulletin Store |
|-------------|------------|-----------|----------------|
| Development | `InMemoryGraphStore` | `FakeEmbeddingClient(dim=8)` | `InMemoryBulletinStore` |
| Production | `PostgresGraphStore` | Real embedding model | Persistent store (TBD) |
