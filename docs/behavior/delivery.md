# Delivery

How a narration gets out. A served push updates Herald's memory only — episodic always, semantic on the canonical ref — and is never reported on its own. Delivery fires on a cadence and on milestones: a daily and a weekly report, and the staging/release milestones that carry a version. Delivery decides which channels fire, in which language, and with what formatting; it assigns and carries the version; and it defines the contract for writing into an integrated app. A milestone's routing derives from one input — the branch role — resolved through a single delivery plan.

## Triggers

A served push is not a delivery event. Every push updates Herald's memory — episodic always, semantic on the repository's canonical ref — and is never reported on its own. Delivery happens on a cadence and on release milestones:

| Trigger | What fires |
|---------|-----------|
| **Daily** (scheduled) | A report of what moved that day → Telegram. |
| **Weekly** (scheduled) | A report of the week's arc → Telegram. |
| **Push to `staging`** | A release-candidate milestone → Telegram (version header) + a GitHub pre-release + the app changelog. |
| **Push to the default branch** | A release milestone → Telegram (version header) + a GitHub release + the app changelog. |

The reports are a cadence (their content is described in [narration.md](narration.md)); the staging/release milestones carry a version (see [Versioning](#versioning)). Neither is a per-push notification.

## Branch role

The branch name maps to exactly one role through a single classification function:

| Branch | Role |
|--------|------|
| `master`, `main` | `release` |
| `staging` | `staging` |
| any other branch | `dev` |

The role names are resolved in one place, not compared inline across the delivery code. The set of release and staging branch names is fixed today; a repository that one day uses a differently named release branch is handled by extending that single resolver, not by threading a new comparison through delivery. See [configuration.md](configuration.md) for where the resolver lives.

## Channels

Language and formatting are properties of the channel, not of the repository. There are three channels, and each delivers in its own language — a configured value with a default, resolved through the config seam rather than hard-coded in the delivery code:

| Channel | Fires on | Language | Notes |
|---------|----------|----------|-------|
| **Telegram** | daily & weekly reports; staging/release milestones | configured, default RU | Report of what moved; on a staging/release milestone it carries a version header and the same text as the release notes. |
| **GitHub release** | `staging`, `release` | configured, default EN | A pre-release on staging, a full release on the default branch. See [Versioning](#versioning). |
| **App changelog store** | `staging`, `release` — only when the repository maps to an integrated app | app-declared | Written through the internal protocol into the app's own database. See [Internal protocol](#internal-protocol). |

The Telegram and GitHub-release languages are single-value defaults today (RU and EN), held in configuration so they can move to a database or a per-organization setting later without touching the delivery code (see [configuration.md](configuration.md)). The app changelog store is the one channel whose languages are not a default at all — it negotiates them per app at runtime.

### Telegram

Telegram carries the reports (daily and weekly) and the staging/release milestone announcements; it is not sent per push. The message language defaults to Russian, resolved through the config seam. A report is a plain notification with no version header. A `staging` or `release` milestone carries a version header (`v1.2.0-rc` or `v1.2.0`) and the same body as the release notes delivered elsewhere — the milestone announcement and the GitHub release read as the same text, differing only by the header and the rc/release marker.

A message longer than Telegram's per-message limit of 4096 is split into ordered parts, sent in sequence, whose concatenation is exactly the original text — nothing dropped, duplicated, or reordered. The limit counts UTF-16 code units rather than characters as a reader would count them: every character outside the Basic Multilingual Plane costs two, so a message dense in such characters reaches the limit sooner than its visible length suggests.

### GitHub release

On `staging` and `release`, Herald cuts a GitHub release on the same repository the push came from, in English by default. No mapping is needed: the repository is known from the push and the App installation already grants the access. Staging produces a pre-release, the default branch produces a full release.

### App changelog store

On `staging` and `release`, and only when the repository maps to an integrated app, Herald writes the notes into that app's own changelog store through the internal protocol. The languages written are the ones the app declares. A repository with no mapping simply does not activate this channel — Telegram and the GitHub release still fire. This keeps Herald from calling an internal endpoint on a repository that has no integrated app behind it.

## The delivery plan

Routing reads from one resolved delivery plan per delivery — a report run or a staging/release milestone. Given `(organization, repository, branch)`, the resolver produces:

- the **branch role**,
- the **Telegram channel** for the organization, and its **language** (default RU),
- whether a **GitHub release** is cut, whether it is a pre-release, and its **language** (default EN),
- the optional **changelog target** (an integrated app's internal endpoint), if the repository maps to one,
- the **set of languages** to generate, unioned across the active channels' resolved languages.

Two maps back the plan:

- **`organization → Telegram channel`** — consulted on every delivery (each report run and each milestone). The organization identity travels in the push payload; Herald maps it to a channel id. This is Herald's own mapping — GitHub does not know it.
- **`repository → changelog app`** — consulted only on `staging` and `release`. It resolves the repository to an integrated app's internal base URL, or to nothing.

Both maps live behind the configuration seam so their backing store can evolve without touching delivery — see [configuration.md](configuration.md).

## Versioning

Herald assigns a version to every staging and default-branch push that carries new work, and reflects it consistently across the channels that carry a version: the GitHub release tag, the Telegram header, and the internal changelog entry. A repo with no version tag yet starts at `v0.1.0`.

### Rules

Every push to `staging` cuts a release candidate: it advances the version from the latest version tag and carries a `-rc` suffix. Successive staging pushes advance it each time — `v1.2.1-rc`, then `v1.2.2-rc` — since each is a distinct test build.

The first push to a newly created `staging` branch is a staging push like any other. It carries no prior commit on that branch behind it, and it cuts that branch's first candidate rather than being read as introducing nothing.

A push to the default branch (`master`/`main`) is one of two things:

| Case | What it is | Version | GitHub artifact |
|------|------------|---------|-----------------|
| Promotion | a change that already rode through staging as a candidate | that candidate's version with the `-rc` dropped — no further bump | full release |
| Hotfix | a change reaching the default branch with no staging candidate behind it | advanced from the last full release | full release |

A promoted release and its staging candidate are the same version at two stages of its life; the `-rc` marks the candidate stage. A hotfix is genuinely new work on the default branch and advances the version on its own.

### Preserved history on the release branches

Version derivation reads the mirror's tags and history, so it holds `staging` and the default branch to a preserved, append-only history: merges into them are real merges or fast-forwards, and their history is never rewritten — no squash-merge, rebase, amend, or force-push on these branches. Rewriting their history detaches the version tags from the commits they mark, so Herald relies on the repository's branch protection to keep this invariant. Because history is preserved, a promoted change reaches the default branch with its staging candidate's commits intact — that is how Herald tells a promotion from a hotfix.

### Back-merge detection

A back-merge from the default branch into staging carries commits that are already part of the released history. Herald detects this — the push introduces no new work of its own beyond what the default branch already carries (a merge commit that only pulls the default branch down brings nothing new) — and skips the version bump, so a back-merge does not manufacture a spurious release candidate. Only genuinely new work on staging advances the version.

Detection rests on reading what the push introduces beyond the default branch. Where that reading cannot be performed at all — an unreadable mirror, a reference that does not resolve — the outcome is an error rather than a silent skip: a version is never withheld on the strength of a question that was never answered.

### Where the version flows

Once assigned, the version is the same token everywhere it appears: the GitHub release/pre-release tag, the Telegram version header, and the `version` field of the [internal changelog entry](#internal-protocol). The increment step — whether a push advances the major, minor, or patch component — is a configuration point rather than a fixed rule baked into delivery, and is resolved alongside the rest of the delivery plan (see [configuration.md](configuration.md)). Deciding the increment from the significance of the change itself is a future extension, not the current behavior.

## Internal protocol

The internal protocol is the contract between Herald and an integrated application. It lets Herald ask an app which languages it wants and write release notes into the app's own changelog store, which the app then exposes to its users as a "what's new" feed.

### Trust boundary

Both endpoints live on a dedicated internal port and carry no API keys. Access is restricted to the internal network: Herald and the integrated apps sit on the same private network on the server, and the internal port is never exposed externally. The network is the authorization boundary, so no per-app secret is exchanged.

This holds as long as Herald is co-located with the apps. Reaching apps across a network boundary — the multi-tenant direction — would require an authenticated, externally reachable endpoint and a per-app key; that is a future concern, not the current contract. See [configuration.md](configuration.md).

### Endpoints

`GET /internal/changelog/config` reports the languages the app expects:

```json
{ "languages": ["ru", "en"] }
```

Herald calls this before generating notes for the app, so it produces exactly the languages the app will store — no more, no less.

`POST /internal/changelog/entry` writes one changelog entry into the app's database:

```json
{
  "version": "v1.2.0",
  "environment": "production",
  "summaries": { "ru": "…", "en": "…" },
  "github_url": "https://github.com/org/repo/releases/tag/v1.2.0"
}
```

| Field | Meaning |
|-------|---------|
| `version` | The assigned version, e.g. `v1.2.0` or `v1.2.0-rc` — the same token everywhere it appears. See [Versioning](#versioning). |
| `environment` | `staging` or `production`. |
| `summaries` | The release notes as a map from language code to text — one entry for each language the app declared in `config`. No language is privileged and no set is fixed: whatever an app asks for, Herald generates it, through the same localization seam that serves every channel (see [narration.md](narration.md#languages-of-generation)). |
| `github_url` | Link to the GitHub release or pre-release the entry corresponds to. |

### How Herald uses it

The changelog channel activates only on a `staging` or `release` push, and only when the repository maps to an integrated app. When it does: Herald calls `GET /internal/changelog/config` to learn the app's languages, generates the notes in those languages (see [narration.md](narration.md#languages-of-generation)), and calls `POST /internal/changelog/entry` with the version, environment, per-language summaries, and the GitHub release URL.

### One frozen contract

These two endpoints are the public interface of Herald toward every integrated app. The shape stays identical across every implementation — hand-written integrations and any future per-platform SDK alike — so that Herald speaks to all apps through the same contract. Each app stores entries in its own Postgres database.
