# 5.1 — Feature-level narrator

> SUPERSEDED by task 8.1 (spec 30) — narration is now a reasoner projection.

**Phase:** 5 — Changelog engine. Depends on 16.2 (the linked change, resolved in episodic memory), Phase 3 (the knowledge store, to retrieve context), Phase 1 (`PromptBuilder`/`OllamaClient`). Closes the phase: a served push becomes feature-level prose.

## Current state

After the episodic resolver (16.2), Herald has a `LinkedChange` (completed tasks + commits). Phase 1's `Summarizer`/`PromptBuilder` turn a `CommitContext` into prose but only from commits — no roadmap anchoring, no project context, and the output reads as a commit log. The knowledge store (Phase 3) holds the project's understanding but nothing queries it for a change.

## Change

Add the narrator that anchors on the delivered tasks, pulls project context from the store, and writes flowing feature-level prose.

- Extend `src/summarization/prompt.py` `PromptBuilder.build` to accept a `LinkedChange` (imported from `src/episodic/linked_change.py`, task 16.2) and retrieved context: render the **completed tasks** as the lead (intent + outcome), the **retrieved context** as background, and the **commits** as supporting detail, with an instruction to write connected feature-level prose (not bullets or a diff). Where `completed_tasks` is empty, fall back to a commit-level digest.
- `src/changelog/narrator.py` — `ChangelogNarrator`:
  - `narrate(change: LinkedChange, dev: bool) -> str` — embed the change (its completed tasks / commit text) via the `Embedder`, `KnowledgeStore.query(embedding, k, repo=change.repo)` for relevant project knowledge, build the prompt, and `OllamaClient.generate`. In dev mode the instruction leans on what recently landed.
- Wire into the ingestion flow (after the serve-allowlist gate and the knowledge sync): on a served push, resolve the `LinkedChange` (16.2) → `narrate` → **log** the prose. Delivery to channels is Phase 7; this task ends at the produced narration.

## Files & types

- edit `src/summarization/prompt.py` (`PromptBuilder.build` takes `LinkedChange` + retrieved context)
- new `src/changelog/narrator.py` (`ChangelogNarrator`)
- edit `src/ingestion/router.py` (resolve → narrate → log on a served push)

## Guards

- Output is connected prose at the feature level — anchored on the completed tasks where present, a commit-level digest otherwise; never a bullet list of raw commits.
- **Single-project** — retrieval is scoped to `change.repo`; cross-project ripple is Phase 6.
- Retrieval failures / an empty store degrade to commits-only narration, never a silent empty string.
- The LLM stays behind `OllamaClient`; timeouts raise.
- `narrator.py` depends on episodic's public `LinkedChange` type — a deliberate one-way exception (episodic → changelog), matching 16.3's guard that `src/episodic/` never imports `src/changelog/` back.

## Verification

- A served push that completes a roadmap task → prose that names the feature that advanced and what it means, drawing on retrieved project context, and is logged.
- A code-only push → a coherent commit-level digest (no fabricated feature).
- Run through the eval harness: the narrator's output for a fixed `{repo, range}` case diffs against its reference note.
