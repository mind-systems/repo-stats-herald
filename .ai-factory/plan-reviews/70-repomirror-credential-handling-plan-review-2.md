# Plan Review — RepoMirror: credential handling (round 2)

**Plan:** `.ai-factory/plans/70-repomirror-credential-handling.md`
**Governing spec:** `.ai-factory/specs/78-repo-mirror-surface-test-plan.md` (ROADMAP_TESTS.md line 20 — "RepoMirror — credential handling")
**Target under test:** `src/github/mirror.py` (`RepoMirror._credential_for` / `_run_git`)
**Files Reviewed:** plan + `src/github/mirror.py`, `src/github/app_auth.py`, `tests/github/conftest.py`, `tests/github/test_mirror_isolation.py`, spec 78, ROADMAP_TESTS.md, prior review round 1

## Code Review Summary

**Files Reviewed:** 6
**Risk Level:** 🟢 Low

This is the second-round review; both critical issues from round 1 are now resolved in the plan text, and re-verification against the source confirms the fixes are correct.

- **Round-1 issue 1 (Task 3 / case 34 fetch-branch trap) — resolved.** The plan now explicitly labels "run `ensure` twice" a trap and explains why (the recording runner never actually runs git, so `bare_path.exists()` stays false and a second `ensure` re-takes the *clone* branch with still-passing-but-meaningless assertions). It instead mandates pre-creating the bare path via `local_mirror.object_store_path(REPO).mkdir(parents=True)` before a single `ensure`, which makes `bare_path.exists()` true and drives the `else:` `fetch --prune origin` branch. Verified against `ensure`'s `if not bare_path.exists()` at `src/github/mirror.py:114` and `object_store_path` returning `mirror_root / f"{repo}.git"` at `:58,68`.
- **Round-1 issue 2 (Task 6 / case 36 bytes-vs-str) — resolved.** The plan now specifies that `exc.stdout` / `exc.stderr` are `bytes` (because `_run_git` calls `run(..., capture_output=True)` with no `text=True`, `src/github/mirror.py:205`), that a `str`-in-`bytes` test raises `TypeError`, and prescribes `b"ghs_SECRET" not in (exc.stderr or b"")` or a decode-first check. It also correctly handles `exc.cmd` as `list[str]` via `" ".join(exc.cmd)` and notes `str(exc)` is a belt-and-braces check. All accurate.

The remainder of the plan re-verifies cleanly against the code:

- **Task 1 (case 32):** `remote.origin.url == str(local_upstream.path)` is how `git clone --mirror <path>` records a local path; the plain-path source means `_credential_for` returns `None` (`:184-188`), so the clean-config property is genuinely exercised. Reading `<bare>/config` raw text for absence of `Authorization` / `x-access-token` is valid — a bare repo keeps `config` at its top level.
- **Task 2 (case 33):** argv/URL/env assertions match `_run_git` (`:190-205`) exactly — token only in `GIT_CONFIG_VALUE_0`, `GIT_CONFIG_COUNT == "1"`, `GIT_CONFIG_KEY_0 == "http.extraHeader"`, and `GIT_CONFIG_VALUE_0 == f"Authorization: Basic {base64('x-access-token:ghs_SECRET')}"`. The "assert on specific keys, never dict-equality" guard correctly anticipates the `**os.environ` merge (`:200`).
- **Task 4 (case 35 real half):** replacing `auth.token` with a raising callable and asserting `ensure` succeeds against the filesystem upstream proves the non-http branch never mints — matches `_credential_for`'s scheme gate.
- **Task 5 (case 35 table half):** the scheme table is exact against `urlsplit`: plain path, `file://`, `ssh://`, and scp-style `git@github.com:acme/x.git` (the `@` prevents a scheme being parsed) all fall outside `{"http","https"}` → `None`; `http://`/`https://` → the token. Direct call signature `_credential_for(source, org_id)` matches `:184`.
- **Task 6 (case 36):** an `https://127.0.0.1:1/x.git` source with the default runner produces a real `CalledProcessError`; `cmd` carries no token (credential lives only in env), and the four-attribute check with correct types is sound. Connection-refused on port 1 fails before any credential prompt, so no hang and no real network.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` present): PASS — a test-only addition under `tests/github/`, no module boundaries crossed.
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty (no project counter-defaults); nothing to enforce.
- **Roadmap** (`ROADMAP_TESTS.md` line 20): PASS — plan title, credential-only scope ("lifecycle group is its own entry"), the recording-runner approach, and the "recorder must return a completed-process object" guard all match the contract line; the lifecycle entry (line 19) is `[x]` and `tests/github/test_mirror_lifecycle.py` exists, confirming the split. Spec linkage (78) is correct.
- **skill-context** (`.ai-factory/skill-context/aif-review/`): absent — no project-specific review overrides to apply.

### Critical Issues
None. Both round-1 defects are fixed and no new defects were found.

### Positive Notes
- **Right seam retained.** Tasks 2/3/6 build a local `RepoMirror(..., run=recorder)` rather than monkeypatching `src.github.mirror.subprocess.run`, matching the `run` keyword-with-default seam already in the code (`:46`) and spec 78's final decision — no module patching, no leak into neighbouring tests.
- **Fetch-branch trap turned into a teaching note.** Task 3 does not merely fix the instruction; it records *why* the naive approach fails, so a future reader cannot silently regress it.
- **Type-correct exception assertions.** Task 6 pins the exact runtime types (`bytes` for `stdout`/`stderr`, `list[str]` for `cmd`), pre-empting the `TypeError` that the round-1 wording would have produced.
- **Fixture-mint guard carried through.** The plan restates that `auth` cannot mint (key is not a PEM) and that every https-path case must monkeypatch `auth.token` so nothing reaches `jwt.encode` — matching `GitHubAppAuth._mint_token` (`app_auth.py:58-64`).
- **Case coverage complete.** Cases 32→Task 1, 33→Task 2, 34→Task 3, 35→Tasks 4+5, 36→Task 6 — the full credential group (32–36) is covered with no gaps and no scope creep into the lifecycle or concurrency groups.

PLAN_REVIEW_PASS
