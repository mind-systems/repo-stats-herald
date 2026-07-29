## Code Review Summary

**Artifact Reviewed:** `.ai-factory/plans/06-19-1-scrub-the-bot-token-from-delivery-failure-paths.md`
**Files consulted:** `src/delivery/telegram.py`, `src/delivery/service.py`, `src/commits/collector.py`, `tests/delivery/test_telegram_client.py`, `.ai-factory/specs/56-telegram-token-redaction.md`, `.ai-factory/ROADMAP.md` (line 28)
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — change is contained to the `src/delivery/` feature's own client; introduces no cross-feature dependency and touches only `TelegramClient`. No boundary concern.
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty (no counter-defaults); nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md` line 28 → `Spec: .ai-factory/specs/56-telegram-token-redaction.md`): PASS on linkage. The plan's intent (scrub token from both the non-2xx and transport-failure paths, keep the raise-on-failure discipline, keep status + redacted endpoint diagnosable) matches the governing spec's Change and Guards sections faithfully. Two spec guards are only partially met — see Critical Issues.

### Critical Issues

**1. The plan leaves an existing test red, but sets `Testing: no` and never mentions it.**
`tests/delivery/test_telegram_client.py::test_bad_token_response_raises_and_is_not_swallowed` (lines 82–90) asserts:
```python
error = httpx.HTTPStatusError("Unauthorized", request=None, response=None)
...
with pytest.raises(httpx.HTTPStatusError):
    await client.send("chat", "hello")
```
After Task 2, `send` catches `httpx.HTTPStatusError` and re-raises `TelegramSendError`, so this `pytest.raises(httpx.HTTPStatusError)` no longer matches and the test fails. Worse, Task 2 reads `response.status_code` off the caught exception, and this stub passes `response=None` — so the new catch block would hit `AttributeError` on `None.status_code` before it could even build the redacted error. An implementer who honors `Testing: no` verbatim will leave `make test` broken. This is inside the task's file boundary (the same module's own test) and must be handled: the plan needs an explicit step to update this existing test to expect `TelegramSendError` and to construct a stub response that actually carries a status code. Note the spec's own Verification section (`56-telegram-token-redaction.md`, lines 26–28) calls for exactly these three checks (stubbed 400, stubbed transport failure, unchanged happy path), so the `Testing: no` setting is itself in tension with the governing spec — at minimum the pre-existing test must be repaired even if no new ones are added.

**2. `raise ... from None` does NOT clear `__context__`; Task 2's stated rationale is factually wrong, and the spec guard "no request object reachable from its attributes" is only partially satisfied.**
Task 2 asserts that raising `from None` means "the original token-bearing `httpx` exception is NOT retained on `__cause__`/`__context__`." Verified directly in Python: `raise X from None` sets `__cause__ = None` and `__suppress_context__ = True`, but because the raise happens inside an `except` block, Python still populates `err.__context__` with the original exception:
```
cause: None
suppress: True
context: ValueError('token-bearing')
```
So after the change, `raised.__context__` is still the `httpx.RequestError`/`HTTPStatusError`, and `raised.__context__.request.url` (or its string form) still carries the token — reachable from the raised error's attributes. `__suppress_context__=True` does stop `logger.exception`/traceback formatting from *printing* the chained context, which closes the concrete leak vector the spec calls out (the ingestion wrapper's `logger.exception`). But spec guard line 21 is stricter — "any request object reachable from its attributes" — and `__context__` is reachable. To satisfy the guard's letter, the plan should build the `TelegramSendError` and raise it *outside* the `except` block (or explicitly set `err.__context__ = None` before raising). At minimum, correct the plan's inaccurate claim so the implementer doesn't rely on `from None` alone believing the chain is gone.

### Positive Notes
- Correctly identifies both leak paths and that they are distinct exception types (`httpx.HTTPStatusError` from `raise_for_status()` vs. `httpx.RequestError` for transport). `HTTPStatusError` is not a subclass of `RequestError`, so two separate `except` clauses are genuinely required — the plan calls for both.
- Good instinct to build the redacted endpoint from a fixed literal rather than interpolating `self._token` or the live `url`, eliminating leak-through-interpolation.
- Following `CommitCollectionError`'s established pattern for the new exception type is consistent with the codebase.
- Downstream is safe: the only caller (`DeliveryService.deliver`) merely awaits `send` without catching a specific type, and the ingestion wrapper catches bare `except Exception`, so `TelegramSendError` propagates and is handled exactly as the old exception was — signalling discipline preserved.
- Correctly scopes the happy path (chunking, order, JSON body, `None` return) as untouched.

### Required changes before implementation
1. Add a task/step to update `tests/delivery/test_telegram_client.py::test_bad_token_response_raises_and_is_not_swallowed` to expect `TelegramSendError` and to stub a response carrying a status code (reconcile the `Testing: no` setting with the spec's Verification section — at least the pre-existing test cannot be left failing).
2. Fix Task 2's `__context__` handling and its rationale: either raise the redacted error outside the `except` block / null out `__context__`, or explicitly document that `__suppress_context__` (not chain removal) is what closes the leak — and reconcile that against spec guard line 21.
