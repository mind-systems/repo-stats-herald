# 18.3 — Back-fill a repo when it starts being served

**Phase:** 18 — Silent release loss & unwired promises. Depends on 3.5 (`ServedRepoStore`) and 3.6 (`KnowledgeSync.backfill`), both already shipped. Closes the phase — the last of its three tasks.

## Current state

The `installation`/`installation_repositories` branch of `src/ingestion/router.py` checks the serve-allowlist, calls `ServedRepoStore.add` for `repos_added` and `.remove` for `repos_removed`, logs the counts, and returns. Nothing in that path calls `KnowledgeSync.backfill`. The 3.5 contract states that the served-repo set drives 3.6's on-install backfill, but `KnowledgeSync.backfill` has exactly one caller today — the manual `scripts/backfill.py` entrypoint — and the served-repo set itself is read only by the reporting run, never to trigger a backfill. A newly installed repo's semantic memory stays empty until someone runs that script by hand.

## Change

After `store.add` succeeds, dispatch `KnowledgeSync.backfill(repo, org_id)` once per repo in `repos_added`, each isolated the same way the existing push-delivery fan-out isolates its background tasks — one repo's failure is caught, logged, and never propagates to a sibling repo's backfill or to the webhook's own acknowledgement.

## Files & types

- edit `src/ingestion/router.py` (the `installation`/`installation_repositories` branch)

## Guards

- One repo's backfill failure never blocks another repo's backfill, and never blocks or delays the webhook response.
- A repeat `installation_repositories` add for an already-served repo re-runs backfill harmlessly — `KnowledgeSync.backfill` is already idempotent on its own terms.
- The removal path (`ServedRepoStore.remove`) is untouched; this task adds no behavior on repo removal.
- The episodic `HistoricalBackfill` is explicitly out of scope — this task wires semantic backfill only, matching what the 3.5 contract actually names.
- Two overlapping backfills of the same repo cannot duplicate or corrupt stored chunks — the chunk table is keyed on repo, path, and chunk index, and each file's write replaces that file's rows — but an unlucky interleaving can still make one of the two writes fail on that key, and the per-repo isolation wrapper would catch it and log it, leaving that repo partially indexed while the webhook has already been acknowledged. A repo left partially indexed must not be indistinguishable from a repo indexed successfully.

## Verification

- An `installation` event naming one or more new repos leaves each repo's knowledge store populated, with no manual script run required.
- An `installation_repositories` event adding a repo to an already-installed org behaves identically.
- If one repo's backfill fails, the webhook still returns its normal response and the other repos in the same event still get backfilled.
