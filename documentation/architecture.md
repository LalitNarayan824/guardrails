# Architecture — LLM Guardrails Gateway

## 1. High-Level Request Flow

```
Client App
    |
    v
Gateway API (FastAPI)
    |
    |--> Observability Layer (logs, metrics, cost tracker)  [runs in parallel]
    |
    v
Input Guardrail Chain
(PII, injection, rate limit, length)
    |
    |-- [ blocked ] --> safe fallback response --> Client
    |
    v  [ passed ]
LLM Provider Adapter --> LLM API
    |
    v
Output Guardrail Chain
(schema, toxicity, policy)
    |
    |-- [ passed ] --------------------------> Client
    |-- [ retry ]  --> re-prompt LLM (max N attempts) --> back to Output Guardrails
    |-- [ fail ]   --> safe fallback response --> Client
```

Guardrail chains are **ordered and short-circuiting**: cheap checks (regex) run before expensive ones (ML model / external API calls), so a request that fails an early, cheap check never pays the cost of a later, expensive one.

## 2. Core Components

| Component | Responsibility |
|---|---|
| **Gateway API** | Public-facing endpoint. Accepts client requests, orchestrates the guardrail pipeline, returns responses. |
| **Policy Engine** | Loads YAML rule definitions; evaluates which rules apply per request; supports hot-reload without redeploying. |
| **Input Guardrail Chain** | Ordered, short-circuiting checks run before the LLM call (PII detection, injection detection, rate limiting, length/cost guard). |
| **Provider Adapter** | Common interface (`Provider` abstract class) so OpenAI, Anthropic, or a local model can be swapped without touching gateway logic. |
| **Output Guardrail Chain** | Checks run on the LLM's response (schema validation, toxicity/content filter, policy/topic enforcement). |
| **Retry / Correction Loop** | On output guardrail failure, re-prompts the LLM with the specific failure reason, up to a configurable max attempts, before falling back. |
| **Circuit Breaker** | Wraps slow/unreliable guardrail dependencies (e.g., an external moderation API); fails open or closed per config if a dependency is unhealthy. |
| **Observability Layer** | Structured logging (PII-redacted), Prometheus-style metrics, per-user cost tracking. |
| **Benchmark Suite** | Offline test harness that runs known attack/benign prompts through the gateway and reports precision/recall. |

## 3. Suggested Tech Stack

| Layer | Suggested Tools |
|---|---|
| API Framework | FastAPI (Python) or Express/Fastify (Node) — async-first |
| Schema Validation | Pydantic (Python) or Zod/AJV (Node) + JSON Schema |
| PII / NER Detection | Regex baseline + spaCy or Microsoft Presidio for entity detection |
| Rules Engine Config | YAML, parsed with PyYAML / js-yaml |
| Rate Limiting | Token bucket via Redis |
| Metrics | Prometheus client + Grafana, or a simple custom dashboard |
| Load Testing | Locust or k6 |
| Containerization | Docker + docker-compose for local dev |
| Deployment (optional) | Render, Fly.io, or Railway for a live demo link |

## 4. Data Flow: Request Lifecycle

1. **Ingress** — Gateway API receives `POST /v1/generate`. Request is logged (async, non-blocking) to the Observability Layer.
2. **Input Guardrails** — Policy Engine resolves the active rule set for this request (base config + `policy_overrides`). Rules run in order of increasing cost. First `block` short-circuits with a fallback response; `redact` mutates the prompt in place and continues.
3. **Provider Call** — Request is dispatched through the Provider Adapter to the configured LLM (`openai` | `anthropic` | `local`), wrapped in the latency budget timer.
4. **Output Guardrails** — Response runs through schema validation, toxicity/content filter, and topic/policy checks, again cheap-first.
   - **Pass** → return to client.
   - **Retry** → Retry/Correction Loop re-prompts the LLM with the specific validation failure appended as instruction, up to `max_retries`. Cost Tracker checks the per-session cost ceiling before allowing each retry.
   - **Fail** (retries exhausted or ceiling hit) → safe fallback response returned.
5. **Egress** — Final response, guardrails triggered, retry count, latency, and cost are logged and returned in the response envelope (see API contract).

## 5. Failure Modes & Resilience

- **Guardrail dependency slow/down** (e.g., external moderation API): Circuit Breaker trips after N consecutive failures/timeouts within a window; while open, the gateway either fails open (skip that check, log a warning) or fails closed (block the request) per YAML config — this choice is deliberately explicit and auditable, never silent.
- **LLM provider error/timeout**: treated as a distinct failure path from guardrail failure; surfaced with its own error code so clients can distinguish "the model failed" from "your request was blocked."
- **Retry loop runaway cost**: capped by both `max_retries` (attempt count) and the per-user/session cost ceiling — whichever triggers first wins.

## 6. Extensibility Points (Strategy Pattern, applied twice)

- **`Provider`** — `generate(prompt, params) -> response`. New LLM backends are added by implementing this interface; no gateway code changes.
- **`Guardrail`** — `check(payload) -> GuardrailResult`. New rules (input or output) are added by implementing this interface and registering them in YAML; no gateway code changes.

This dual application of the same pattern is the primary "systems design" signal of the project — see `design.md` for interface details.

## 7. Deployment Topology (local dev)

```
docker-compose
 ├── gateway (FastAPI app)
 ├── redis   (rate limiting, circuit breaker state)
 └── (optional) prometheus + grafana
```

Single-process gateway is sufficient for the target scope; horizontal scaling is noted as a "with more time" item, not a requirement.
