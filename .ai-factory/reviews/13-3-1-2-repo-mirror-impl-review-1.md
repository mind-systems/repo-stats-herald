## Code Review — 3.1.2 Repo mirror (impl)

**Files reviewed (in full):** `src/github/app_auth.py`, `src/github/mirror.py`, `src/core/config.py`, `pyproject.toml`, `.env.example`, plus the pinned tests (`tests/github/*`) and their conftest.
**Verification run:** `uv run pytest` → 8 passed (all three pinned 3.1.1 scenarios green, webhook suite unregressed). Independently reproduced that `git clone --mirror` + `git fetch --prune origin` advances `refs/heads/*` on both fast-forward and force-amend (the round-1 critical fix holds).

**Risk level:** 🟡 Medium — one real secret-handling defect on the credentialed error path that the pinned tests cannot catch (they use a local, credential-less source); everything else is correct.

---

### Findings

**1. [Medium — security / spec-guard violation] The installation token is passed in the git command's argv, so it leaks into the process table AND into `CalledProcessError` (→ logs).**
`src/github/mirror.py:135-141` (`_run_git`) builds `["git", "-c", f"http.extraheader=Authorization: Basic {basic}", ...]`, where `basic` is `base64(f"x-access-token:{token}")`. base64 is encoding, not encryption — trivially reversible.

Two exposure paths, both violating spec `04-repo-mirror.md` Guards ("the token is **never** ... logged") and ROADMAP line 35 ("token as git credential never in `origin`"):
- **Process table:** while `clone`/`fetch` runs, `ps aux` (or `/proc/<pid>/cmdline`, world-readable by default on Linux) shows the full `-c http.extraheader=...` argument to any local user. Herald is co-located with Ollama on its server (CLAUDE.md), so this is a real local-exposure surface for a live, org-scoped (1h) token.
- **Logs (the guard's exact words):** `subprocess.run(..., check=True)` raises `CalledProcessError(retcode, cmd, ...)` whose `str()` embeds the **entire command list including the credential**. Reproduced:
  `Command '['git', '-c', 'http.extraheader=Authorization: Basic eC1hY2Nlc3MtdG9rZW46Z2hzX1NFQ1JFVFRPS0VOMTIz', 'fetch', 'origin']' returned non-zero exit status 128.`
  The base64 decodes straight back to `x-access-token:ghs_...`. Any `ensure()` that hits a transient GitHub/network failure on the `clone`/`fetch` path (the *only* commands that carry a credential) raises this, and Herald logs exceptions via the `logging` module — so a routine fetch failure writes the token to the log.

**Why the tests miss it:** the conftest's `clone_source` returns a **local filesystem path**, so `_credential_for` returns `None` and no credential is ever placed on argv. The defect only manifests against a real `https://` source. Green suite ≠ guard satisfied.

**Fix:** keep the token out of argv entirely. Pass the header via git's environment-based config so it is neither in `argv` nor in the raised `CalledProcessError.cmd`:
```python
env = {**os.environ,
       "GIT_CONFIG_COUNT": "1",
       "GIT_CONFIG_KEY_0": "http.extraHeader",
       "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}"}
subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)
```
(`GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n` is supported since git 2.31.) Env vars are readable only by the process owner/root (`/proc/<pid>/environ`), strictly better than the world-readable argv, and never appear in the subprocess exception. If any risk of the credential reaching a log remains, also scrub the header value from errors before propagating.

---

### Deferred observations

- **Worktree reclamation does not survive a process restart — unbounded disk leak across restarts (consumer/composition-root task).** `tree()`'s `finally` records finished worktrees in the **in-memory** `self._finished_worktrees` list, reclaimed only on the next `ensure()` for that repo (`src/github/mirror.py:107-127`). This correctly greens the pinned tests (which require the yielded path to still exist after the `with` block — see the docstring rationale, a genuine and necessary deviation from the plan's "remove in `finally`"). But on a crash/restart the list is lost, so worktrees finished before the restart are orphaned: their scratch dirs remain on disk, and `git worktree prune` will **not** collect them because their directories still exist. Over repeated restarts this contradicts the spec's "no disk leak" guard. The spec anticipated exactly this ("a startup sweep or explicit cleanup handles the rare leak"), but no boot path exists in this task. The consuming task that first constructs `RepoMirror` (3.4.2/3.6) should add a startup sweep of `{mirror_root}/worktrees` (remove every worktree + `git worktree prune`) before serving. Worth adding a one-line hand-off to the module docstring alongside the existing settings-assertion note. [dismissed]

- **`mint_token` caches a fixed TTL, not the server's `expires_at`.** `_VALID_FOR_SECONDS = 3600 - 300` (`app_auth.py:10`) assumes GitHub's 1h token lifetime with a 5-min margin, which is correct today and matches `_mint_token -> str` (the server `expires_at` isn't returned). If GitHub ever issues a shorter-lived token the cache could outlive it. Acceptable given the pinned signature; flagging only so a future change that surfaces `expires_at` uses it. [dismissed]

---

### Confirmed correct (spot-checks)
- **Single-flight token** (`app_auth.py:32-56`): lock-free fast path + per-org lock with double-checked cache re-read → exactly one mint under the 8-caller barrier; monkeypatched `_mint_token(org_id)` arity matches the one-positional call. `time.monotonic()` for cache expiry vs. wall-clock `time.time()` for the JWT `iat/exp` is the right split.
- **`_mint_token`** (`app_auth.py:58-90`): App JWT (`iat-60`, `exp+540` within GitHub's 10-min cap, `iss`=app_id), installation resolved by numeric `account.id == org_id` + `type == "Organization"` with correct link-header pagination (`params` dropped once following absolute `next` URLs), `raise_for_status()` on every call so failures never yield an empty token.
- **`ensure`** (`mirror.py:53-76`): `--mirror` (not `--bare`) so `remote.origin.fetch = +refs/*:refs/*` and fetch actually refreshes — verified live, including force-update; full clone (no sparse/partial); `_credential_for` gates the token on `http`/`https` scheme so local sources skip `auth.token()` (keeps isolation tests from failing on the stub's `NotImplementedError`).
- **`tree`** (`mirror.py:78-108`): `git worktree add --detach` avoids the same-ref branch-checkout collision and tolerates force-push; per-call `mkdtemp` gives distinct paths; deferred reclamation keeps already-yielded paths valid (required by `test_...isolated`'s post-`with` `path.exists()` assertion).
- **`Settings`** (`config.py:19-21`): new App/mirror fields made optional-with-defaults so the already-green webhook suite still constructs `Settings()`; validator block untouched; `.env.example` adds only `MIRROR_ROOT=`.
