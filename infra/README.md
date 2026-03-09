# Agent Harness — Production Deployment

## Prerequisites

- Docker and Docker Compose v2
- Google Cloud ADC credentials (`gcloud auth application-default login`)
- DCE Backend running and accessible

## Quick Start

```bash
# 1. Copy and configure environment
cp infra/.env.example infra/.env
# Edit infra/.env with your values

# 2. Build and start
docker compose -f infra/docker-compose.prod.yml up -d

# 3. Verify
curl http://localhost:8000/health
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  GCE VM                                              │
│                                                      │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────────┐ │
│  │ Gateway  │  │ Worker   │  │ Temporal + PG       │ │
│  │ :8000    │  │ (DCE)    │  │ :7233 (internal)    │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬──────────┘ │
│       │              │                   │            │
│       └──────────────┴───────────────────┘            │
│                      │                                │
│              Vertex AI (ADC)                          │
│              DCE Backend (internal)                     │
└──────────────────────────────────────────────────────┘
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| gateway | 8000 | FastAPI intake API |
| worker-dce | — | DCE Temporal worker |
| temporal | 7233 (internal) | Workflow orchestration |
| temporal-ui | 8233 (internal) | Temporal Web UI |
| postgresql | 5432 (internal) | Temporal + pgvector storage |

## ADC Credentials

The worker and gateway mount your local ADC credentials:
```bash
gcloud auth application-default login
```

The credentials file is mounted read-only at `/tmp/adc.json` inside containers.

## Updating

```bash
docker compose -f infra/docker-compose.prod.yml pull
docker compose -f infra/docker-compose.prod.yml up -d --build
```
