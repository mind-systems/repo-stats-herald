# Overview

Herald is a service that stands between an organization's development process and the
people who need to hear about it. It watches pushes across an organization's
repositories, builds a standing understanding of each project from its own curated
docs, and narrates how its features progress with a local LLM — as periodic reports
and as release notes, delivered to the channels each fits.

## End-to-end flow

Two things happen, on different clocks.

**On every push** — [ingestion](spec/ingestion.md) turns a push to a tracked repository
into an authenticated event carrying the organization, repository, branch, and
commits, and the derivation engine folds it into Herald's memory: the episodic log
always, and the semantic model when the push is on the project's canonical ref (see
[understanding.md](spec/understanding.md),
[architecture](architecture.md#the-two-engines-over-the-event-stream)). A push updates
memory; it is not reported on its own.

**On a cadence and on releases** — the [reasoner](spec/narration.md) narrates from that
memory and [delivery](spec/delivery.md) sends it: daily and weekly **reports** — each
an ordered composition of content sections over a time window — and, on a push to
`staging` or the default branch, a versioned **release note** accumulated since the
last deploy. Each goes to the channels its trigger activates: Telegram for reports;
Telegram, the GitHub release, and an integrated app's changelog store for releases.

A delivery reads from a single delivery plan resolved from
`(organization, repository, branch)` — see [delivery.md](spec/delivery.md) and
[configuration.md](spec/configuration.md).

For a repository that predates Herald, [replay](spec/replay.md) runs the same engines
over its existing history in simulated time, delivering the reports and release notes
Herald would have sent along the way.

## Actors and terms

| Term | Meaning |
|------|---------|
| **Organization** | A GitHub org that has installed the Herald GitHub App. The installation is what authorizes Herald to act on the org's repositories. |
| **Repository** | A repo covered by an installation. Herald tracks its pushes and narrates its progress. |
| **Branch role** | The classification of a branch — `release`, `staging`, or `dev` — derived from the branch name. It classifies the release path — a `staging` or default-branch push carries a version and cuts a release; reports are branch-agnostic. |
| **Channel** | A delivery destination with its own fixed language and formatting: Telegram, GitHub release, or an app's changelog store. |
| **Integrated app** | An application that implements the internal changelog protocol and receives release notes into its own database. Only some repositories map to one. |
| **Release notes** | The versioned narration cut on a `staging` or default-branch push, accumulating everything since the last deploy — feature-level, not a per-commit log. |
| **Report** | A periodic narration — daily or weekly — composed of content sections over a time window, delivered to Telegram. Cadence-driven, not deploy-driven, and carries no version. |

## Design spine

- **Herald narrates from an understanding of each project.** It keeps a
  standing [knowledge model](spec/understanding.md#per-project-knowledge-model) of every project — features,
  direction, built-vs-remaining — built from curated artifacts, and a
  [project graph](spec/understanding.md#project-graph) of how projects connect. Narration reasons
  over these; a push's commits tell Herald what moved, and the model gives it the
  meaning.
- **The branch role classifies the release path.** A `staging` or default-branch push
  carries a version and cuts a release on the release channels; every other push
  updates memory silently. Reports are cadence-driven and branch-agnostic. The role
  is resolved in one place, never by reading the raw branch name downstream.
- **Language is a property of the channel, not the repository.** Telegram defaults to
  Russian and GitHub releases to English — configured values resolved through the seam,
  not hard-coded — and an app's changelog store uses the languages that app declares. A
  delivery generates whatever set of languages its active channels require.
- **Authorization comes from the GitHub App installation.** An organization opts in
  by installing the App; that installation is both the trust boundary and the spam
  filter. Herald never acts on a repository it was not installed on.
- **Configuration resolves per delivery, behind one seam.** The mapping from a
  delivery to a plan lives behind a single resolver so its backing store can grow from
  environment configuration to a database to a multi-tenant GUI without touching the
  narration or delivery code.
