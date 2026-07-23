# Rules Reference — Policy Engine (YAML)

This document is the authoritative reference for writing guardrail rules. Non-engineers should be able to change gateway behavior by editing this file alone — no code changes required.

## 1. File Location & Reload

- Default path: `./config/rules.yaml`
- Hot-reload: either a file-watcher picks up changes automatically, or `POST /v1/admin/reload` triggers a manual reload (pick one to build first; file-watcher is the stretch version).
- Invalid YAML or an unknown rule `type` fails the reload safely — the gateway keeps running on the last-known-good config and logs an error, it never crashes on a bad edit.

## 2. Rule Schema

```yaml
rules:
  - name: <string, unique>          # required
    type: input | output            # required — which chain this rule runs in
    action: block | redact | retry  # required — see Action Types below
    # -- action-specific fields below --
```

## 3. Action Types

| Action | Valid stage | Behavior |
|---|---|---|
| `block` | input, output | Short-circuits the chain immediately; client receives the safe fallback response. |
| `redact` | input only | Mutates the payload (e.g., replaces PII with `[REDACTED_EMAIL]`) and continues the chain. |
| `retry` | output only | Triggers the Retry/Correction Loop instead of an immediate block; falls back to `block` behavior once `max_retries` is exhausted. |

## 4. Built-in Rule Types

### 4.1 `block_pii` (input, action: `redact` or `block`)

```yaml
- name: block_pii
  type: input
  action: redact
  entities: ["EMAIL", "PHONE", "CREDIT_CARD", "SSN"]
```

- `entities` — which PII categories to detect. Backed by regex for structured patterns (email, phone, credit card, SSN) and optionally spaCy/Presidio for names/addresses.

### 4.2 `injection_detection` (input, action: `block`)

```yaml
- name: injection_detection
  type: input
  action: block
  patterns: ["ignore previous instructions", "disregard the system prompt"]
  embedding_check: true          # optional, fuzzy match against known-attack corpus
  similarity_threshold: 0.85     # only used if embedding_check is true
```

### 4.3 `rate_limit` (input, action: `block`)

```yaml
- name: rate_limit
  type: input
  action: block
  requests_per_window: 20
  window_seconds: 60
  scope: user_id | api_key
```

### 4.4 `length_guard` (input, action: `block`)

```yaml
- name: length_guard
  type: input
  action: block
  max_input_tokens: 4000
```

### 4.5 `require_json_schema` (output, action: `retry`)

```yaml
- name: require_json_schema
  type: output
  action: retry
  schema: "./schemas/response.json"
  max_retries: 2
```

### 4.6 `toxicity_filter` (output, action: `block`)

```yaml
- name: toxicity_filter
  type: output
  action: block
  threshold: 0.7
  provider: local | external_api
```

### 4.7 `no_competitor_mentions` (output, action: `block`) — example of a custom topic/policy rule

```yaml
- name: no_competitor_mentions
  type: output
  action: block
  patterns: ["CompetitorX", "CompetitorY"]
  semantic_check: false   # optional: also catch paraphrased mentions
```

## 5. Circuit Breaker Config (attached to any rule backed by a slow/external dependency)

```yaml
- name: toxicity_filter
  type: output
  action: block
  provider: external_api
  circuit_breaker:
    failure_threshold: 5     # consecutive failures before tripping
    window_seconds: 30
    cooldown_seconds: 15     # time before a half-open probe
    fail_mode: closed        # 'open' = skip check & pass; 'closed' = block while tripped
```

Default recommendation: `fail_mode: closed` for anything security-critical (PII, injection); `fail_mode: open` acceptable for softer checks (e.g., topic enforcement) where availability matters more than strict enforcement — but this must be a conscious choice per rule, not a blanket default.

## 6. Request-Level Overrides

Clients may reference `policy_overrides` in the `/v1/generate` request to **disable specific named rules** for that call only:

```json
{
  "prompt": "...",
  "policy_overrides": ["no_competitor_mentions"]
}
```

- Overrides can only reference existing rule names already defined in YAML — clients can never inject new rule logic at request time. This boundary is deliberate and should not be relaxed.
- Consider gating which rules are override-able at all (e.g., `PIIGuardrail` and `injection_detection` should probably never be disable-able via request override, even if listed).

## 7. Full Example: `config/rules.yaml`

```yaml
rules:
  - name: block_pii
    type: input
    action: redact
    entities: ["EMAIL", "PHONE", "CREDIT_CARD"]

  - name: injection_detection
    type: input
    action: block
    patterns: ["ignore previous instructions", "you are now"]
    embedding_check: true
    similarity_threshold: 0.85

  - name: rate_limit
    type: input
    action: block
    requests_per_window: 20
    window_seconds: 60
    scope: user_id

  - name: length_guard
    type: input
    action: block
    max_input_tokens: 4000

  - name: require_json_schema
    type: output
    action: retry
    schema: "./schemas/response.json"
    max_retries: 2

  - name: toxicity_filter
    type: output
    action: block
    threshold: 0.7
    provider: local
    circuit_breaker:
      failure_threshold: 5
      window_seconds: 30
      cooldown_seconds: 15
      fail_mode: closed

  - name: no_competitor_mentions
    type: output
    action: block
    patterns: ["CompetitorX", "CompetitorY"]
```

## 8. Adding a New Guardrail Type (for engineers)

1. Implement the `Guardrail` interface (`design.md §1.2`) with a unique `name` and `stage`.
2. Register the class in the Policy Engine's rule-type registry (a simple `dict[str, type[Guardrail]]` keyed by YAML `type`/rule name pattern is enough — no need for plugin discovery machinery at this scope).
3. Add the new rule to `rules.yaml` — no other code changes required. This is the practical proof of the pluggable-architecture claim (spec §4.2.4).
4. Add corresponding attack/benign prompts to the benchmark suite if the rule is detection-oriented, so its precision/recall is measured, not just assumed.
