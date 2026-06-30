# Project Roadmap

> A press secretary between the dev process and the outside world: listens for GitHub pushes, summarizes changes with a local LLM, and routes human-readable release notes by branch.

## Milestones

---STOP---

- [ ] **Summarizer spike & eval harness** — isolated script (no FastAPI, no webhooks) that runs real commit ranges from mind/tradeoxy through Ollama. Build a small eval set of human-approved "good" notes, a model-agnostic `summarize(context) -> text` boundary, and iterate prompt + few-shot until output is acceptable. De-risks the single biggest unknown before any plumbing is built.
- [ ] **Structure-aware context collection** — assemble the input the LLM actually needs: commit messages + diff-stats + changed file paths (the projection of project structure) + PR titles/bodies + a short per-repo "project map". Quality comes from what is fed in, not from the model guessing.
- [ ] **Two-stage summarization pipeline** — stage 1: atomic per-commit/PR summaries (cheap, parallel); stage 2: aggregate into a digest. Keeps the 14B model in its competence zone (small focused inputs) and is model-swappable at the boundary.
- [ ] **Herald core service** — FastAPI webhook receiver triggered by a `.github/workflows/herald.yml` dropped into each repo; branch detection; Telegram delivery (RU) for all non-release branches. Provision the GitHub App (contents/metadata read) and Telegram bot here. Shortest path to "it lives".
- [ ] **Daily digest accumulation** — persist per-branch digests and accumulate commits since the last deploy to staging/master, so release notes are built from collected history, never from scratch.
- [ ] **GitHub releases & versioning** — semver bump on master + GitHub release; `-rc` suffix on staging + pre-release; back-merge detection (commit SHA already in master → skip the bump). Adds `releases: write` to the GitHub App.
- [ ] **First app integration (manual) + frozen contract** — hand-write the two internal endpoints (`/internal/changelog/config`, `/internal/changelog/entry`) into one real app and store entries in its own Postgres. Freeze the contract as a single `contract/changelog.openapi.yaml` in this repo — the one cross-cutting invariant.
- [ ] **Extracted changelog SDK** — after a second manual integration reveals what actually repeats, extract the thin shared part (table migration + write router) into `sdk/nestjs/` and `sdk/fastapi/` inside this mono-repo. No public registry; consumed by git, not npm/pip. SDK extraction comes last, not first.
- [ ] **Production deployment** — package herald as a Docker container with clean env/config wiring (Ollama host URL, GitHub App credentials, Telegram token) and ship the `herald.yml` workflow for tracked repos. Where it runs is the deployer's concern, not ours.
- [ ] **Quality feedback loop** — fold approved release notes back into the eval set and the few-shot prompt so output quality compounds over time; keep the LLM boundary swappable for a larger/hosted model upgrade without re-platforming.
