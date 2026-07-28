# 19.4 — Chunk Telegram messages by UTF-16 code units

**Phase:** 19 — Boundary representation mismatches. Depends on 19.3 (the governing-spec rule this task implements). Independent of 19.1 and 19.2.

## Current state

`TelegramClient._chunks` compares `len(text)` against `TELEGRAM_MESSAGE_LIMIT` and slices by the same code-point index. Python's `len` counts code points; Telegram counts UTF-16 code units, in which every astral-plane character costs two. A message dense in such characters can pass the local length check at or below the limit while its true UTF-16 length exceeds it, and the Bot API rejects the oversized part.

## Change

Measure and split chunks by UTF-16 code-unit count instead of Python code-point count, implementing the rule 19.3 pins in the governing spec.

## Files & types

- edit `src/delivery/telegram.py` (`TelegramClient._chunks`)

## Guards

- A message entirely within the Basic Multilingual Plane chunks exactly as it does today — Python's code-point count and the UTF-16 code-unit count coincide there, so this is a behavior-preserving change for the common case.
- The concatenation of all parts still equals the original message exactly, with no loss, duplication, or reordering — the same property the client's existing mandatory chunking test already pins.
- The UTF-16 cost is measured per code point and every cut falls on a code-point boundary of the Python string — the encoded bytes are never sliced. A Python string holds no surrogate pairs, so a code-point-boundary cut cannot split one; slicing UTF-16 bytes instead would both introduce that possibility and fail on decode. The property holds by construction, not by testing for it.
- Sending stays plain text with no `parse_mode`, so no formatting entity is put at risk by a boundary falling inside it.

## Verification

- A message whose UTF-16 length exceeds the limit while its Python length does not is split into multiple parts rather than sent whole.
- The parts rejoin to the original message exactly.
- An all-BMP message produces the same parts as it did before this change.
