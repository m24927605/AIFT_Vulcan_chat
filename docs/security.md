# Security Controls

The system implements defense-in-depth security across six layers: transport, session, API, LLM input, LLM output, and operational observability.

## Layer 1: Transport & Browser Hardening

- CORS restricted to the configured `FRONTEND_URL` only; `localhost:3000` is added exclusively when `API_SECRET_KEY` is empty (dev mode).
- All responses include security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (deny camera/mic/geo), and `Strict-Transport-Security` (HTTPS only).
- `API_SECRET_KEY` is required in production. If it is empty outside local development, the web server refuses to start.

## Layer 2: Session & Authentication

- Web conversations are protected by server-managed `HttpOnly` session cookies (`vulcan_session`) stored in the `web_sessions` table — not browser-managed auth tokens.
- Sessions are bound to user-agent hash + IP prefix. Mismatched fingerprints are rejected immediately.
- Sessions rotate every 24 hours. Rotation migrates all owned conversations and analysis tasks to the new session ID atomically.
- Orphan conversations (no owner) can only be auto-claimed if the requesting session's linked Telegram chat ID matches the conversation's Telegram chat ID — preventing strangers from claiming conversations by guessing UUIDs.

## Layer 3: API Protection

- State-changing routes require CSRF double-submit validation: the `X-CSRF-Token` header must match the `csrf_token` cookie (constant-time comparison), and the `Origin` header must match the configured frontend URL.
- Rate limiting is enforced per-endpoint (`/api/chat` and `/api/analysis` each get an independent 30 req/min per-IP bucket) and persisted in SQLite, remaining effective across process restarts and multiple instances.
- Admin notification endpoints require `X-API-Key` backed by `API_SECRET_KEY`.
- Telegram linking requires a one-time 8-digit code hashed with HMAC-SHA256, with 10-minute expiry, a 5-attempt limit, and Telegram-side possession proof.
- Analysis task ownership is persisted in SQLite with default-deny: unknown or unowned task IDs return 403, not the task result.

## Layer 4: LLM Input Hardening (Prompt Injection Defense)

- **Search result sanitization**: Before the Executor sees any search result, content is scanned for prompt injection patterns (`ignore.*instructions`, `reveal.*system prompt`, `exfiltrat`, `tool instructions`, `api_key`, `secret`, `token`) and matches are replaced with `[filtered]`.
- **Schema extraction**: Raw search result text is never passed to the LLM. Instead, results are normalized into a constrained schema (`source_kind`, `title`, `publisher`, `published_at`, `excerpt`, `facts[]`, `numbers[]`) with strict length limits (title: 300 chars, content: 4000 chars, max 3 facts, max 5 numbers).
- **Prompt boundary enforcement**: All agent system prompts explicitly instruct the LLM to treat search results, citations, and conversation history as untrusted data — never following instructions embedded within them.
- **Deterministic fast-paths**: Greetings and simple arithmetic bypass the LLM entirely (AST-based math evaluator), eliminating prompt drift risk for these categories.

## Layer 5: LLM Output Hardening (Data Exfiltration Defense)

- **Secret egress guard**: Before every response chunk is sent to the client, it is scanned for secret-like patterns — OpenAI keys (`sk-*`), session tokens (`sess-*`), base64 blobs (32+ chars), API key assignments (`api_key=...`), and bearer tokens. Matches are replaced with `[REDACTED: sensitive content removed]`.
- **Verifier Agent**: After the Executor generates an answer (when search results are present), the Verifier Agent independently checks every number, statistic, and percentage against the original sources. This catches hallucinated data that could mislead users, and surfaces a confidence score and issue list via the `verification` SSE event.
- **Shared secure answer pipeline**: Both `/api/chat` (streaming) and `/api/analysis` (async deep analysis) share the same `secure_answer_pipeline` module (`app.core.pipelines.secure_answer`), ensuring identical security controls — refusal gate, `guard_model_output` on every chunk, and Verifier Agent cross-check. This prevents security drift between the two code paths.
- **Temporal refusal gate**: When a query requires up-to-date information (temporal/stock/forex) but search returns no results, the system refuses with a localized message instead of falling back to potentially stale LLM knowledge. The refusal message is localized (Chinese for CJK queries, English otherwise).

## Layer 6: Operational Security & Observability

- **Log secret redaction**: Server logging applies `SecretRedactionFilter` to all log output, catching Telegram bot tokens, bearer tokens, `sk-*` keys, session tokens, and API key assignments before they reach stdout.
- **Langfuse LLM tracing**: Every Planner, Executor, and Verifier call is traced with input, output, latency, token usage, and model metadata. Traces degrade gracefully (no-op) when Langfuse keys are absent.
- **Request ID correlation**: Every request gets a unique ID (auto-generated or forwarded via `X-Request-ID`), injected into all log records and returned in the response header for end-to-end tracing.
- **Rate limit IP source**: Rate limiting uses the direct connection IP only — `X-Forwarded-For` is ignored because it is user-controlled and can be spoofed to bypass limits.

## Adversarial Testing (Red Team)

The project includes an automated adversarial testing pipeline (`evals/adversarial_dataset.json`) with 28 attack cases across 8 categories, validated by the `tests/evals/test_adversarial.py` test suite:

| Category | Count | What It Tests |
|----------|-------|---------------|
| Jailbreak | 3 | DAN prompts, role-play override attempts |
| Prompt Leaking | 4 | System prompt extraction, chain-of-thought leaking |
| Instruction Override | 3 | "Ignore previous instructions" variants |
| Data Exfiltration | 4 | API key extraction, bearer token probing |
| Indirect Injection | 4 | Malicious instructions embedded in search results |
| Encoding Bypass | 3 | Mixed-case evasion, Unicode obfuscation |
| Output Attack | 4 | Secret patterns in model output (sk-*, sess-*) |
| Benign (control) | 3 | Legitimate queries that must NOT be filtered |

**Automated test assertions:**
- `TestInputSanitization`: Injection patterns in search results are caught and replaced with `[filtered]`
- `TestOutputGuard`: Secret-like patterns in model output are redacted before reaching the client
- `TestBenignInputsNotFiltered`: Legitimate queries pass through sanitization unaltered
- `TestPlannerResilience`: The Planner does not follow injected instructions in user messages
- `TestAdversarialReport`: Coverage validation — at least 25 cases across at least 5 categories

## Planner Evaluation

A 20-case evaluation dataset (`evals/planner_eval_dataset.json`) covers 8 query categories (Taiwan stocks, US stocks, forex, temporal, factual, conversational, greeting, math) and measures three accuracy dimensions:
- `needs_search_accuracy`: Was the search/no-search decision correct?
- `query_type_accuracy`: Was the query classified correctly (temporal/factual/conversational)?
- `data_source_accuracy`: Were the correct data sources routed (Fugle/Finnhub/none)?

Run with `python -m evals.run_planner_eval` (live) or `--dry-run` (dataset stats only).

## Security Notes

- Anonymous sessions provide owner isolation for browser conversations, but they are not a substitute for full user-account authentication.
- Schema extraction reduces prompt-injection risk significantly, but it is still a pragmatic control, not formal information-flow isolation.
- The adversarial test suite covers known attack categories but is not exhaustive; the dataset should grow as new attack vectors emerge.
