# Phase 1 (Week 1) — Gateway Skeleton & Provider Abstraction

**Goal:** a working `/v1/generate` endpoint that talks to a real LLM through a swappable provider interface, with the first input guardrails in place and actually enforced.

**Exit criteria:** a client can hit `/v1/generate`, get a real LLM response, and have at least PII redaction + rate limiting actually enforced — verifiable with a couple of `curl` commands (see Step 9).

---

## Step 0 — Project scaffold

Create the folder structure before writing any logic. Deciding this upfront avoids reshuffling later.

```
app/
  main.py                  # FastAPI app factory, mounts routers
  routers/
    generate.py             # POST /v1/generate
    health.py                # GET /health
  config/
    settings.py               # env vars, Redis URL, provider defaults (pydantic BaseSettings)
    policies.yaml              # rule definitions
    policy_loader.py            # parses YAML → Guardrail instances
providers/
  base.py                   # Provider abstract class
  local_mock.py               # LocalMockProvider
  anthropic_provider.py        # AnthropicProvider (or OpenAI)
  factory.py                    # get_provider(name) -> Provider instance
guardrails/
  base.py                   # Guardrail abstract class + GuardrailResult
  chain.py                    # GuardrailChain executor
  pii.py                        # PII regex guardrail
  length_guard.py                 # input length/cost guard
  rate_limit.py                    # token bucket / fixed-window, Redis-backed
tests/
  test_providers.py
  test_guardrails/
    test_pii.py
    test_length_guard.py
    test_rate_limit.py
docker-compose.yml
Dockerfile
requirements.txt
```

**Tasks:**
- [ ] Create the folder/file structure above (empty files are fine to start).
- [ ] `requirements.txt` — pin `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `pyyaml`, `redis`, `anthropic` (or `openai`), `pytest`, `pytest-asyncio`, `fakeredis` (for tests).
- [ ] `Dockerfile` — `python:3.12-slim` base, install deps, run via `uvicorn app.main:app --host 0.0.0.0`.
- [ ] `docker-compose.yml` — two services: `gateway` (build from Dockerfile) and `redis` (official `redis:alpine` image). Confirm `docker-compose up` starts both.
- [ ] `GET /health` endpoint returning `{"status": "ok"}` with a 200 — needed later for Render health checks and load-testing scripts, cheap to do now.

---

## Step 1 — `Provider` interface

Defines the contract every LLM adapter must satisfy, so gateway logic never needs to know which provider it's talking to.

**File: `providers/base.py`**
```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class GenerateParams(BaseModel):
    max_tokens: int = 1024
    temperature: float = 0.7
    response_schema: dict | None = None

class ProviderResponse(BaseModel):
    text: str
    tokens_used: int
    raw: dict  # original provider payload, for debugging/logging

class Provider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, params: GenerateParams) -> ProviderResponse:
        ...
```

**Tasks:**
- [ ] Write `Provider`, `GenerateParams`, `ProviderResponse` as above.
- [ ] Decide on a small set of normalized exception types (e.g. `ProviderTimeoutError`, `ProviderError`) that every adapter raises, so downstream code never branches on provider-specific exceptions.

---

## Step 2 — `LocalMockProvider`

Build this before the real adapter — it's simpler, free, and becomes your main testing tool for later phases (retry loop, circuit breaker).

**Tasks:**
- [ ] Implement `LocalMockProvider(Provider)` with a `mode` parameter (from request or env var):
  - [ ] `mode="valid"` — returns clean text or valid JSON matching a given schema.
  - [ ] `mode="broken_json"` — returns malformed JSON (needed in Phase 2 to test the retry loop).
  - [ ] `mode="timeout"` — sleeps past the latency budget (needed later for circuit breaker testing).
  - [ ] `mode="error"` — raises a `ProviderError` (needed later for fallback-response testing).
- [ ] Default mode is `"valid"` so it works out of the box without extra config.

---

## Step 3 — Real cloud adapter

**Tasks:**
- [ ] Implement `AnthropicProvider(Provider)` (or `OpenAIProvider`) as a thin wrapper around the official SDK.
- [ ] Catch SDK-specific exceptions and re-raise as your normalized exception types from Step 1.
- [ ] Read the API key from an environment variable — never hardcode it, never put it in `policies.yaml`.

---

## Step 4 — Provider factory (Strategy pattern)

**File: `providers/factory.py`**
```python
def get_provider(name: str) -> Provider:
    return {
        "local": LocalMockProvider(),
        "anthropic": AnthropicProvider(),
    }[name]
```

**Tasks:**
- [ ] Implement `get_provider(name)` as above.
- [ ] Provider is selected via a `provider` field on the incoming request, falling back to a config default if omitted — never hardcoded in route logic.

---

## Step 5 — `Guardrail` interface + `GuardrailChain`

**File: `guardrails/base.py`**
```python
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel

class GuardrailAction(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    REDACT = "redact"

class GuardrailResult(BaseModel):
    action: GuardrailAction
    guardrail_name: str
    modified_input: str | None = None   # set if action == REDACT
    reason: str | None = None            # set if action == BLOCK

class Guardrail(ABC):
    name: str

    @abstractmethod
    async def check(self, payload: str, context: dict) -> GuardrailResult:
        ...
```
`context` carries request-scoped info like `user_id` so guardrails needing it (rate limiting, cost tracking) don't need a different method signature.

**File: `guardrails/chain.py`**
```python
class GuardrailChain:
    def __init__(self, guardrails: list[Guardrail]):
        self.guardrails = guardrails  # order matters: cheapest first

    async def run(self, payload: str, context: dict) -> tuple[str, list[GuardrailResult]]:
        triggered = []
        current_payload = payload
        for g in self.guardrails:
            result = await g.check(current_payload, context)
            if result.action == GuardrailAction.BLOCK:
                triggered.append(result)
                return current_payload, triggered  # short-circuit
            if result.action == GuardrailAction.REDACT:
                current_payload = result.modified_input
                triggered.append(result)
        return current_payload, triggered
```

**Tasks:**
- [ ] Implement `Guardrail`, `GuardrailResult`, `GuardrailAction` as above.
- [ ] Implement `GuardrailChain` with short-circuit-on-block behavior.
- [ ] Build the chain executor **before** wiring guardrails into the route handler — don't call guardrails directly from `routers/generate.py` as a shortcut, even with just one guardrail. Same effort now, avoids a refactor later.

---

## Step 6 — The three input guardrails

Order in the chain (cheapest/fastest first): **length guard → rate limit → PII detection.**

### 6a. Length / cost guard
**File: `guardrails/length_guard.py`**
```python
class LengthGuard(Guardrail):
    name = "length_guard"
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens

    async def check(self, payload, context):
        estimate = len(payload) // 4  # rough estimate; swap for tiktoken later for precision
        if estimate > self.max_tokens:
            return GuardrailResult(action=GuardrailAction.BLOCK, guardrail_name=self.name,
                                    reason=f"Input exceeds {self.max_tokens} token estimate")
        return GuardrailResult(action=GuardrailAction.PASS, guardrail_name=self.name)
```
- [ ] Implement as above.
- [ ] Confirm oversized prompts are blocked **before** any provider call is made (check this in a test that asserts the mock provider was never invoked).

### 6b. Rate limiting
**File: `guardrails/rate_limit.py`**
```python
class RateLimiter(Guardrail):
    name = "rate_limit"
    def __init__(self, redis_client, max_requests: int, window_seconds: int):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds

    async def check(self, payload, context):
        key = f"rate:{context['user_id']}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window)
        if count > self.max_requests:
            return GuardrailResult(action=GuardrailAction.BLOCK, guardrail_name=self.name,
                                    reason="Rate limit exceeded")
        return GuardrailResult(action=GuardrailAction.PASS, guardrail_name=self.name)
```
- [ ] Implement as above (fixed-window counter — simpler than a true token bucket, good enough for Phase 1; noted as a possible later upgrade for the "what I'd do with more time" section).
- [ ] Wire Redis client from `config/settings.py` (connection string from env var).

### 6c. PII detection (regex baseline)
**File: `guardrails/pii.py`**
```python
PATTERNS = {
    "EMAIL": r'[\w.+-]+@[\w-]+\.[\w.-]+',
    "PHONE": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    "CREDIT_CARD": r'\b(?:\d[ -]*?){13,16}\b',
}

class PIIGuardrail(Guardrail):
    name = "pii_detection"
    def __init__(self, action: GuardrailAction = GuardrailAction.REDACT):
        self.action = action

    async def check(self, payload, context):
        modified = payload
        found = []
        for entity, pattern in PATTERNS.items():
            if re.search(pattern, modified):
                found.append(entity)
                if self.action == GuardrailAction.REDACT:
                    modified = re.sub(pattern, f"[{entity}_REDACTED]", modified)
        if not found:
            return GuardrailResult(action=GuardrailAction.PASS, guardrail_name=self.name)
        return GuardrailResult(action=self.action, guardrail_name=self.name,
                                modified_input=modified if self.action == GuardrailAction.REDACT else None,
                                reason=f"Detected: {', '.join(found)}")
```
- [ ] Implement as above.
- [ ] Confirm both `redact` and `block` action modes work (configurable per rule, see Step 7).
- [ ] Note: Presidio/spaCy for names/addresses is deliberately **out of scope** for Phase 1 — regex only.

---

## Step 7 — Minimal YAML policy engine

Just enough to load rules and instantiate guardrails at startup — no hot-reload yet (that's Phase 3).

**File: `config/policies.yaml`**
```yaml
rules:
  - name: block_pii
    type: input
    guardrail: pii_detection
    action: redact
    entities: [EMAIL, PHONE, CREDIT_CARD]

  - name: length_limit
    type: input
    guardrail: length_guard
    max_tokens: 4000

  - name: rate_limit
    type: input
    guardrail: rate_limit
    max_requests: 20
    window_seconds: 60
```

**File: `config/policy_loader.py`**
```python
def load_guardrail_chain(path: str) -> GuardrailChain:
    config = yaml.safe_load(open(path))
    guardrails = []
    for rule in config["rules"]:
        if rule["guardrail"] == "pii_detection":
            guardrails.append(PIIGuardrail(action=GuardrailAction(rule["action"])))
        elif rule["guardrail"] == "length_guard":
            guardrails.append(LengthGuard(max_tokens=rule["max_tokens"]))
        elif rule["guardrail"] == "rate_limit":
            guardrails.append(RateLimiter(redis_client, rule["max_requests"], rule["window_seconds"]))
    return GuardrailChain(guardrails)
```

**Tasks:**
- [ ] Write `policies.yaml` with the three rules above.
- [ ] Implement `load_guardrail_chain()` mapping rule `guardrail` field → `Guardrail` instance.
- [ ] Load the chain once at app startup (module-level or FastAPI `lifespan` event) — no need for file-watching/hot-reload yet.

---

## Step 8 — Wire up `POST /v1/generate`

**File: `routers/generate.py`**
```python
@router.post("/v1/generate")
async def generate(req: GenerateRequest):
    start = time.perf_counter()
    context = {"user_id": req.user_id}

    processed_prompt, triggered = await guardrail_chain.run(req.prompt, context)
    blocked = any(r.action == GuardrailAction.BLOCK for r in triggered)
    if blocked:
        return GenerateResponse(
            output=None, blocked=True, retries_used=0,
            guardrails_triggered=[r.guardrail_name for r in triggered],
            latency_ms=int((time.perf_counter() - start) * 1000), cost_usd=0.0
        )

    provider = get_provider(req.provider)
    result = await provider.generate(processed_prompt, GenerateParams())

    return GenerateResponse(
        output=result.text, blocked=False, retries_used=0,
        guardrails_triggered=[r.guardrail_name for r in triggered],
        latency_ms=int((time.perf_counter() - start) * 1000),
        cost_usd=0.0  # real cost calc comes in Phase 3
    )
```

**Tasks:**
- [ ] Define `GenerateRequest` and `GenerateResponse` Pydantic models matching the final API contract (`prompt`, `provider`, `user_id` in; `output`, `blocked`, `retries_used`, `guardrails_triggered`, `latency_ms`, `cost_usd` out) — even though `retries_used` and `cost_usd` have no real logic yet, matching the shape now avoids a breaking change to the response format later.
- [ ] Implement the route as above: input chain → (block early return) → provider call → response.
- [ ] No output guardrails yet — that's Phase 2. The raw provider response goes straight back to the client.

---

## Step 9 — Manual verification

Run these two checks yourself before considering Phase 1 done:

**Check 1 — PII redaction + successful generation:**
```bash
curl -X POST http://localhost:8000/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "My email is john@test.com, tell me a joke", "provider": "local", "user_id": "u1"}'
```
Expect: `guardrails_triggered: ["pii_detection"]`, a mock LLM response, `blocked: false`.

**Check 2 — Rate limit enforcement:**
```bash
for i in {1..25}; do
  curl -s -X POST http://localhost:8000/v1/generate \
    -H "Content-Type: application/json" \
    -d '{"prompt": "hi", "provider": "local", "user_id": "u1"}' | jq .blocked
done
```
Expect: the first ~20 return `false`, the rest return `true` with `guardrails_triggered: ["rate_limit"]`.

---

## Step 10 — Unit tests (write alongside, not after)

**Tasks:**
- [ ] `test_pii.py` — assert email/phone/credit-card get redacted; assert clean text passes through unchanged; assert `action=block` mode blocks instead of redacting.
- [ ] `test_length_guard.py` — assert an oversized prompt is blocked; assert one under the limit passes.
- [ ] `test_rate_limit.py` — assert the (N+1)th request in a window is blocked; assert the counter resets after the window expires (use `fakeredis` or a real Redis test container — don't mock away the actual behavior).
- [ ] `test_providers.py` — assert `LocalMockProvider` returns correct output for each `mode`; cheap to write, catches typos before they cost a debugging session in Phase 2.

---

## Explicitly out of scope for Phase 1

Don't start these yet — they belong to later phases and starting early usually leaves Phase 1 half-finished:
- Output guardrails, schema validation, retry/correction loop (Phase 2).
- Circuit breaker (Phase 2).
- Presidio/spaCy-based PII detection (later, if time allows).
- YAML hot-reload (Phase 3).
- Observability layer, metrics, benchmark suite (Phase 3).
- Cost tracking beyond the placeholder `0.0` (Phase 3).

---

## Definition of done

- [ ] `docker-compose up` starts the gateway + Redis with no manual steps.
- [ ] `GET /health` returns 200.
- [ ] `POST /v1/generate` with `provider: "local"` and `provider: "anthropic"` both work by changing only the request field, no code changes.
- [ ] A prompt containing PII gets redacted before reaching the provider, and this is reflected in `guardrails_triggered`.
- [ ] A prompt exceeding the length limit is blocked before any provider call.
- [ ] Exceeding the rate limit for a `user_id` returns `blocked: true`.
- [ ] All four test files pass under `pytest`.
