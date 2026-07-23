# Project Memory — LLM Guardrails Gateway

Purpose: a running log of decisions, open questions, and context so work can be picked back up (by you, a collaborator, or an AI coding assistant) without re-deriving the reasoning behind past choices. Update this file at the end of each work session — treat stale entries as a bug.

---

## How to use this file

- **Decisions Log**: append-only. Once a decision is made, don't delete it — if it's later reversed, add a new entry noting the reversal and why.
- **Open Questions**: things not yet decided. Move to Decisions Log once resolved.
- **Current State**: overwrite this section each session — it should always reflect "where things actually are right now," not history.
- **Gotchas**: anything that cost you real debugging time, so the next session (or the next person) doesn't rediscover it the hard way.

---

## Current State

*(Update at the end of every session.)*

- **Phase**: Not started / Week 1 / Week 2 / Week 3 / Week 4 *(edit as you go)*
- **Last completed**: —
- **Next up**: —
- **Blocking issues**: —

---

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| _(seed)_ | Framework: FastAPI (Python) chosen over Express/Fastify | Async-first, Pydantic gives schema validation for free, matches the target track (backend/systems, not full-stack). |
| _(seed)_ | Two provider adapters only: one real cloud LLM + one local/mock | Non-goal to support every provider on day one; proves the abstraction without extra surface area. |
| _(seed)_ | Rules engine config format: YAML | Human-editable by non-engineers per the core requirement; PyYAML is a one-line dependency. |
| _(seed)_ | Rate limiting: token bucket via Redis | Standard, well-understood algorithm; Redis also reused for circuit-breaker shared state. |
| _(seed)_ | Default circuit-breaker `fail_mode` for security-critical guardrails (PII, injection): `closed` | Availability is less important than not silently letting unsafe content through during an outage. |
| _(seed)_ | Benchmark suite size: ~50-100 attack prompts + ~50 benign edge cases | Enough for a statistically meaningful precision/recall number without turning corpus curation into its own multi-week project. |

*(Add new rows as real decisions get made during implementation — e.g., which PII library was actually used, how the retry correction prompt is templated, what the fallback response text ended up being, etc.)*

---

## Open Questions

- [ ] File-watcher hot-reload vs. explicit `/v1/admin/reload` endpoint for the policy engine — which ships first?
- [ ] Should `policy_overrides` be allowed to disable *any* named rule, or should certain rules (PII, injection) be hard-excluded from override eligibility?
- [ ] Embedding-similarity injection check: build a tiny local corpus + cosine similarity, or skip and rely on heuristics only for v1?
- [ ] Where does the "safe fallback response" text live — hardcoded default, or itself YAML-configurable per rule?
- [ ] Deploy target for the optional live demo link (Render / Fly.io / Railway) — decide only once core functionality is solid.

---

## Gotchas / Lessons Learned

*(Empty until real implementation surfaces something. Examples of the kind of thing that belongs here: "Presidio's default model misses phone numbers without a country code prefix — added a regex fallback"; "circuit breaker half-open probe was double-counting failures because two requests raced into the probe simultaneously — added a lock.")*

---

## Reference Map (where things live once built)

| Concern | Expect to find it in |
|---|---|
| Guardrail base interfaces | `design.md §1` |
| Rule/YAML schema | `rules.md` |
| Request/response contract | `README.md` API section, mirrored from spec §6 |
| Roadmap / what's done vs. not | `phases.md` |
| High-level system flow | `architecture.md` |
