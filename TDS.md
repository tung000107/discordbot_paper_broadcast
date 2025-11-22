# Discord Research Assistant — Technical Design Spec

This document is the single source of truth for implementing the Discord Research Assistant (DRA). Every `.spec`/`.entry` file under `src/` is scoped and summarized here.

---

## 0. Goals
- Discord bot that ingests arXiv or conference links, returns structured Zh-Hant summaries, streams intermediate results, and delivers PDF reports.
- Monthly push of most cited/impactful papers across arXiv + major conferences (ICLR, NeurIPS, ACL, CVPR) grouped by topic.
- Non-functional targets: multi-model collaboration, aggressive caching/cost control, low-latency streaming, Docker-based deployment, rich observability.

## 1. Architecture Overview
```
Discord ↔ Bot Service ─┬─ LLM Service (OpenAI/vLLM API)
                        ├─ Retriever (arXiv / Semantic Scholar / Conferences)
                        ├─ PDF Exporter
                        ├─ Redis Cache
                        └─ Scheduler (Monthly Push)
```
- Interaction + orchestration rules live in `src/bot/main.entry`.
- Contracts for LLM stages are in `src/llm/*.spec`.
- Data acquisition specs reside in `src/retriever/*.spec`.
- Output formatting and scheduling instructions are under `src/exporter` and `src/scheduler`.

## 2. Target Directory Structure (Spec-only)
See `README.md` for the filesystem map. All `.spec`/`.entry` files describe inputs/outputs, validation, and failure policies without executable code.

## 3. Configuration (.env)
Environment variables, defaults, and typing rules are defined in `src/config/settings.spec`. Required keys: `DISCORD_TOKEN`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`. Optional knobs include `OPENAI_MODEL_PRE`, `OPENAI_MODEL_VAL`, `LLM_TEMPERATURE`, `LLM_MAX_OUTPUT_TOKENS`, `REDIS_URL`, `MONTHLY_PUSH_CRON`, `S2_API_KEY`, `TIMEZONE`. Example values live in `.env.example`.

## 4. Data Contracts
| Flow | Spec file | Description |
| --- | --- | --- |
| Discord message parsing | `src/bot/events/message_create.spec` | Emits `arxiv_link_detected` events with IDs, channel/user metadata. |
| arXiv retriever | `src/retriever/arxiv.spec` | Defines request by ID and normalized metadata response. |
| Semantic Scholar citations | `src/retriever/s2.spec` | Describes citation enrichment and caching. |
| Conference ingestion | `src/retriever/conference.spec` | Aligns third-party sources with internal fields. |
| LLM pipeline | `src/llm/pipeline.spec` | Stage A (pre-sanitizer) → Stage B (main summarizer) → Stage C (validator) JSON payloads. |
| PDF exporter | `src/exporter/pdf.spec` | Template inputs, PDF generation output contract, retry policy. |
| Scheduler ranking | `src/scheduler/monthly_push.spec` | Input filters, ranking weights, embed packaging. |
| Manual / admin commands | `src/scheduler/commands.spec` | Slash-command formats, auth rules, audit events. |

## 5. Cache & Cost Control
- Namespace: `dra:*`. Key taxonomy in `src/config/settings.spec`.
- Cache lifetimes: metadata 7d, summaries/PDFs 30d, citation rollups 7d, rate-limit windows sliding.
- Cost metrics: `tokens_in`, `tokens_out`, `cost_estimated`, `model`, `duration_ms`, `cache_hit` recorded per request and daily aggregate (see `src/telemetry/metrics.spec`).

## 6. Streaming Design
- LLM emits chunks `{section, partial_text, progress}` via stream adapter spec (`src/bot/utils/stream_adapter.spec`).
- Bot updates Discord embeds with intro/background/method/conclusion fields; capped edits per Discord API; fallback to appended messages.
- Completion attaches PDF or download link plus optional admin-only cost breakdown.

## 7. Scheduler
- Cron from `MONTHLY_PUSH_CRON`, timezone default `Asia/Taipei`.
- Ranking priority: citations → recency → topic weight. Failure fallback to previous month.
- Posts multiple embeds (≤5 papers each) with summaries + links.

## 8. Validation & Quality Gates
- JSON schema enforcement for all Stage outputs (`src/llm/validators/schema.spec`).
- Sentence count, Traditional Chinese language check, hallucination guard rails, and retry logic documented in `src/llm/validators/rules.spec`.
- PDF field length limits (Embed safe limits) described in `tests/pdf_export.spec`.

## 9. Error Handling Matrix
- Detailed handling per failure type captured inside each component spec plus consolidated table in `src/config/logging.spec`.
- Key downgrades: parser usage hints, retriever retry/downgrade, validator low-temp reruns, heuristic summary fallback, PDF text-only fallback, scheduler fallback to previous month.

## 10. Observability
- Structured logs with `trace_id`, `user_id`, `channel_id`, `stage`, `latency_ms`, `tokens_in/out`, `cache_hit`, `error_code`.
- Metrics: Stage latency percentiles, token cost, retriever success, PDF timings, scheduler success (see `src/telemetry/metrics.spec`).
- Tracing spec enumerates span names and propagation fields (`src/telemetry/tracing.spec`).

## 11. Security & Privacy
- No long-term storage of Discord DM content (≤24h TTL if needed for debugging).
- Remove PII from PDFs; limit stored data to paper content + metadata.
- API keys injected via environment only; never logged.

## 12. Deployment (Docker Compose)
- `docker-compose.yml` defines `bot`, `redis`, optional `vllm` services, health checks, shared `dra-net`.
- Bot depends on Redis and (optionally) vLLM; vLLM exposes OpenAI-compatible `/v1` endpoints; Redis uses persistent volume `redis-data`.

## 13. Testing Strategy
- Unit: parser, retriever, validators, pdf field rules.
- Integration: end-to-end summarize flow with mock LLM.
- Load: 10 & 50 concurrent summarize invocations, track P95 latency/error rate.
- Regression: monthly push ranking determinism.

## 14. Risks & Mitigations
- API changes → abstracted retriever + feature flags.
- Cost overrun → cache-first, downgrade models once budget hit.
- Long abstracts → PDF deep-read router (future) + enforced output limits.

## 15. Definition of Done
- `/summarize` streams within 8 seconds and emits PDF.
- `/top-papers` covers arXiv + ≥1 conference source with topic grouping embeds.
- Cost dashboard JSON ready for admins per day.
- >90% coverage on critical code paths plus passing E2E regressions.

## 16. Non-goals
- No PDF/OCR figure understanding, no personalized recs, no automatic external archiving (temp storage only).

## 17. Prompt Schema Snapshot
- Stage B prompt structure preserved in `src/llm/prompts/main_summary.prompt.json` (Zh-Hant, JSON-only response).
- Validator ensures `bullet_points` length 3–5, sections 2–4 sentences, Traditional Chinese text, characters < 900 per section.
