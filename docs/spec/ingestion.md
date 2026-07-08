# Ingestion & Authorization

Herald receives pushes as native GitHub App webhook events. The App installation is
the single mechanism that authorizes a repository, filters out anything unsolicited,
and delivers the push — no per-repository configuration and no shared secrets in the
tracked repositories themselves.

## Onboarding by installation

An organization opts in by installing the Herald GitHub App on its repositories. The
installation is offered in two scopes:

| Scope | Effect |
|-------|--------|
| **All repositories** | Every current and future repository in the org is covered automatically. |
| **Only select repositories** | Only the chosen repositories are covered; the set is managed in the GitHub UI. |

Repository visibility does not matter — private and public repositories are covered
identically. The installation is the GitHub-side access boundary: Herald can reach only
repositories an installation covers, and a repository becomes reachable the moment the
App is installed on it, with no further wiring. Whether Herald actually *serves* the
organization behind that installation is a separate decision — see
[Who Herald serves](#who-herald-serves).

When the installation uses **Only select repositories**, Herald tracks the
`installation_repositories` event so it learns immediately when a repository is added
to or removed from its reach.

## Who Herald serves

Being installable is not the same as being served. The App is public — it has to be, to
reach more than one organization — so anyone could install it on their own
repositories. GitHub's scoping and the signed webhook keep out unsolicited
*repositories*, but they do not stop an unsolicited *organization* from installing.

Serving is therefore gated a second time, on Herald's side, by a **serve-allowlist of
organization IDs**. Every event carries the installing organization's identity
(`organization.id` / `installation.account.id`); Herald checks it against the allowlist:

- **on the allowlist** — it mints an installation token and runs the pipeline;
- **not on the allowlist** — it drops the event: no token, no summarization, no
  delivery, no LLM spend.

The two layers are distinct:

| Layer | Owner | Decides |
|-------|-------|---------|
| Installation | GitHub | which **repositories** Herald may access, and which generate events |
| Serve-allowlist | Herald | which **organizations** Herald actually acts for |

The allowlist lives behind the config resolver, so it starts as a small static set of
org IDs and later becomes self-service onboarding (see [configuration.md](configuration.md)).

## Trigger: the App's own webhook

Herald exposes one webhook endpoint. The webhook is configured once on the GitHub App
itself, not per repository, and the App subscribes to the `push` event. Every push to
a covered repository is delivered to that single endpoint.

This makes authorization and spam-resistance intrinsic:

- **Signed payloads.** Each delivery is HMAC-signed with the App's webhook secret.
  Herald verifies the signature and rejects any request that is unsigned or whose
  signature does not match. An open HTTP endpoint that drives the LLM is otherwise a
  standing invitation to be flooded; the signature closes it.
- **Installation-scoped.** Only repositories under an installation generate events at
  all, so there is no per-repository list for Herald to maintain. Which
  *organizations* it serves is a separate, Herald-owned gate — see
  [Who Herald serves](#who-herald-serves).

Because the trigger is the App's webhook rather than a workflow dropped into each
repository, tracked repositories need no `herald.yml` and no repository-level secret.

## What the push carries

A push event carries everything role resolution and routing need without an extra
lookup against GitHub:

- the **organization** and **repository** identity (`organization`, `repository.owner`),
- the **branch** the push landed on,
- the **commits** in the push and the before/after SHAs.

The organization identity resolves the Telegram channel; the repository identity
resolves an optional changelog target; the branch resolves the role. See
[delivery.md](delivery.md) for how these map to a delivery plan.

## GitHub App permissions

| Permission | Access | Why |
|------------|--------|-----|
| **Contents** | write | Read commit history and file contents for summarization; create tags and releases. Release and tag creation both fall under Contents write. |
| **Metadata** | read | Mandatory baseline for any GitHub App. |
| **Pull requests** | read | Read PR titles and bodies for richer summarization context. Used only where the summarizer consumes PR data. |

Herald authenticates as the App (App ID + private key), exchanges that for an
installation access token per organization, and uses the token for all reads and for
release creation. It never uses personal access tokens.
