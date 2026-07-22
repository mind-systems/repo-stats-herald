## Code Re-Review — 3.1.2 Repo mirror (impl) — round 2

**Files re-read in full:** `src/github/mirror.py`, `src/github/app_auth.py`, `src/core/config.py`, `pyproject.toml`, `.env.example`.
**Verification run:** `uv run pytest` → 8 passed. Independently confirmed the new credential path: `GIT_CONFIG_COUNT`/`KEY_0`/`VALUE_0` correctly injects `http.extraHeader`, and on git failure the secret is absent from `CalledProcessError` (`cmd == ['git', 'fetch', 'origin']`, `"SECRET" in str(e)` → `False`).

---

### Verdicts on round-1 findings

**Finding 1 [Medium — token in git argv → process table + `CalledProcessError`/logs]: FIXED.**
`_run_git` no longer places the credential on argv; it passes it through git's environment-based config. Current `src/github/mirror.py:141-156`:
```python
def _run_git(self, *args: str, cwd: Path, credential: str | None = None) -> None:
    env = None
    if credential is not None:
        basic = base64.b64encode(f"x-access-token:{credential}".encode()).decode()
        # Passed via env, not `-c ...`/argv: argv lands in the process
        # table (world-readable via /proc/<pid>/cmdline) and verbatim in
        # `CalledProcessError.cmd` on failure — env vars are readable
        # only by the process owner/root and never appear in that
        # exception.
        env = {
            **os.environ,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        }
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)
```
The token is now out of `argv` (so out of `/proc/<pid>/cmdline` and out of `CalledProcessError.cmd`) — both exposure paths cited in round 1 are closed, and I reproduced that the header is still applied to the fetch. It remains out of the `origin` URL (`ensure` still passes `source` verbatim to clone) and git never echoes `extraHeader` to stderr, so the "never logged" guard now holds on the error path too.

**Deferred observation 1 [restart-orphaned worktrees / startup sweep]: ADDRESSED (hand-off documented).**
The `RepoMirror` docstring now carries the sweep hand-off to the consuming task. Current `src/github/mirror.py:33-38`:
```
error deep inside token minting instead of a clear boot failure. That
same startup path should also sweep `{mirror_root}/worktrees` (remove
every entry, then `git worktree prune` per repo) — `tree()`'s deferred
reclamation lives in an in-memory list, so worktrees finished right
before a crash/restart are never picked up by `ensure()` and would
otherwise leak on disk indefinitely.
```
This is the correct resolution for this task (no boot path exists here to host the sweep); the responsibility is now explicit for 3.4.2/3.6.

**Deferred observation 2 [fixed TTL vs. server `expires_at`]: unchanged, acceptable.**
`src/github/app_auth.py:10` still `_VALID_FOR_SECONDS = 3600 - 300`. Correct for GitHub's current 1h token lifetime and consistent with the pinned `_mint_token -> str` signature (server `expires_at` isn't surfaced). No action required.

---

### New issues

None blocking. The `app_auth.py` implementation is unchanged from round 1 (single-flight double-checked locking, JWT mint, paginated installation resolution — all re-confirmed correct), and the `mirror.py` change is isolated to `_run_git`'s credential transport, which I verified end-to-end.

### Deferred observation (non-blocking, for the consumer task)
- **Concurrent first-`ensure()` for the same repo can double-clone.** In `ensure` (`mirror.py:59-76`), two threads that both observe `not bare_path.exists()` before either clone completes would each run `git clone --mirror` into the same path; the loser fails with `CalledProcessError`. This is loud (raises, not silent corruption) and self-healing (once the bare store exists, subsequent calls take the `fetch` branch), and it is outside 3.1.1's pinned contract (the tests exercise concurrent `tree()`, and `ensure()` exactly once). The consumer that drives `ensure()` per push should serialize `ensure` per repo (or make first-clone idempotent) if near-simultaneous first pushes for a brand-new repo are expected. No change needed in this task.

REVIEW_PASS
