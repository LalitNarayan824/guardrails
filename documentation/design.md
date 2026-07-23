# Design Document — LLM Guardrails Gateway

This document covers interface-level and class-level design decisions that `architecture.md` doesn't go into. Treat it as the reference used while actually writing code.

## 1. Core Interfaces

### 1.1 `Provider` (abstract base)

```python
class Provider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, params: dict) -> ProviderResponse:
        """Send prompt to the underlying LLM and return a normalized response."""
```

- `OpenAIProvider`, `AnthropicProvider`, `LocalMockProvider` all implement this.
- `ProviderResponse` normalizes across providers: `{ text, raw_tokens_in, raw_tokens_out, model, finish_reason }`.
- Provider selection happens via a factory keyed off the `provider` field in the request, resolved from YAML/env default if omitted.

### 1.2 `Guardrail` (abstract base)

```python
class Guardrail(ABC):
    name: str
    stage: Literal["input", "output"]
    cost_tier: Literal["cheap", "expensive"]  # drives execution order

    @abstractmethod
    async def check(self, payload: GuardrailPayload) -> GuardrailResult:
        """Evaluate the payload and return a pass/fail/redact verdict."""
```

```python
class GuardrailResult(BaseModel):
    guardrail_name: str
    verdict: Literal["pass", "block", "redact", "retry"]
    reason: str | None = None          # human-readable, used in retry re-prompt
    redacted_payload: str | None = None  # only set when verdict == "redact"
```

- Guardrails are stateless and side-effect-free beyond returning a `GuardrailResult` — this keeps them independently unit-testable.
- Ordering within a chain is sorted by `cost_tier` (`cheap` before `expensive`), then by explicit YAML order for ties.

### 1.3 Guardrail Chain (executor)

```python
class GuardrailChain:
    def __init__(self, guardrails: list[Guardrail]):
        self.guardrails = sorted(guardrails, key=lambda g: g.cost_tier)

    async def run(self, payload: GuardrailPayload) -> ChainResult:
        for g in self.guardrails:
            result = await g.check(payload)
            if result.verdict == "block":
                return ChainResult(blocked=True, triggered=[result])
            if result.verdict == "redact":
                payload = payload.with_redaction(result.redacted_payload)
        return ChainResult(blocked=False, payload=payload, triggered=[...])
```

- Short-circuits on first `block`.
- Accumulates all `redact` mutations before continuing.
- Every guardrail's verdict (pass or not) is recorded for the response's `guardrails_triggered` field and for metrics — even passes, for false-positive/negative benchmarking later.

## 2. Policy Engine

- YAML file is the single source of truth for active rules. Loaded at startup; a file-watcher (or a `/v1/admin/reload` endpoint, whichever is simpler to build first) triggers hot-reload.
- Each rule maps to one `Guardrail` instance, parameterized from YAML (e.g., `patterns`, `entities`, `max_retries`, `schema` path).
- Rule resolution order per request: **global rules** → **request-level `policy_overrides`** (can disable/enable specific named rules, not arbitrary new logic — overrides never let a client inject unvetted rules at runtime).
- Rule types:
  - `block` — short-circuit with a fallback response.
  - `redact` — mutate and continue (input side only, typically PII).
  - `retry` — used only on the output side; triggers the Retry/Correction Loop rather than an immediate block.

### 2.1 Example Rule → Guardrail mapping

| YAML `type` | Guardrail class | Stage |
|---|---|---|
| `block_pii` (`action: redact`) | `PIIGuardrail` | input |
| `injection_detection` | `PromptInjectionGuardrail` | input |
| `rate_limit` | `RateLimitGuardrail` | input |
| `length_guard` | `LengthCostGuardrail` | input |
| `require_json_schema` (`action: retry`) | `SchemaGuardrail` | output |
| `toxicity_filter` | `ToxicityGuardrail` | output |
| `no_competitor_mentions` (`action: block`) | `TopicPolicyGuardrail` | output |

See `rules.md` for the full YAML schema and worked examples.

## 3. Retry / Correction Loop

```
attempt = 0
while attempt < max_retries:
    response = provider.generate(prompt_with_failure_context)
    result = output_chain.run(response)
    if result.passed:
        return response
    if not cost_tracker.can_retry(session_id):
        break
    prompt_with_failure_context = build_correction_prompt(prompt, result.failure_reason)
    attempt += 1
return fallback_response(reason="max_retries_exhausted_or_cost_ceiling")
```

- `build_correction_prompt` appends a short, specific instruction derived from the failing guardrail's `reason` (e.g., *"Your previous response was missing the `email` field per the required schema. Return valid JSON matching the schema exactly."*) — never a generic "try again."
- Every attempt is logged with its own `guardrails_triggered` so the eventual benchmark/metrics can compute a true self-correction rate (fixed-on-retry vs. never-fixed).

## 4. Circuit Breaker

- Wraps any `Guardrail` whose `check()` calls an external/slow dependency (e.g., a moderation API).
- States: `closed` (normal) → `open` (failing, calls short-circuited) → `half-open` (probe) → `closed`.
- Config per guardrail:
  ```yaml
  circuit_breaker:
    failure_threshold: 5
    window_seconds: 30
    cooldown_seconds: 15
    fail_mode: open | closed   # what happens to the *request* while breaker is open
  ```
- `fail_mode: open` → guardrail is skipped (treated as `pass`) and a warning is logged; `fail_mode: closed` → guardrail is treated as `block` while the breaker is open. This choice must be visible in logs/metrics, never silent, since it directly affects safety posture.

## 5. Cost Tracking

- Per-request cost estimated from provider token usage (`raw_tokens_in/out * provider_rate_table`).
- Accumulated per `user_id`/`session_id` in Redis (or in-memory for local dev).
- Checked before each retry attempt (`cost_tracker.can_retry`) and exposed via `/v1/metrics` as `cost_per_user`.
- Ceiling breach ends the retry loop early regardless of remaining `max_retries` budget.

## 6. Observability

- **Structured logs**: JSON lines, one per request, with PII already redacted by the time logging happens (logging reads the *post-guardrail* payload, never the raw input).
- **Metrics** (Prometheus-style, exposed at `/v1/metrics`):
  - `requests_total`, `requests_blocked_total`
  - `retry_success_rate`
  - `guardrail_latency_ms` (histogram, per guardrail)
  - `cost_per_user`
- Logging and metrics emission are async/fire-and-forget relative to the main request path, so they never add to client-facing latency.

## 7. Benchmark Suite Design

- Input: a curated JSON/YAML file of ~50–100 known attack prompts (labeled `malicious`) and ~50 legitimate edge-case prompts (labeled `benign`).
- Runner sends each through the full gateway pipeline (or just the guardrail chain in isolation, for faster iteration) and records the verdict.
- Reports, per guardrail and in aggregate:
  - **Recall** = malicious prompts blocked / total malicious
  - **Precision** = malicious prompts blocked / total blocked
  - **False-positive rate** = benign prompts blocked / total benign
- Exposed via `POST /v1/benchmark/run`, returning the same numbers that go in the README.

## 8. Key Design Tradeoffs (to document in README once built)

- **Heuristic detection vs. ML classifier**: heuristics are transparent and fast (fits the latency budget) but have a real, honestly-reported false-negative rate. This is a deliberate, stated tradeoff — not a limitation to hide.
- **Fail-open vs. fail-closed default**: fail-closed is safer but can cause outages if a dependency degrades; fail-open keeps availability but risks letting bad content through during an outage. Default should be `fail_closed` for security-critical guardrails (injection, PII) and configurable per rule otherwise.
- **Synchronous retry loop vs. async/queued correction**: synchronous is simpler and fits the "return a guarded response in one HTTP call" contract, at the cost of added latency on retry paths — acceptable given retries are the exception, not the common case.
