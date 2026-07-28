# 23.5 — Make the generator refuse an empty answer

**Phase:** 23 — Clear the way for the coverage pass. Independent of the four seams; depends on 23.4 only in that the transport parameter is what lets the cases supply a response at all. Establishes `tests/llm/`, which the test roadmap's Ollama entry then extends with the embedder's own coverage. The cases are already written out in `.ai-factory/specs/80-ollama-clients-test-plan.md` under the generator's response-parsing group.

## Current state

The two concrete implementations behind the model-agnostic boundary are asymmetric in a way nothing declares. The embedder checks what came back before returning it: a missing vector array, an empty one, a count that disagrees with the texts it sent, an empty vector, and vectors of disagreeing dimension each raise with a message naming the client and the defect. The generator performs no check at all — it returns whatever the decoded body holds under its text key.

So a success response carrying an empty string is returned as an empty string. Nothing raises, nothing logs, and the value flows through the reasoner's narration, through the localizer, into a Telegram message that arrives blank; on a release push it also reaches the GitHub release body and the changelog app as an empty summary. A body missing the key entirely raises a bare lookup error naming only the key, from inside a client the caller has no reason to suspect. A success response that is not an object at all — a proxy or a broken tunnel answering 200 with something else — raises a type error from the same place.

The boundary's own discipline says a timeout or a transport failure raises rather than yielding a silently empty summary. That discipline was never extended to a successful response with nothing in it, which is the case that actually reaches a person.

## Change

Give the generator the validation its sibling already performs: a successful response whose body is not an object, lacks the text key, or carries text that is empty or only whitespace raises rather than returning. Follow the embedder's precedent for the failure — the same exception type, and a message naming the client and the specific defect — so both halves of the boundary fail the same way and a caller can catch one type.

Land the generator's response-parsing cases from the test plan with it, in a new `tests/llm/` driven through the injected transport.

## Files & types

- edit `src/llm/client.py` (`OllamaClient.generate`)
- add `tests/llm/` (package marker, a conftest carrying the transport-driven construction helper, and the generator's response cases)

## Guards

- A successful response carrying real text behaves exactly as today — same string, no stripping, no rewriting.
- The abstract boundary is untouched: it gains no validation concept and keeps naming nothing about the concrete backend.
- Whitespace-only text counts as empty. This is a decision, not an accident: a model that answers with a newline has produced nothing a reader can use, and letting it through would leave the blank-message path open under a different disguise.
- The embedder is not edited. Its five checks already exist and are covered by their own entry; this task only brings the generator level with it.
- Nothing about the transport, the timeout, the conditional bearer header, or the request body changes.

## Verification

- A success response with an empty body text, with whitespace-only text, with the text key absent, and with a non-object body each raise, and each message identifies the client and what was wrong.
- A success response with real text returns exactly that text.
- The generator and the embedder raise the same exception type for a defective response.
- No blank note can leave the boundary: exercising narration end to end against a model that answers with nothing surfaces an error rather than delivering an empty message.
