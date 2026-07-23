# Product Requirements Document (PRD)
## LLM Guardrails Gateway

**Version:** 1.0
**Track:** General Software Engineering / Backend
**Estimated Build Time:** 3–4 weeks

---

## 1. Problem Statement

Applications that call Large Language Models directly expose themselves to a class of risks that traditional API gateways were never designed to handle: prompt injection, sensitive data leakage, malformed or unsafe model output, and unbounded cost from retries or abuse.

Most teams bolt on ad-hoc checks per-application, leading to inconsistent enforcement, duplicated logic, and no shared observability across LLM traffic.

## 2. Solution Summary

The LLM Guardrails Gateway is a middleware proxy that sits between any client application and any LLM provider. It intercepts every request and response to enforce configurable safety, compliance, and structural rules — functioning as a specialized API gateway for LLM traffic, in the same spirit as Kong or NGINX for conventional HTTP services.

## 3. Why This Project Matters

- Frames an AI-adjacent problem as an **infrastructure / systems engineering** problem — the core skills demonstrated are resilience, observability, and API design, not prompt engineering.
- Produces **measurable engineering results** (latency budgets, precision/recall, retry success rate) rather than subjective safety claims.
- Exercises a broad slice of backend engineering: middleware design, rules engines, async I/O, circuit breakers, structured logging, and load testing.

## 4. One-Line Pitch

> "A middleware gateway that auto-corrects malformed LLM output (73% self-correction rate), blocks prompt-injection attempts (94% recall, <2% false-positive rate on a 100-prompt benchmark), and adds under 50ms p95 latency overhead."

*(Numbers are illustrative targets — replace with actual measured results once built.)*

## 5. Goals

| # | Goal |
|---|------|
| G1 | Provide a provider-agnostic proxy for LLM calls (OpenAI, Anthropic, local models) behind one consistent API. |
| G2 | Enforce configurable input and output guardrails without requiring code changes (YAML-driven policy engine). |
| G3 | Automatically self-correct malformed or non-compliant LLM output via a retry loop. |
| G4 | Expose first-class observability: metrics, structured logs, and a benchmark suite with precision/recall numbers. |
| G5 | Stay within a defined latency budget, with graceful degradation if a guardrail dependency is slow or unavailable. |

## 6. Non-Goals

- **Not** a general-purpose, research-grade jailbreak detector. Heuristic and lightweight ML detection on a known benchmark is sufficient, and should be explicitly stated as such (not oversold).
- **Not** supporting every LLM provider on day one. Two providers (one cloud, one local/mock) is enough to prove the abstraction.
- **Not** building a full enterprise admin UI. A YAML config file plus a minimal read-only dashboard is sufficient.

## 7. Target Users / Use Cases

- **Backend/platform engineers** who want a drop-in safety layer in front of any LLM call without changing application code.
- **Portfolio / interview context**: this PRD assumes the primary "user" is also an evaluator — every feature should map to a demonstrable, measurable engineering result.

## 8. Functional Requirements

### 8.1 Input Guardrails (must-have)
- PII detection (emails, phone numbers, credit cards, SSNs/national IDs) — block or redact.
- Prompt injection detection (keyword/pattern heuristics, optional embedding-similarity check).
- Rate limiting (token bucket, per user/API key).
- Input length / cost guard (reject oversized requests before they reach a paid LLM API).

### 8.2 Output Guardrails (must-have)
- Schema enforcement (JSON Schema validation on JSON-mode responses).
- Toxicity / content filter.
- Topic / policy enforcement (e.g., "never mention competitor X").

### 8.3 Policy Engine
- YAML-driven rule definitions.
- Hot-reload without redeploy.
- Rule types: `block`, `redact`, `retry`.

### 8.4 Provider Abstraction
- Common `Provider` interface with a single `generate(prompt, params)` method.
- At least two adapters: one real cloud LLM (OpenAI or Anthropic) and one local/mock model.
- Provider selection is config-driven (Strategy pattern).

### 8.5 Differentiator Features
- Auto-retry-with-correction loop (re-prompt LLM with specific failure reason, capped retries).
- Latency budget + circuit breaker around slow/unreliable guardrail dependencies.
- Benchmark suite reporting precision/recall/false-positive rate.
- Pluggable `Guardrail` interface for adding new rules without modifying gateway code.
- Shadow mode / canary evaluation for new rules.
- Cost tracking with a hard per-user/session ceiling.

### 8.6 Stretch Features
- Hallucination guard (flag low-confidence/unverifiable claims).
- Multi-tenant policy support (per-API-key rule sets).
- Minimal read-only real-time metrics dashboard.
- Streaming response support with guardrails applied to partial output.

## 9. Success Metrics & Targets

| Metric | Target / What to Report |
|---|---|
| Injection detection recall | % of known attack prompts correctly blocked (benchmark suite) |
| Injection detection false-positive rate | % of benign prompts incorrectly blocked |
| Schema retry self-correction rate | % of initially malformed outputs fixed within N retries |
| Latency overhead (p50 / p95) | Added milliseconds from guardrail checks, under load |
| Throughput | Requests/sec sustained before degrading (load test) |
| Cost per request | Average $ spent per request including retries, and effect of cost ceiling |

## 10. Out of Scope / Explicit Risks

- Detection accuracy is heuristic-based; it is **not** a substitute for a production-grade, continuously-retrained safety model. This should be stated plainly in the README, not hidden.
- No claim of "unjailbreakable" — the benchmark suite exists precisely to make the actual detection rate visible and honest.

## 11. Dependencies

- Redis (rate limiting, optionally shared state for circuit breaker).
- An LLM provider API key (OpenAI or Anthropic) for the live adapter.
- Optional: spaCy / Microsoft Presidio for NER-based PII detection.
- Optional: Prometheus + Grafana for metrics visualization.

## 12. Acceptance Criteria (Definition of Done)

See `phases.md` and the Final Deliverables Checklist in the original spec — summarized:

- [ ] Gateway with ≥4 input guardrails and ≥3 output guardrails, working end-to-end.
- [ ] YAML policy engine with ≥2 distinct rule types, hot-reloadable.
- [ ] Auto-retry-with-correction loop implemented and tested.
- [ ] Circuit breaker around ≥1 external/slow dependency.
- [ ] Benchmark suite with reported precision/recall/false-positive numbers.
- [ ] Load test results (p50/p95 latency, max throughput) documented.
- [ ] Dockerized via docker-compose.
- [ ] Unit + integration test suite.
- [ ] README with architecture diagram, tradeoffs, measured results, and "what I'd do with more time."
