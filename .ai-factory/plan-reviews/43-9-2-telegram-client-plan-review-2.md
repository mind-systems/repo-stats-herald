## Plan Review Summary

**Plan:** 9.2 — Telegram client (`43-9-2-telegram-client.md`)
**Files the plan touches:** 6 (2 source, 1 config example, 3 test)
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap alignment (WARN → none):** The plan maps cleanly to `ROADMAP.md:92` (`9.2 — Telegram client`) and its `Spec: .ai-factory/specs/15-telegram-client.md`. Every roadmap contract element is honored: `Settings.telegram_bot_token`, `src/delivery/telegram.py` (`TelegramClient.send(chat_id, text)`), httpx → Bot API `sendMessage`, plain text (no `parse_mode`), over-length chunked in order at `TELEGRAM_MESSAGE_LIMIT = 4096` with `join == original`, token-from-env-only, `raise_for_status` mirroring `OllamaClient`, chunk-not-truncate. No missing linkage.
- **Governing spec (`specs/15-telegram-client.md`):** Full coverage. The plan's Phase 3 mandatory chunking test matches the spec's silent-failure guard verbatim (mocked transport, captured POST bodies, ordered parts, exact concatenation, written before/around the impl). Verification items (`send("hello")` posts once; >4096 → ordered parts, join == original; bad token raises) are all reflected as concrete test cases.
- **Architecture (`CLAUDE.md` / patterns):** Consistent. `TelegramClient.__init__(token, timeout)` takes primitives and is wired at the composition root — matching "Wire concretes only at the composition root" and the `OllamaClient(base_url, ...)` precedent. HTTP/URL specifics stay inside the class ("Owned details stay inside the owning class"). Token comes only from `Settings` ("Secrets and host details come only from env"). New `src/delivery/` feature package follows the existing per-feature package convention.
- **Rules:** No `.ai-factory/RULES.md` or `aif-review` skill-context file present in the repo; no project-specific overrides to apply.

### Critical Issues

None. The plan's codebase assumptions were verified against ground truth and all hold:

- **`Settings` field precedent** — `src/core/config.py:19` has `github_webhook_secret: str` as a required, no-default field; the plan's `telegram_bot_token: str` mirrors it exactly. `model_config` reads `env_file=".env"` (only git-ignored `.env.dev` exists locally), confirming the plan's reasoning that tests must supply the token explicitly rather than rely on an `.env` backfill.
- **Test-breakage analysis is complete and correct.** A repo-wide grep for `Settings(` construction confirms exactly two live materialization paths: (1) `get_settings()` → `Settings()` at `config.py:85`, reached in tests only through the `client` fixture → `app` lifespan, whose sole env-priming site is the `webhook_secret_env` fixture (`tests/conftest.py:19`); and (2) the one direct construction at `tests/routing/test_role_for_branch.py:25` (`Settings(github_webhook_secret="x")`). The only other `Settings(` grep hit is a docstring in `src/github/mirror.py:30`, not real code. Both real sites are addressed by the plan and no third site exists — the plan's "exactly this one test site" claim is accurate.
- **`OllamaClient` references are accurate.** `src/llm/client.py` confirms the transport discipline the plan mirrors: a single `async with httpx.AsyncClient(timeout=self._timeout) as client:`, `client.post(url, json=...)`, then `response.raise_for_status()`. The plan's "one client for the whole send, post each chunk sequentially" instruction is faithful and correct.
- **`.env.example`** currently has `GITHUB_WEBHOOK_SECRET=` (empty, per-env) and no Telegram entry — the plan's addition is needed and non-duplicative.
- **pytest-asyncio** is configured `asyncio_mode = "auto"` (`pyproject.toml:22`), so the plan's async tests need no decorator — consistent with existing async tests (e.g. `tests/episodic/test_episodic_store_contract.py`).
- **API usage** — URL `https://api.telegram.org/bot{token}/sendMessage` and JSON body `{"chat_id", "text"}` with no `parse_mode` match the Bot API and the spec's plain-text mandate.
- **Chunking test math** is sound: `4096*2 + 123 = 8315` → parts of `4096, 4096, 123` → `len(parts) == 3`, so `len(parts) >= 3` and all parts `≤ 4096` hold; the empty-string edge (`_chunks("") == [""]`, still one POST) is explicitly handled.

### Positive Notes

- The plan correctly resolves the concrete-only design tension: spec 15 says "behind a boundary so the delivery backend could swap," and the downstream 9.3 contract (`ROADMAP.md:93`) pins "single concrete class, no ABC" for the delivery feature. The plan implements a single concrete `TelegramClient` with no premature ABC, consistent with that later directive while still honoring the module-boundary intent.
- Task dependencies (`Task 2 depends on 1`, `3 on 1`, `4 on 3`, `5 on 4`) are explicit and correctly ordered; the test-before-impl discipline for the silent-failure surface is preserved.
- The empty-string and at-limit boundary behaviors of `_chunks` are pinned in prose, closing the ambiguity an implementer would otherwise have to guess.

## Deferred observations

- Affects: Phase 9 / `specs/15-telegram-client.md` — The spec and roadmap both mandate splitting on the Python "character boundary," but Telegram's 4096 limit is counted in UTF-16 code units; a message dense in astral-plane characters (emoji, some CJK extensions) could produce a part whose Python `len` is ≤ 4096 yet exceeds Telegram's UTF-16 count, causing the API to reject it. This is a governing-spec decision, not a plan defect — the plan faithfully implements the spec as written — and is out of scope for this task. Flagging only so a future delivery-hardening pass can decide whether the limit should be measured in UTF-16 units. [routed → .ai-factory/specs/58-telegram-message-boundary-rule.md]

PLAN_REVIEW_PASS
