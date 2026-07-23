# LLM Guardrails Gateway

A middleware proxy that sits between any client application and any LLM provider, enforcing configurable safety, compliance, and structural guardrails on every request and response — a specialized API gateway for LLM traffic, in the same spirit as Kong or NGINX for conventional HTTP services.

> **Status:** Spec / pre-implementation. Numbers below are illustrative targets until the benchmark suite and load tests are actually run — see `phases.md` for the build plan.

## The Pitch

> A middleware gateway that auto-corrects malformed LLM output (target: ~73% self-correction rate), blocks prompt-injection attempts (target: ~94% recall, <2% false-positive rate on a 100-prompt benchmark), and adds under 50ms p95 latency overhead.

## Why This Exists

Applications that call LLMs directly inherit a class of risks traditional API gateways were never built for: prompt injection, sensitive data leakage, malformed or unsafe model output, and unbounded cost from retries or abuse. Most teams patch this in per-application, with inconsistent enforcement and no shared visibility. This project centralizes it — and treats it as an infrastructure problem (resilience, observability, API design), not a prompt-engineering problem.

## Features

**Input Guardrails**
- PII detection (email, phone, credit card, SSN) — block or redact
- Prompt injection detection (heuristic + optional embedding-similarity)
- Rate limiting (token bucket via Redis)
- Input length / cost guard

**Output Guardrails**
- JSON schema enforcement, with auto-retry-and-correction on failure
- Toxicity / content filtering
- Topic / policy enforcement (e.g., "never mention competitor X")

**Platform Features**
- YAML-driven policy engine, hot-reloadable, no code changes to add a rule
- Provider-agnostic (OpenAI, Anthropic, local/mock) via a common `Provider` interface
- Circuit breaker around slow/unreliable guardrail dependencies (fail open/closed, configurable)
- Structured, PII-redacted logging + Prometheus-style metrics
- Per-user/session cost tracking with a hard ceiling
- Benchmark suite reporting real precision/recall/false-positive numbers

## Architecture (short version)

```
Client --> Gateway API --> Input Guardrails --> LLM Provider --> Output Guardrails --> Client
                                 |                                      |
                            [blocked?]                          [retry / fallback]
```

Full details, component responsibilities, and failure-mode handling: see `architecture.md`.

## Project Docs

| Doc | Contents |
|---|---|
| [`PRD.md`](./PRD.md) | Problem statement, goals/non-goals, functional requirements, success metrics |
| [`architecture.md`](./architecture.md) | System flow, core components, tech stack, resilience design |
| [`design.md`](./design.md) | Interfaces (`Provider`, `Guardrail`), retry loop, circuit breaker, benchmark design, tradeoffs |
| [`rules.md`](./rules.md) | YAML policy engine schema and full rule reference |
| [`phases.md`](./phases.md) | Week-by-week build plan with exit criteria |
| [`memory.md`](./memory.md) | Running decision log / project context for continuity across sessions |

## Quickstart (once implemented)

```bash
git clone <repo>
cd llm-guardrails-gateway
cp .env.example .env         # add your OPENAI_API_KEY or ANTHROPIC_API_KEY
docker-compose up
```

```bash
curl -X POST http://localhost:8000/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarize this in one sentence: ...",
    "provider": "openai",
    "user_id": "demo-user"
  }'
```

## API Contract (draft)

### `POST /v1/generate`

Request:
```json
{
  "prompt": "string",
  "provider": "openai | anthropic | local",
  "response_schema": { "...": "optional JSON Schema" },
  "policy_overrides": ["rule_name"],
  "user_id": "string"
}
```

Response:
```json
{
  "output": "string | object",
  "blocked": false,
  "retries_used": 1,
  "guardrails_triggered": ["pii_detection"],
  "latency_ms": 142,
  "cost_usd": 0.0021
}
```

### `GET /v1/metrics`
Prometheus-compatible: `requests_total`, `requests_blocked_total`, `retry_success_rate`, `guardrail_latency_ms` histogram, `cost_per_user`.

### `POST /v1/benchmark/run`
Runs the benchmark suite against the current config; returns precision/recall/false-positive rate per guardrail.

## Measured Results

*(Fill in once built — this is the section that matters most to reviewers.)*

| Metric | Result |
|---|---|
| Injection detection recall | — |
| Injection detection false-positive rate | — |
| Schema retry self-correction rate | — |
| Latency overhead (p50 / p95) | — |
| Throughput (sustained req/s) | — |
| Cost per request (avg, incl. retries) | — |

## Design Tradeoffs

*(Summarize from `design.md §8` once implementation choices are finalized — e.g., heuristic vs. ML detection, fail-open vs. fail-closed defaults, synchronous vs. queued retry loop.)*

## Testing

| Type | Coverage |
|---|---|
| Unit | Each guardrail in isolation (PII regex, schema validator, policy engine parsing) |
| Integration | Full pipeline incl. retry/correction loop and circuit breaker fail-open/closed |
| Benchmark | Precision/recall against curated attack + benign prompt set |
| Load | Locust/k6 — p50/p95 latency, max sustained throughput |

## What I'd Do With More Time

*(Fill in post-build — candidates from the stretch list: hallucination guard, multi-tenant policy support, real-time dashboard, streaming-response guardrails, embedding-based semantic detection to reduce false negatives further.)*

## Non-Goals (stated up front, on purpose)

This is **not** a research-grade jailbreak detector, does not support every LLM provider on day one, and does not ship a full enterprise admin UI. See `PRD.md §6` for the full reasoning — these are deliberate scope boundaries, not gaps.

## License

*(Add your license of choice.)*
