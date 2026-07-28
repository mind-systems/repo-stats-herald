# 20.1 — Extract the release fan-out into `ReleaseDelivery`

**Phase:** 20 — Thin the ingestion router. Independent of 20.2 — touches orchestration placement, not the mirror's call shape.

## Current state

`_deliver_release` orchestrates the entire staging/release fan-out — ensuring the mirror is fresh, resolving the version, resolving the changelog app's declared-language union, building and localizing the release note, creating the GitHub release, delivering the Telegram note, and finally posting the changelog entry — inside the module whose job is receiving and verifying webhooks. It takes eight collaborators as keyword arguments with no type annotations, wired together at the call site rather than through a constructor, bypassing the dependency-injection discipline this project otherwise follows everywhere else. This project's architecture guidance names logic living in an entry point an anti-pattern and pins that routers stay thin while services own business logic. Two already-completed task specs — one for the GitHub-release wiring, one for the changelog-channel wiring — each named the delivery service module as the file to edit; the orchestration grew inline in the router instead of landing there.

## Change

Move the orchestration into a new `ReleaseDelivery` class living alongside the existing delivery service, in the same module. Its collaborators are typed and injected through the constructor, not passed per call. The class exposes one method that takes the parsed push event and runs the fan-out; the router constructs or fetches an already-built instance and awaits that one method. The router itself keeps only receiving the webhook, verifying its signature, parsing the payload, and dispatching to the background task — no orchestration logic remains in it.

## Files & types

- edit `src/ingestion/router.py` (remove the fan-out function; keep receive/verify/parse/dispatch)
- edit `src/delivery/service.py` (add the `ReleaseDelivery` class alongside the existing delivery service)

## Guards

- No behavior change at all: the same legs run in the same order — mirror ensure, version, changelog-app union, release note, GitHub release, Telegram, changelog entry.
- The changelog app's graceful degradation is identical in every case — unmapped, unreachable at the language-union call, or failing at the entry call — none of these ever block the GitHub release or the Telegram send.
- The isolation wrapper that keeps one background task's failure from aborting a sibling task is unchanged.
- Every existing log message and its content are preserved.
- The changelog base URL is read as a plain attribute on the delivery plan. The plan declares that field with a default and the resolver fills it on every resolve, so the attribute is always present and a defensive lookup with a fallback can never reach it — carrying that lookup across would preserve a false signal that the field may be absent, and would keep the access invisible to type checking and to a rename.
- The gate that decides whether the fan-out is dispatched at all — checking that every required collaborator is present — stays at the composition root and in the router, not inside the new class; the class assumes it is only ever called with all collaborators wired.
- The module-level fan-out already carries a twelve-case behavior suite pinning leg order, the single language-union resolution feeding every channel, graceful degradation at both changelog calls, the prerelease flag per branch role, the no-version skip, and the absence of re-derivation. Every one of those cases retargets at the new class as part of this task — none is dropped, weakened, or merged — and the suite is what proves the extraction changed no behavior.

## Verification

- A staging push produces the same GitHub release, the same Telegram message, and the same changelog entry it produces today.
- A push to a repo with no changelog app mapped still delivers the GitHub release and the Telegram note.
- A changelog app that is unreachable still blocks neither the GitHub release nor the Telegram note.
- The router module no longer contains any fan-out orchestration logic.
