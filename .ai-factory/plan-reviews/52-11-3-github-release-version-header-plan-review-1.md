## Code Review Summary

**Artifact reviewed:** Plan `52-11-3-github-release-version-header.md` (Phase 11.3 — GitHub release + version header)
**Files cross-checked:** 12 (plan, spec `21-github-release.md`, ROADMAP line 11.3, and every code file the plan touches or calls into)
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap alignment — OK.** The plan's `# Plan:` heading maps cleanly to ROADMAP.md line 11.3 (Phase 11, last unchecked task above the stop). Scope matches the contract line: extend `DeliveryPlan`, resolve the language union once, cut the GitHub release, head the Telegram message, all in one isolated background task that `mirror.ensure`s first. The 12.1/12.2 changelog-app leg is correctly held dormant (order 11.3 < 12.1).
- **Spec alignment (`21-github-release.md`) — OK.** Every clause of the spec is represented: one `report_notes` call per push; `target_commitish=event.after`; role→prerelease via `role_for_branch` in one place; `None` version cuts nothing; `config` failure degrades to the fixed union; `owner=event.org_login`; installation token via `GitHubAppAuth.token(org_id)`; `X-GitHub-Api-Version: 2022-11-28`; single isolated background task; caller-side `mirror.ensure` first. The plan's `org_id`-first parameter addition to `create` is a documented, justified deviation from the spec's parameter list (the token mint needs it) — verified against `GitHubAppAuth.token(org_id)`.
- **Architecture (`ARCHITECTURE.md`) / thin-router — OK.** Placing `_deliver_release` as a module-level function in `src/ingestion/router.py` (rather than a new service file) is explicitly mandated by the spec ("local values inside the single staging/release handler", "Files & types lists no new service file"). The plan constrains the router to sequencing + set-math + the `config` try/except, keeping concretes wired only at the composition root — consistent with the feature-modular / composition-root pattern. No boundary violation.
- **RULES.md — OK.** No explicit convention violations found.
- **Skill-context — N/A.** No `.ai-factory/skill-context/aif-review/SKILL.md` present.

### Correctness verification (ground-truth checks)

Every API the plan assumes was confirmed against the live code:

- `DeliveryPlan` is `@dataclass(frozen=True, slots=True)`; adding `github_release_language: str = "en"` after `language` is valid, and `getattr(plan, "changelog_base_url", None)` returns `None` correctly under `slots=True` (3-arg `getattr` catches the `AttributeError`). ✓
- `GitHubAppAuth.token(self, org_id: int) -> str` — signature matches Task 2's `self._auth.token(org_id)`. ✓
- `create(...)` positional arg order in Task 4 step 8 (`org_id, org_login, repo, version, body, prerelease, target_commitish`) exactly matches the Task 2 signature. ✓
- `release_report(repo, org_id, branch, *, mirror, collector, resolver, reasoner)` — the `functools.partial` binding of the four keyword collaborators and the `(repo, org_id, branch)` call are correct. ✓
- `Localizer.report_notes(report, repo, org_id, langs)` returns `dict[str, str | None]`; the plan's `notes.get(...) or ""` correctly guards both a missing key and a `None` value (empty-report case). ✓
- `PivotLocalizer(reasoner, translator, pivot="en")`, `Versioner(mirror, collector, version_increment)`, `Reasoner(llm, embedder, knowledge, episodic, graph, reasoner_k)` constructors all match the wiring in Task 5. `Reasoner` needs no `RemainingPromptBuilder` (only `SummarySection` is used by `release_report`, and it takes `(mirror, resolver, reasoner)`). ✓
- `mirror.ensure` and `versioner.next` are **synchronous** (`def`, not `async def`); the plan correctly calls `mirror.ensure(...)` without `await` (mirrors `KnowledgeSync.on_push` and `scripts/report.py`) and awaits only the genuinely-async calls (`report_notes`, `create`, `deliver`). ✓
- `PushEvent` carries `org_login`, `before`, `after` — all used by the fan-out. ✓
- All Task 5 collaborators (`mirror`, `store`, `embedder`, `episodic_store`, `graph`, `auth`, `collector`, `resolver`) exist inside the `if github_app… mirror` block of `main.py`'s `lifespan`; `delivery_plan_resolver` is set unconditionally, so the App-disabled `else` correctly leaves the new attrs absent and Task 6's `getattr` presence check skips the fan-out. ✓
- No import cycles: `versioner` does not import `delivery`, so `service.py`/`github_release.py` importing `Version` is safe; `main.py`/`router.py` additions reuse imports already proven by `scripts/report.py`. ✓
- Backward compatibility: `DeliveryService.deliver(plan, note, version=None)` keeps existing Phase-10 callers (`deliver(plan, note)`) working; the header is keyed purely on `version` presence. ✓

### Critical Issues

None. The plan is internally consistent, grounded in the actual code, and faithful to both the spec and the roadmap contract.

### Positive Notes

- The 12.1/12.2 forward-compat strategy is handled with real rigor: dormant changelog leg via `getattr(plan, "changelog_base_url", None)` + optional injected `changelog_client=None`, so the mandatory union/degradation behaviour is fully implemented and testable *now* with fakes, with zero dependency on 12.1's concrete types. The extension-point locals (`github_url`, `union`, `notes`, `app_available`) are explicitly marked for 12.2.
- The `org_id`-first deviation on `create` is surfaced as a pinned decision with its rationale, not silently baked in — exactly the right way to record a spec-vs-reality reconciliation.
- Test tasks 7–8 pin the load-bearing invariants the spec calls mandatory (one `report_notes` call; union equality; role→prerelease; `target_commitish`; `mirror.ensure`-first ordering; `None`-version early return; unreachable-app degradation to the fixed union).
- The sync-in-async blocking of `mirror.ensure`/`versioner.next`/`token()` inside the async background task is not a defect — it is the established codebase pattern (`KnowledgeSync.on_push` is `async` yet calls the synchronous `mirror.ensure` directly), so 11.3 stays consistent.

## Deferred observations

- Affects: Phase 12.1 (`.ai-factory/specs/22-changelog-protocol-client.md`) — The plan pins `changelog_client.config(base_url)` as returning an object exposing `.languages: list[str]`, while 12.1's frozen contract states `GET config → {languages:[string]}`. If 12.1 ships `config` as returning a mapping/dict rather than an attribute-bearing object, the single accessor in Task 4 step 5 (`(await changelog_client.config(base_url)).languages`) must be adapted. This is already explicitly flagged in the plan's "Assumptions & pinned decisions" and its fix lies wholly in the not-yet-built 12.1 leg, so it is out of 11.3's scope — recorded here only so the 12.1 implementer reconciles the shape rather than re-deriving it. [dismissed]

PLAN_REVIEW_PASS
