# 23.4 — Let a caller supply the model boundary's transport

**Phase:** 23 — Clear the way for the coverage pass. Independent of 23.1, 23.2 and 23.3. Opens the seam only; the generator's missing response guard is a behaviour change with its own reason to revert and is not part of this task.

## Current state

Both concrete implementations behind the model-agnostic boundary — the generator and the embedder — receive their host, model name, optional key, and timeout through the constructor, so everything about how they are addressed is already steerable by a caller. What they do not offer is any way to supply the transport: each builds its HTTP client inside the call, with neither an injected client nor a transport parameter.

The behaviour these two classes own is entirely a matter of what they do with a response — the generator returns the model's text out of the decoded body, the embedder checks the returned vectors against the texts it sent, rejecting a missing array, an empty one, a count that disagrees with the input, an empty vector, and vectors of disagreeing dimension. Every one of those decisions is a function of a response body or a transport failure, and neither can be supplied. The established way around it in this repository is to replace the HTTP client symbol on the module and hand-write a stand-in client and response pair, as the two delivery clients already do. That stand-in has to re-implement the asynchronous context-manager protocol, the request call, the status check, and the body decoding — none of which is the behaviour under test, and each an approximation that can diverge from the real library and let a wrong expectation pass.

## Change

Accept an optional transport on both classes and pass it through to the HTTP client they construct. A caller can then supply the library's own stub transport and drive the boundary with genuine response objects — real status raising, real decoding, real transport failures — instead of a hand-written approximation.

## Files & types

- edit `src/llm/client.py` (`OllamaClient.__init__` and the client construction inside `generate`)
- edit `src/llm/embedder.py` (`OllamaEmbedder.__init__` and the client construction inside `embed`)

## Guards

- The parameter is keyword-with-default-absent on both, so the application composition root and every script entrypoint are unchanged and keep the library's own default transport.
- The abstract boundary both classes implement is untouched — it gains no transport concept, so it keeps naming nothing about the concrete backend and stays swappable.
- No response-handling behaviour changes in this task. The generator today returns whatever the decoded body holds under its text key, with none of the validation its sibling embedder performs; that asymmetry is real and is a separate task, not a fix to slip in while the constructor is open.
- The three delivery clients share this construct-the-client-inline shape, and the two that are tested already carry the hand-written stand-in. They are out of scope: they are covered today and nothing pending depends on changing them. If the same seam is wanted there it is its own task.

## Verification

- Both classes can be constructed with a supplied transport and driven end to end with no network and no module replaced.
- A response body, a non-success status, and a transport failure can each be produced through the supplied transport, and the classes behave as they do against a real backend.
- Constructing either class without the parameter reaches the real backend exactly as today.
