## Code Review Summary

**Artifact Reviewed:** `.ai-factory/plans/06-19-1-scrub-the-bot-token-from-delivery-failure-paths.md`
**Files consulted:** `src/delivery/telegram.py`, `src/delivery/service.py`, `src/commits/collector.py`, `src/ingestion/router.py`, `tests/delivery/test_telegram_client.py`, `.ai-factory/specs/56-telegram-token-redaction.md`, `.ai-factory/RULES.md`, `.ai-factory/plan-reviews/…-plan-review-1.md`
**Risk Level:** 🔴 High — the plan's prescribed code does not achieve its own stated goal, and it contradicts a test the same plan requires.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — change is contained to the `src/delivery/` feature's own `TelegramClient`; no new cross-feature dependency, wiring, or composition-root change. Consistent with "owned details stay inside the owning class."
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty (no counter-defaults to enforce).
- **Roadmap** (`.ai-factory/ROADMAP.md` line 28 → `Spec: .ai-factory/specs/56-telegram-token-redaction.md`): PASS on linkage. The plan's intent maps faithfully to the spec's Change/Guards/Verification. Round-1's issue #1 (a red pre-existing test under `Testing: no`) is now resolved — `Settings` sets `Testing: yes` and Task 3 repairs `test_bad_token_response_raises_and_is_not_swallowed` and adds the transport-failure case. That regression is closed. The remaining problem is a new one introduced by round-2's fix to issue #2.

### Critical Issues

**1. Task 2's prescribed `err.__context__ = None` before the raise is overwritten by the raise itself — the token still leaks via `__context__`, and this directly contradicts Task 3's own assertion.**

The plan states (Task 2): *"Setting `__context__ = None` is what actually removes the chained object; `from None` alone is not sufficient,"* and prescribes:
```python
except httpx.HTTPStatusError as exc:
    status = exc.response.status_code if exc.response is not None else None
    err = TelegramSendError(status)
    err.__context__ = None
    raise err from None
```
This does **not** work. CPython's implicit context chaining runs at the moment of `raise`, inside the `except` block: `raise err` re-sets `err.__context__` to the exception currently being handled (the `httpx` error), **overwriting** the `None` assigned a line earlier. `from None` only sets `__cause__ = None` / `__suppress_context__ = True`; it does not stop `__context__` from being re-populated.

Verified against ground truth (project venv, Python 3.13; behavior identical on the project's 3.12 — this chaining semantics has been stable since 3.0):
```
py: 3.13.0
__context__ is None?: False
type of __context__: HTTPStatusError
LEAK token in url?: True        # e.__context__.request.url still contains the token
```
So after the change as written, `raised.__context__.request.url` is still reachable and still carries the token — the exact leak spec guard line 21 forbids ("no request object reachable from its attributes"). `__suppress_context__ = True` does stop `logger.exception` from *printing* the chained context (closing the concrete ingestion-wrapper log vector), but the object remains reachable, so the guard's letter is unmet.

This is worse than a stale rationale: Task 3 explicitly requires a test asserting "no `__context__`/`__cause__` reachable from the raised error carries the token." An implementer who writes the Task 2 code exactly as prescribed and then writes the Task 3 test will get a **failing test with no fix path in the plan** — the plan is internally inconsistent.

Round-1's review offered two remedies ("raise outside the `except` block *or* explicitly set `err.__context__ = None` before raising"); the second is the one that does not work, and the plan picked it. Only the first is correct.

**Fix — raise the redacted error *outside* the `except` block** (verified to leave `__context__ is None` and no token reachable, `status=400`):
```python
async def send(self, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{self._token}/sendMessage"
    async with httpx.AsyncClient(timeout=self._timeout) as client:
        for chunk in self._chunks(text):
            try:
                response = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
            except httpx.RequestError:
                status = None
            else:
                continue
            raise TelegramSendError(status)   # no active exception here → __context__ stays None
```
Once the `except` block finishes without re-raising, the handler's active exception is cleared, so the later `raise TelegramSendError(status)` establishes no implicit context — `__context__` is genuinely `None`. (An equivalent alternative is to `raise … from None` inside the block, then re-catch in an enclosing handler and set `.__context__ = None` there; the raise-outside form is simpler.) Whichever form is chosen, the plan must drop the false claim that setting `__context__ = None` before the raise removes the chain, and apply the same correction to the `httpx.RequestError` clause (which the plan says is "analogous" and therefore inherits the same defect).

### Positive Notes
- Round-1 issue #1 is fully addressed: `Testing: yes`, and Task 3 both repairs the now-red `test_bad_token_response_raises_and_is_not_swallowed` (expecting `TelegramSendError`, stubbing a response that actually carries a status code so the `status_code` read doesn't `AttributeError`) and adds the transport-failure case — matching all three spec Verification items.
- Both leak paths are correctly identified as distinct types; `HTTPStatusError` is not a subclass of `RequestError`, so the two `except` clauses are genuinely both required, as the plan states.
- Building the redacted endpoint from a fixed literal (never `self._token` or the live `url`) correctly eliminates leak-through-interpolation.
- The `exc.response is not None` guard before reading `status_code` is a real defense — it prevents an `AttributeError` when `response` is absent.
- Downstream signalling is preserved and correctly analyzed: `DeliveryService.deliver` awaits `send` without catching a type, and `src/ingestion/router.py` catches bare `except Exception` (line 33) via `logger.exception`, so `TelegramSendError` propagates and is handled exactly as the prior exception was.
- Following `CommitCollectionError`'s established one-line-docstring pattern for the new exception type is consistent with the codebase.
- The test's `FakeResponse.raise_for_status` raising the configured error correctly exercises the `RequestError` clause too, since Task 2's `try` wraps both `post` and `raise_for_status` — the plan's claim that both modes are stubbable via `_install_fake_transport(error=...)` holds.

### Required changes before implementation
1. **Fix Task 2's context-severing mechanism.** Replace the `err.__context__ = None; raise err from None` pattern with raising `TelegramSendError` *outside* the `except` block (or re-catch-and-null in an enclosing handler). Remove the incorrect claim that "setting `__context__ = None` is what actually removes the chained object." Apply the same correction to the `httpx.RequestError` clause. Without this, the token remains reachable via `__context__.request.url` and Task 3's required assertion fails with no in-plan remedy.
