# Plan: 19.4 — Chunk Telegram messages by UTF-16 code units

## Context
`TelegramClient._chunks` measures and slices by Python code points, but Telegram counts its 4096 limit in UTF-16 code units (astral-plane characters cost two); bring the chunker to the counting rule the governing spec pins in `docs/behavior/delivery.md` so an astral-dense message is split locally instead of being rejected by the Bot API.

## Settings
- Testing: yes (one targeted case)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: UTF-16-aware chunking

- [x] **Task 1: Measure and cut `_chunks` by UTF-16 code-unit count**
  Files: `src/delivery/telegram.py`
  Rewrite `TelegramClient._chunks` so both the fast-path guard and the slicing are governed by UTF-16 code-unit count rather than `len(text)` (code points), implementing the rule stated in `docs/behavior/delivery.md` ("The limit counts UTF-16 code units … every character outside the Basic Multilingual Plane costs two").
  - A code point's UTF-16 cost is `1` if `ord(ch) < 0x10000`, else `2`. Keep this as a small local helper (module-level function or inline), consistent with the file's plain style — no new class, no config, no external dependency; `TELEGRAM_MESSAGE_LIMIT = 4096` stays as the unit count.
  - Fast path: if the whole message's UTF-16 length is `<= TELEGRAM_MESSAGE_LIMIT`, return `[text]` unchanged.
  - Otherwise iterate the string by code point, accumulating UTF-16 cost, and start a new part whenever appending the next code point would push the running cost above the limit. Every cut lands on a Python code-point boundary — Python strings hold no surrogates, so a cut can never split a surrogate pair (the property holds by construction; do not slice encoded bytes).
  - Preserve the existing guarantees: parts are ordered and their concatenation equals the original text exactly (no loss, duplication, reordering); a message entirely within the BMP produces byte-for-byte the same parts as today, since each BMP code point costs exactly one unit. `send` is untouched — it still posts each chunk as plain text with no `parse_mode`.

### Phase 2: Verification

- [x] **Task 2: Test that an astral-dense over-limit message splits losslessly** (depends on Task 1)
  Files: `tests/delivery/test_telegram_client.py`
  Follow the existing `test_over_length_message_splits_into_ordered_lossless_parts` pattern (uses `_install_fake_transport` + `TelegramClient.send`). Add a case built from astral-plane characters (e.g. a repeated emoji or other `ord >= 0x10000` code point) whose UTF-16 length exceeds `4096` while its Python `len` stays at or below it. Assert: the message is split into more than one part; every part's UTF-16 length (`len(part.encode("utf-16-le")) // 2`) is `<= 4096`; and `"".join(parts)` equals the original text exactly. Leave the existing BMP chunking test in place — it pins that all-BMP behavior is unchanged.
