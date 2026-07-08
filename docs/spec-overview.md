# Overview

Herald is a service that stands between an organization's development process and the
people who need to hear about it. It watches for pushes to tracked repositories,
summarizes the changes behind each push with a local LLM, and delivers the result to
the channels that fit the branch it landed on.

## End-to-end flow

A single push drives the whole pipeline:

1. **[Ingestion](spec/ingestion.md)** — a push to a tracked repository reaches Herald as an
   authenticated event carrying the organization, repository, branch, and commits.
2. **Role resolution** — the branch is mapped to a role: `release`, `staging`, or
   `dev` (see [delivery.md](spec/delivery.md)). The role decides which channels fire and
   how the notes are shaped.
3. **[Summarization](spec/summarization.md)** — Herald collects the relevant commits, feeds
   them to the LLM, and produces release notes as a digest of the key changes, in
   every language the active channels need.
4. **[Delivery](spec/delivery.md)** — the notes go out on the channels the role activates:
   Telegram always, GitHub releases and the app's changelog store on staging and
   release.

Every step reads from a single delivery plan resolved from the push's
`(organization, repository, branch)` — see [delivery.md](spec/delivery.md) and
[configuration.md](spec/configuration.md).

## Actors and terms

| Term | Meaning |
|------|---------|
| **Organization** | A GitHub org that has installed the Herald GitHub App. The installation is what authorizes Herald to act on the org's repositories. |
| **Repository** | A repo covered by an installation. Pushes to it are eligible for summarization. |
| **Branch role** | The classification of a branch — `release`, `staging`, or `dev` — derived from the branch name. Drives all routing. |
| **Channel** | A delivery destination with its own fixed language and formatting: Telegram, GitHub release, or an app's changelog store. |
| **Integrated app** | An application that implements the internal changelog protocol and receives release notes into its own database. Only some repositories map to one. |
| **Release notes** | The human-readable summary produced for a push — a digest of key changes, not a per-commit log. |

## Design spine

- **The branch role is the pivot.** One classification of the branch decides
  channels, languages, formatting, and whether a version is cut. Everything
  downstream reads the role, never the raw branch name.
- **Language is a property of the channel, not the repository.** Telegram defaults to
  Russian and GitHub releases to English — configured values resolved through the seam,
  not hard-coded — and an app's changelog store uses the languages that app declares. A
  push generates whatever set of languages its active channels require.
- **Authorization comes from the GitHub App installation.** An organization opts in
  by installing the App; that installation is both the trust boundary and the spam
  filter. Herald never acts on a repository it was not installed on.
- **Configuration resolves per push, behind one seam.** The mapping from a push to a
  delivery plan lives behind a single resolver so its backing store can grow from
  environment configuration to a database to a multi-tenant GUI without touching the
  summarization or delivery code.
