# 15.1 — Conversation endpoint

**Phase:** 15 — Conversational surface. Depends on Phase 7 (the reasoner). First task; the behavioral contract is `docs/spec/conversation.md`.

## Current state

The reasoner (Phase 7) answers a query, but nothing exposes it to a person — `src/main.py` has only `GET /health` and the GitHub webhook. `docs/spec/conversation.md` specifies the contract this task implements: a channel-agnostic request/response surface, stateless (each question self-contained, answered from standing memory rather than conversation history), optionally scoped to a project.

## Change

Add the conversation surface as its own feature package — a thin seam that carries a question to the reasoner and its answer back, with no reasoning of its own.

- `src/conversation/models.py` — `Question` (immutable): `text: str`, `repo: str | None`.
- `src/conversation/router.py` — `APIRouter` with `POST /ask`:
  - accepts `{ "question": str, "repo": str | None }`, parses into a `Question`;
  - calls `Reasoner.answer(question.text, repo=question.repo)` (Phase 7);
  - returns `{ "answer": str }`.
- Wire the router into `src/main.py` (`app.include_router(...)`), constructed at the composition root with the `Reasoner` injected the same way as other seams.

## Files & types

- new `src/conversation/__init__.py`, `src/conversation/models.py` (`Question`), `src/conversation/router.py`
- edit `src/main.py` (include router, inject `Reasoner`)

## Guards

- **Stateless** — no session, no conversation id; each question is answered independently from Herald's standing memory, never from a memory of prior turns (per the doc's "single question, standing memory").
- **No reasoning in the surface** — the router validates input and delegates entirely to `Reasoner`; it holds no retrieval, prompting, or synthesis logic of its own.
- **Channel-agnostic** — a plain request/response seam. A Telegram inbound adapter (15.3, using `TelegramClient`, Phase 9) covers that channel — out of scope here.
- Access control / entitlement tiering (free local vs. paid hosted model) is deferred to the multi-tenant stage (Phase 14); this endpoint is internal/unauthenticated for now.

## Verification

- `POST /ask` with a question about a served project returns prose grounded in its memory.
- A `repo`-scoped question stays focused on that project (reaching its neighbours per Phase 7's cross-project reach where relevant); an unscoped question answers across the ecosystem.
- A question about a project Herald holds no memory for surfaces the reasoner's honest "no memory" answer, never an invented one.
