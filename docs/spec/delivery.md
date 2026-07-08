# Delivery & Routing

Delivery decides, for a single push, which channels fire, in which language, and with
what formatting. Every decision derives from one input — the branch role — resolved
through a single delivery plan.

## Branch role

The branch name maps to exactly one role through a single classification function:

| Branch | Role |
|--------|------|
| `master`, `main` | `release` |
| `staging` | `staging` |
| any other branch | `dev` |

The role names are resolved in one place, not compared inline across the delivery
code. The set of release and staging branch names is fixed today; a repository that
one day uses a differently named release branch is handled by extending that single
resolver, not by threading a new comparison through delivery. See
[configuration.md](configuration.md) for where the resolver lives.

## Channels

Language and formatting are properties of the channel, not of the repository. There
are three channels, and each delivers in its own language — a configured value with a
default, resolved through the config seam rather than hard-coded in the delivery code:

| Channel | Fires on | Language | Notes |
|---------|----------|----------|-------|
| **Telegram** | every push (all roles) | configured, default RU | Day-to-day notification. On staging/release it carries a version header and the same text as the release notes. |
| **GitHub release** | `staging`, `release` | configured, default EN | A pre-release on staging, a full release on the default branch. See [versioning.md](versioning.md). |
| **App changelog store** | `staging`, `release` — only when the repository maps to an integrated app | app-declared | Written through the internal protocol into the app's own database. See [internal-protocol.md](internal-protocol.md). |

The Telegram and GitHub-release languages are single-value defaults today (RU and EN),
held in configuration so they can move to a database or a per-organization setting
later without touching the delivery code (see [configuration.md](configuration.md)).
The app changelog store is the one channel whose languages are not a default at all —
it negotiates them per app at runtime.

### Telegram

Telegram fires on every push regardless of role. The message language defaults to
Russian, resolved through the config seam rather than fixed in code. For a
`dev` push it is a plain notification with no version header. For a `staging` or
`release` push it carries a version header (`v1.2.0-rc` or `v1.2.0`) and the same body
as the release notes delivered elsewhere — the release announcement and the GitHub
release read as the same text, differing only by the header and the rc/release marker.

### GitHub release

On `staging` and `release`, Herald cuts a GitHub release on the same repository the
push came from, in English by default. No mapping is needed: the repository is known
from the push and the App installation already grants the access. Staging produces a
pre-release, the default branch produces a full release.

### App changelog store

On `staging` and `release`, and only when the repository maps to an integrated app,
Herald writes the notes into that app's own changelog store through the internal
protocol. The languages written are the ones the app declares. A repository with no
mapping simply does not activate this channel — Telegram and the GitHub release still
fire. This keeps Herald from calling an internal endpoint on a repository that has no
integrated app behind it.

## The delivery plan

Routing reads from one resolved delivery plan per push. Given
`(organization, repository, branch)`, the resolver produces:

- the **branch role**,
- the **Telegram channel** for the organization, and its **language** (default RU),
- whether a **GitHub release** is cut, whether it is a pre-release, and its **language**
  (default EN),
- the optional **changelog target** (an integrated app's internal endpoint), if the
  repository maps to one,
- the **set of languages** to generate, unioned across the active channels' resolved
  languages.

Two maps back the plan:

- **`organization → Telegram channel`** — consulted on every push. The organization
  identity travels in the push payload; Herald maps it to a channel id. This is
  Herald's own mapping — GitHub does not know it.
- **`repository → changelog app`** — consulted only on `staging` and `release`. It
  resolves the repository to an integrated app's internal base URL, or to nothing.

Both maps live behind the configuration seam so their backing store can evolve without
touching delivery — see [configuration.md](configuration.md).
