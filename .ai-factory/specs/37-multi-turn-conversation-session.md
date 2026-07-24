# 15.2 — Multi-turn conversation session

**Phase:** 15 — Conversational surface. Depends on 15.1 (`/ask`), Phase 7 (`Reasoner.answer`). After 15.1.

## Current state

15.1's `POST /ask` is stateless by design (per `docs/behavior/conversation.md`'s "single question, standing memory") — each question is answered independently, with no memory of prior turns in the same conversation. A user asking a natural follow-up ("what about its dependencies?") gets an answer with no idea what "its" refers to.

## Change

Add optional session support at the conversation surface — the reasoner itself stays single-shot; the surface manages turn history and folds it into the query it sends.

- `src/conversation/models.py` — extend `Question` (or add a sibling) to accept an optional `session_id: str | None`.
- `src/conversation/session.py` — a session store (in-memory for now, e.g. `dict[session_id, list[turn]]`): `append_turn(session_id, question, answer)`, `history(session_id) -> list[turn]`.
- `src/conversation/router.py` — `POST /ask` with a `session_id`: fetch the session's prior turns, prepend them as context when building the query passed to `Reasoner.answer` (Phase 7) — e.g. folded into the `query` text itself, since `Reasoner.answer`'s signature does not change — then append the new turn to the session's history.
- No `session_id` → identical behavior to 15.1 (fully stateless).

## Files & types

- edit `src/conversation/models.py` (`Question.session_id`)
- new `src/conversation/session.py` (session store)
- edit `src/conversation/router.py` (session-aware `/ask`)

## Guards

- **The reasoner is unchanged** — `Reasoner.answer`'s signature and internals stay exactly as Phase 7 built them; all history-awareness lives in the conversation surface, not the reasoner.
- History is **bounded** — last-N turns or a token budget, never an unbounded transcript folded into every query.
- The session store is **in-memory** for now — persistent/durable sessions are a later concern, not this task's.
- A request with no `session_id` behaves exactly as stateless 15.1 — this task adds a capability, it does not change the default path.

## Verification

- Two `/ask` calls sharing a `session_id`, the second a natural follow-up ("what about X's dependencies?") → answered using context from the first turn.
- A request with no `session_id` → behaves identically to 15.1 (no history involved).
- A session's history beyond the bound (last-N / token budget) does not grow unbounded across many turns.
