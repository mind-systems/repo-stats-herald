# Code Review: 19.4 — Chunk Telegram messages by UTF-16 code units

## Scope
- `src/delivery/telegram.py` — new `_utf16_cost` helper; `TelegramClient._chunks` rewritten to measure and cut by UTF-16 code-unit count.
- `tests/delivery/test_telegram_client.py` — added `test_astral_dense_message_splits_by_utf16_length`.

## What the change does
`_utf16_cost(ch)` returns `1` for a BMP code point (`ord < 0x10000`) and `2` for an astral one, matching Telegram's UTF-16 counting rule pinned in `docs/behavior/delivery.md`. `_chunks` now:
- fast-paths to `[text]` when the total UTF-16 cost is `<= TELEGRAM_MESSAGE_LIMIT`;
- otherwise greedily accumulates code points, flushing the current part before a code point that would push the running cost over the limit.

## Verification performed
- **Full suite for the file:** `pytest tests/delivery/test_telegram_client.py` — 5 passed.
- **BMP behavior preservation (the primary guard):** compared new output against the old code-point slicing (`text[i:i+4096]`) for sizes `0, 1, 4095, 4096, 4097, 8192, 8315, 12288`. Parts are identical in every case, and `"".join(parts) == text` holds. The boundary math coincides because each BMP code point costs exactly one unit, so the greedy flush lands on the same index the old slice did.
- **Astral splitting:** an astral-dense message over the limit splits into multiple parts, each with UTF-16 length `<= 4096`, rejoining losslessly; every emitted part re-encodes to `utf-16-le` cleanly, confirming no cut falls inside a surrogate pair.

## Correctness notes
- A single code point costs at most 2 units, far below the 4096 limit, so the `if current and ...` guard can never strand a part that itself exceeds the limit — no infinite loop or oversized single-char part.
- Empty string: total cost `0 <= 4096` → `[""]`, identical to the prior `len("") <= 4096` path.
- Ordering and losslessness are preserved by construction (single left-to-right pass, no reordering, no dropped or duplicated code points).
- Surrogate-pair safety holds by construction: cuts fall on Python code-point boundaries, and Python strings hold no lone surrogates. Consistent with the spec's stance that this is a structural property, not a tested one.
- No `parse_mode` is introduced; `send` is untouched, so the plain-text/no-entity guard is unaffected.
- `_chunks` is private and has a single caller (`send`); no other consumer of the delivery module is affected. Other repo hits for `_chunks`/`TELEGRAM_MESSAGE_LIMIT` belong to the unrelated knowledge chunker.

## Minor observations (non-blocking, no action required)
- `_chunks` makes two passes over `text` in the over-limit case (the fast-path `sum(...)` then the accumulation loop). This is O(n) either way and messages are bounded; not worth complicating the code to fold into one pass.

No correctness, security, or runtime concerns found.

REVIEW_PASS
