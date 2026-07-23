# Phases / Roadmap — LLM Guardrails Gateway

Total estimated build time: **3–4 weeks**. Each phase below expands the spec's 4-week roadmap into concrete, checkable tasks.

---

## Phase 1 (Week 1) — Gateway Skeleton & Provider Abstraction

**Goal:** a working `/v1/generate` endpoint that talks to a real LLM through a swappable provider interface, with the first input guardrails in place.

- [ ] Scaffold FastAPI project structure (`app/`, `guardrails/`, `providers/`, `config/`, `tests/`).
- [ ] Define `Provider` abstract interface (`design.md §1.1`).
- [ ] Implement `LocalMockProvider` (deterministic canned responses, for fast/free testing).
- [ ] Implement one real cloud adapter (`OpenAIProvider` or `AnthropicProvider`).
- [ ] Provider selection via config/request field (Strategy pattern, no hardcoding).
- [ ] Define `Guardrail` abstract interface (`design.md §1.2`) and `GuardrailChain` executor.
- [ ] Implement input guardrails: PII regex detection, input length/cost guard, rate limiting (token bucket + Redis).
- [ ] Basic YAML policy engine: load rules at startup, map rule `type` → `Guardrail` instance.
- [ ] `POST /v1/generate` wired end-to-end: input chain → provider → return raw response (no output guardrails yet).
- [ ] Unit tests for each input guardrail in isolation.

**Exit criteria:** a client can hit `/v1/generate`, get a real LLM response, and have at least PII redaction + rate limiting actually enforced.

---

## Phase 2 (Week 2) — Output Guardrails, Retry Loop, Circuit Breaker

**Goal:** the differentiator feature that makes this more than a wrapper — auto-correction — plus resilience around slow dependencies.

- [ ] Implement output guardrails: JSON schema validation, toxicity/content filter, topic/policy enforcement.
- [ ] Implement the Retry/Correction Loop (`design.md §3`): re-prompt with specific failure reason, capped `max_retries`, fallback response on exhaustion.
- [ ] Implement Circuit Breaker wrapping the (likely external) toxicity/moderation check, with configurable `fail_mode`.
- [ ] Extend YAML schema to support `retry` action and circuit-breaker block (`rules.md §5`).
- [ ] Integration tests: full pipeline including retry loop and circuit breaker fail-open/fail-closed behavior.
- [ ] Confirm request-level `policy_overrides` work and cannot inject unregistered rules.

**Exit criteria:** a deliberately malformed JSON response gets auto-corrected within N retries and this is demonstrable in a test; a simulated dependency outage trips the circuit breaker and behaves per configured `fail_mode`.

---

## Phase 3 (Week 3) — Observability, Benchmark Suite, Cost Tracking

**Goal:** turn the project's safety claims into actual numbers.

- [ ] Structured JSON logging (async, PII-redacted, one line per request).
- [ ] Prometheus-style metrics: `requests_total`, `requests_blocked_total`, `retry_success_rate`, `guardrail_latency_ms` histogram, `cost_per_user`.
- [ ] `GET /v1/metrics` endpoint.
- [ ] Cost tracker: per-request cost estimate from token usage, per-user/session accumulation, hard ceiling enforcement on retries.
- [ ] Curate benchmark corpus: ~50-100 known attack prompts + ~50 benign edge cases.
- [ ] Build benchmark runner + `POST /v1/benchmark/run` reporting precision/recall/false-positive rate per guardrail.
- [ ] Run the benchmark for the first time and record actual (not illustrative) numbers.

**Exit criteria:** running the benchmark suite produces a real precision/recall/false-positive table that can go straight into the README.

---

## Phase 4 (Week 4) — Load Testing, Packaging, Docs, Polish

**Goal:** ship something a reviewer can clone, run, and evaluate in minutes.

- [ ] Write Locust or k6 load test script(s).
- [ ] Run load test, capture p50/p95 latency and max sustained throughput.
- [ ] Dockerfile + `docker-compose.yml` (gateway + Redis, optional Prometheus/Grafana).
- [ ] Verify a clean `docker-compose up` works from a fresh clone.
- [ ] Write final README: architecture diagram, design tradeoffs, measured results, "what I'd do with more time" (see `README.md`).
- [ ] (Optional) Deploy a live demo (Render / Fly.io / Railway) and link it.
- [ ] (Optional, if time remains) Shadow-mode rule evaluation.
- [ ] (Optional, if time remains) One stretch feature from PRD §8.6 (hallucination guard, multi-tenant policies, dashboard, or streaming guardrails).

**Exit criteria:** matches the Final Deliverables Checklist in `PRD.md §12`.

---

## Suggested Order of Operations Within Each Week

Guardrails are easiest to build and test in isolation before wiring into the chain — write the unit test for a guardrail before hooking it into `GuardrailChain`. Similarly, get the retry loop working against `LocalMockProvider` (which you can force to return malformed output on command) before relying on a real LLM's actual failure modes, which are noisier and slower to iterate against.

## Explicitly Deferred (do not start until Phases 1–4 are solid)

- Multi-tenant policy support
- Streaming response guardrails
- Hallucination guard
- Full real-time dashboard (a minimal read-only one is in scope; a polished one is not)
