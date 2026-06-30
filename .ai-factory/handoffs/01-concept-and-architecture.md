# Handoff — concept-and-architecture

## 1. Frame
The repo-stats-herald service concept has been fully designed and the AI Factory context has been initialized; no code has been written yet — rehydrate from CLAUDE.md and .ai-factory/ files, then move to implementation planning.

## 2. Read-first map

### Must-read now (minimal rehydration set)
- `CLAUDE.md` — single source of truth: what the service does, delivery matrix, internal protocol, versioning rules, GitHub App approach
- `.ai-factory/DESCRIPTION.md` — full feature list, tech stack, branch→delivery matrix, internal protocol spec
- `.ai-factory/ARCHITECTURE.md` — folder structure, dependency rules, code examples in Python/FastAPI

### Read on demand
- `.ai-factory/rules/base.md` — Python naming and module conventions
- `.mcp.json` — GitHub MCP server configured (needs GITHUB_TOKEN in env)

## 3. Current state

**Done:**
- Full concept designed: webhook service that listens for GitHub pushes, summarizes commits via Ollama, routes summaries by branch
- Named: `repo-stats-herald`
- Remote: `https://github.com/mind-systems/repo-stats-herald.git`
- AI Factory initialized: config.yaml, DESCRIPTION.md, ARCHITECTURE.md, rules/base.md, AGENTS.md
- Architecture chosen: Structured Modules (Technical Layers), Python/FastAPI
- MCP: GitHub server added to .mcp.json

**In-flight:**
- No code written yet
- Integration libraries for target apps not designed yet (see Next Step)
- GitHub App not created yet
- Telegram bot not created yet
- Docker Compose not written yet

**Uncommitted working-tree state:**
- All files in repo are new and uncommitted (.gitignore, CLAUDE.md, AGENTS.md, .ai-factory/*, .mcp.json)

## 4. Next step
Design and plan the **integration SDK** — the lightweight library that any target application must install to participate in the changelog ecosystem. The service declares a contract (two endpoints); the SDK implements it for each platform. Platforms to cover: NestJS (TypeScript), FastAPI (Python). Possibly Flutter/Dart if mobile apps need it. The interface is:
```
GET  /internal/changelog/config   → { "languages": ["ru", "en"] }
POST /internal/changelog/entry    → { version, environment, summary_ru, summary_en?, github_url }
```
Each SDK is a thin package (npm for NestJS, pip for FastAPI) that adds these two endpoints and stores entries in the app's own Postgres. Run `/aif-plan` for the SDK design, then plan the herald service itself.

## 5. Working discipline
- Never commit without explicit permission from the user
- Don't implement in the same session where a plan is created — plan → stop, implement in a separate session via `/aif-implement`
- Don't add features beyond what's discussed — no speculative abstractions
- No API keys per project — internal port access is the auth boundary

## 6. Error log
- Initial CLAUDE.md included server connection details (SSH host, key path, Ollama URL) — these belong in the digital_ocean repo, not here. Removed.
- Initial CLAUDE.md purpose paragraph named the specific Ollama model and server IP — too infrastructure-specific for a project-level doc. Removed.

## 8. Domain model spine

**Branch → delivery routing (don't re-litigate):**
- Any branch except `staging`/`master` → Telegram only (RU, no version header)
- `staging` → Telegram (RU, `v1.2.0-rc` header) + app changelog store + GitHub pre-release
- `master` → Telegram (RU, `v1.2.0` header) + app changelog store + GitHub release
- Staging and master Telegram message = same text as release notes, just with version header
→ See `CLAUDE.md` delivery matrix

**No API keys between services (don't re-litigate):**
- Internal port access is the sole auth boundary — no per-project API keys
- herald calls apps on a dedicated internal port; nginx doesn't expose it externally
→ See `CLAUDE.md` internal protocol section

**GitHub access via GitHub App, not personal tokens (don't re-litigate):**
- One GitHub App installed org-wide with `contents: read`, `metadata: read`, `releases: write`
- New repos are picked up automatically — no per-repo config needed
→ See `CLAUDE.md`

**Version bump rules (don't re-litigate):**
- Only master gets a real semver tag; staging gets `-rc` suffix
- Back-merges from master → staging are detected (commit SHA already in master) and skipped — no duplicate version bump
→ See `.ai-factory/ARCHITECTURE.md` anti-patterns

**Trigger mechanism (don't re-litigate):**
- GitHub Actions in each repo (`.github/workflows/herald.yml`) — one identical file dropped into every repo
- Actions call herald via HTTP on push; herald does all the work
- No webhook configuration in GitHub UI required per repo

## 9. Hard rules
- Commit message: short noun phrase or imperative, sentence case, no type prefixes (no feat:/fix:/chore:)
- No body for single-concern commits
- Artifacts language: English
- UI/communication language: Russian
- Memory writes only on explicit user trigger phrases ("запомни", "save to memory", etc.)

## 10. Cross-cutting contracts / invariants

Internal protocol endpoints — these must be identical across all SDK implementations:
```
GET  /internal/changelog/config
     → 200 { "languages": ["ru", "en"] }

POST /internal/changelog/entry
     → 201
     body: {
       "version": string,          // e.g. "1.2.0" or "1.2.0-rc"
       "environment": string,      // "staging" | "production"
       "summary_ru": string,
       "summary_en": string|null,  // null if app doesn't support EN
       "github_url": string        // URL to GitHub release
     }
```
This contract is the public interface of `repo-stats-herald` toward integrated apps. SDK packages implement it; herald calls it. Must stay identical across NestJS SDK, FastAPI SDK, and any future platform SDK.
