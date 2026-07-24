# 8.1 — Reasoner narrate

**Phase:** 8 — Narration (the broadcast projection). Depends on 7.1 (retrieval), 7.2 (cross-project reach), 4.2 (the resolved `LinkedChange`).

## Current state

The reasoner (Phase 7) answers free-text queries, retrieving from both memories and folding in cross-project neighbors. Broadcast narration would otherwise duplicate that work through three separate mechanisms: the old standalone narrator (semantic-memory-only, its own `LLMClient` call — spec 12, superseded), old neighbor discovery (spec 13, superseded), and old forest narration (spec 14, superseded — folding neighbors into the narrator's prompt). All three exist to do, change-shaped, what the reasoner already does query-shaped.

## Change

Add a narration entry point to the reasoner that reuses its existing retrieval and cross-project machinery, framed for narration instead of Q&A.

- `src/reasoning/reasoner.py` — `Reasoner.narrate(change: LinkedChange, lang: str = "ru") -> str`:
  - build a retrieval query from `change.completed_tasks` (`tuple[str, ...]` of done-marker identifiers, `src/episodic/linked_change.py:22`) **and** the commit messages in `change.commits` (a `CommitContext`; each `Commit.message`, `src/commits/models.py`) — neither source dropped when the other is empty;
  - reuse 7.1/7.2's **shared internal retrieval+neighbor step** — the same `_gather_context(query, repo)`-style helper `answer` calls (embed once → `KnowledgeStore.query` semantic + `EpisodicStore.query` episodic → 7.2 neighbor folding), scoped to `change.repo` (the bare `push.repo` key, `linked_change.py:21`), with the same injected `Settings.reasoner_k`. `narrate` consumes that helper's **context** and then builds its own prompt — it does **not** call `answer` (which returns finished Q&A prose, not context);
  - build a **narration** prompt (not the Q&A prompt `answer` uses) in `lang`: completed tasks as the lead (intent + outcome), commits as supporting detail, cross-project ripple framed as "unblocks" where neighbors were found;
  - `LLMClient.generate(prompt)`.
  - Where `completed_tasks` is empty, the prompt falls back to a commit-level digest (same discipline the old narrator had).
  - `lang` restores the language dimension the superseded narrator had via `PromptBuilder.build(context, lang)` — the default `"ru"` serves any caller that passes no language. `narrate` has **no per-push call site** (a served push is memory-only); its callers are the report sections (`SummarySection`/`PerBranchSection`, 10.1.2), which serve both the report cadence (Phase 10) and the release note (11.2.2). Per-language generation is the localizer's concern (`report_notes`), not `narrate`'s.

## Files & types

- edit `src/reasoning/reasoner.py` (`Reasoner.narrate`, gains `lang`)
- register a `narrate` case-type handler in the eval-harness registry (5.2 / spec `52`) — builds a `{repo, range}` case into a `LinkedChange` (via `LinkedChangeResolver`) and runs `narrate`, so the harness verification below is a real registered case, not a manual check

## Guards

- **No second retrieval or neighbor mechanism** — `answer` and `narrate` share **one** internal retrieval+neighbor step (e.g. `_gather_context(query, repo)`); they differ only in the prompt built after it. This requires 7.1.2/7.2 to factor retrieval+neighbor folding into that reusable helper rather than inlining it in `answer`; `narrate` neither re-implements it nor calls `answer` (whose output is finished prose).
- **The retrieval query is built from both `completed_tasks` and commit messages** — this is new surface 7.1.1's contract doesn't cover (it takes a query string directly). When `completed_tasks` is empty, the commit messages still drive retrieval; neither source is silently dropped from the query regardless of which is empty. Mockable without a real LLM — assert on the constructed query text (or the embedder's input) directly.
- Output is prose at the feature level — never bullets or a raw diff.
- Anchored on `completed_tasks` where present; a commits-only digest otherwise.
- Cross-project ripple appears only where 7.2's neighbor folding actually surfaces a neighbor; otherwise the note stays single-project.
- **The change's own commits are the floor** — `change.commits` is always present, so `narrate` never returns empty. Degradation ladder: full context (both stores + neighbors) → a surviving store's context (per 7.1's per-store failure isolation) → a commits-only digest when retrieval yields nothing usable or `completed_tasks` is empty. Retrieval/neighbor context is additive; its absence never fails the note.
- Model-agnostic — `LLMClient` via the existing DI, unchanged from 7.1; entitlement tiering is still Phase 14's concern.

## Verification

- A push completing a roadmap task → prose naming the feature that advanced and (where a neighbor surfaces via retrieval or the graph) what it unblocks elsewhere.
- A change with completed tasks → the constructed retrieval query includes the task text.
- A commits-only change (no `completed_tasks`) → the constructed retrieval query still includes the commit messages — retrieval is never starved by an empty task list.
- A code-only push → a coherent commit-level digest, no fabricated feature.
- An isolated change (no neighbors) → a single-project note.
- A mocked store-retrieval failure → the note still renders from the change's commits (and any surviving store), never empty — the commits-only floor holds.
- Run through the eval harness: `narrate`'s output for a fixed `{repo, range}` case diffs against its reference note.
