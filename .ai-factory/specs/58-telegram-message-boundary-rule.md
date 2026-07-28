# 19.3 — Pin the Telegram message-boundary counting rule in the governing spec

**Phase:** 19 — Boundary representation mismatches. Independent of 19.1 and 19.2. 19.4 depends on this landing first.

## Current state

The delivery behavioral spec states no rule for how Telegram's 4096-unit message limit is counted — a search of the document confirms it mentions neither the limit nor any counting unit. The Bot API itself counts in UTF-16 code units. The completed task spec for the Telegram client compounds the gap: it describes splitting "on the character boundary" and calls 4096 a "per-message character limit," and that wording is the origin of the defect the sibling tasks in this phase close in code.

## Change

State the counting rule in the delivery spec's Telegram section: the limit itself, the unit it is counted in, and the guarantee that a message over the limit is split into ordered parts whose concatenation equals the original.

## Files & types

- edit `docs/behavior/delivery.md` (the Telegram section)

## Guards

- Documentation only — no `src/` or `tests/` file changes as part of this task.
- Present tense, stating behavior as it is meant to work, per this project's documentation style.
- The completed Telegram-client task spec is not rewritten — it is history, and the governing spec now supersedes its wording rather than matching it.
- This task blocks 19.4: the counting rule is pinned in the spec before the chunker is changed to follow it, never the reverse.

## Verification

- The delivery spec states the message limit, the unit it is counted in, and the splitting guarantee, unambiguously enough that a chunking implementation can be checked against it.
- Nothing under `src/` or `tests/` changes as part of this task.
