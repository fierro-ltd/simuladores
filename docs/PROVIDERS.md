# Provider Compatibility Matrix

| Provider Profile | Capable Model | Fast Model | Cache Control | Structured Output | Air-Gapped | Status |
|---|---|---|---|---|---|---|
| anthropic-vertex | claude-opus-4-6 | claude-sonnet-4-6 | Full | ANTHROPIC_TOOLS | No | Production |
| openrouter | claude-opus-4-6 | claude-sonnet-4-6 | Pass-through | JSON | No | Production |
| litellm-proxy | (configured in litellm) | (configured in litellm) | LiteLLM strips | JSON | Depends | Production |
| hospital-airgapped | mistral-large | mistral-small | Stripped | vLLM guided | Yes | Validated |
| local-ollama | llama4:scout | mistral-small3.1 | Stripped | Model-dependent | Yes | Dev only |

## Configuration

Provider selection is a single environment variable:

```bash
SIMULADORES_PROVIDER_PROFILE=anthropic-vertex  # default
SIMULADORES_PROVIDER_PROFILE=openrouter        # OpenRouter cloud gateway
SIMULADORES_PROVIDER_PROFILE=litellm-proxy     # self-hosted LiteLLM
SIMULADORES_PROVIDER_PROFILE=hospital-airgapped # air-gapped hospital
SIMULADORES_PROVIDER_PROFILE=local-ollama      # local dev, no API keys
```

## Known Limitations Per Provider

### OpenRouter
- 5% markup on all requests — not suitable for high-volume production
- SaaS only — requests route through OpenRouter infrastructure (GDPR consideration)
- 25-40ms added latency per request

### local-ollama
- Structured output reliability is model-dependent — increase max_retries to 5
- Not suitable for NEEDS_REVIEW threshold compliance — use hospital-airgapped instead

### hospital-airgapped
- Prompt caching not available — expect higher latency on repeated similar documents
- Quality gap vs. Claude — validate with full golden case suite before production use
- Requires pre-downloaded model weights on hospital hardware

## Validating a New Provider

Run the promptfoo eval suite against golden cases:

```bash
SIMULADORES_PROVIDER_PROFILE=<profile> \
npx promptfoo eval --config tests/evals/promptfooconfig.yaml --ci
```

If verdicts match at >= 95% on golden cases, the provider is acceptable for that domain.
