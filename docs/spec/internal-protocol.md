# Internal Protocol

The internal protocol is the contract between Herald and an integrated application. It
lets Herald ask an app which languages it wants and write release notes into the app's
own changelog store, which the app then exposes to its users as a "what's new" feed.

## Trust boundary

Both endpoints live on a dedicated internal port and carry no API keys. Access is
restricted to the internal network: Herald and the integrated apps sit on the same
private network on the server, and the internal port is never exposed externally. The
network is the authorization boundary, so no per-app secret is exchanged.

This holds as long as Herald is co-located with the apps. Reaching apps across a
network boundary — the multi-tenant direction — would require an authenticated,
externally reachable endpoint and a per-app key; that is a future concern, not the
current contract. See [configuration.md](configuration.md).

## Endpoints

### `GET /internal/changelog/config`

Reports the languages the app expects.

```json
{ "languages": ["ru", "en"] }
```

Herald calls this before generating notes for the app, so it produces exactly the
languages the app will store — no more, no less.

### `POST /internal/changelog/entry`

Writes one changelog entry into the app's database.

```json
{
  "version": "1.2.0",
  "environment": "production",
  "summary_ru": "…",
  "summary_en": "…",
  "github_url": "https://github.com/org/repo/releases/tag/v1.2.0"
}
```

| Field | Meaning |
|-------|---------|
| `version` | The assigned version, e.g. `1.2.0` or `1.2.0-rc`. See [versioning.md](versioning.md). |
| `environment` | `staging` or `production`. |
| `summary_ru` | The Russian notes. Russian is the baseline language and is always present. |
| `summary_en` | The English notes, or `null` when the app does not declare English. |
| `github_url` | Link to the GitHub release or pre-release the entry corresponds to. |

## How Herald uses it

The changelog channel activates only on a `staging` or `release` push, and only when
the repository maps to an integrated app (see [delivery.md](delivery.md)). When it
does:

1. Herald calls `GET /internal/changelog/config` to learn the app's languages.
2. It generates the notes in those languages (see [summarization.md](summarization.md)).
3. It calls `POST /internal/changelog/entry` with the version, environment, per-language
   summaries, and the GitHub release URL.

## One frozen contract

These two endpoints are the public interface of Herald toward every integrated app.
The shape stays identical across every implementation — hand-written integrations and
any future per-platform SDK alike — so that Herald speaks to all apps through the same
contract. Each app stores entries in its own Postgres database.
