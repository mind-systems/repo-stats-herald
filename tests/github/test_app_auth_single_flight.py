"""Red single-flight test pinning `GitHubAppAuth.token()`'s per-org
invariant against the stub.

Fails because `token()` raises `NotImplementedError` before ever calling
`_mint_token` (the single-flight logic is absent), never because of an
import, fixture, or monkeypatch-arity error. The follow-up task's
single-flight `token()` wrapping the retained `_mint_token` turns it green
unchanged.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

ORG_ID = 1
N_CALLERS = 8
MINT_DELAY_SECONDS = 0.05


def test_concurrent_token_calls_mint_exactly_once(auth, monkeypatch):
    mint_count = 0
    counter_lock = threading.Lock()
    barrier = threading.Barrier(N_CALLERS)

    def counting_mint(org_id):
        nonlocal mint_count
        with counter_lock:
            mint_count += 1
        time.sleep(MINT_DELAY_SECONDS)
        return "fresh-token"

    monkeypatch.setattr(auth, "_mint_token", counting_mint)

    def call_token():
        barrier.wait()
        try:
            return auth.token(ORG_ID)
        except Exception as exc:  # noqa: BLE001 - captured for the assertion below, not swallowed
            return exc

    with ThreadPoolExecutor(max_workers=N_CALLERS) as executor:
        results = [future.result() for future in [executor.submit(call_token) for _ in range(N_CALLERS)]]

    assert mint_count == 1
    assert len(set(results)) == 1
