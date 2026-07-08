# Configuration

Configuration answers one question per push: given
`(organization, repository, branch)`, what is the delivery plan? That resolution lives
behind a single seam so its backing store can grow over time without touching the
summarization or delivery code that depends on it.

## The resolver seam

All routing state is read through one resolver rather than by scattering environment
reads and branch comparisons across the code. Given a push, it returns the delivery
plan described in [delivery.md](delivery.md): the branch role, the Telegram channel,
whether a GitHub release is cut, the optional changelog target, and the set of
languages to generate.

Delivery and summarization depend on this resolver, never on the environment directly
— the same discipline the LLM boundary follows for the model backend. Concrete state
is read once and passed down; features stay unaware of where it came from. This is
what lets the backing store change without a rewrite.

## What the resolver holds

| State | Consulted | Content |
|-------|-----------|---------|
| Branch-role classification | every push | The fixed mapping of branch names to `release` / `staging` / `dev`. |
| `organization → Telegram channel` | every push | The channel id notifications go to for that org. |
| Channel languages | every push | The language each fixed channel delivers in — Telegram (default RU) and the GitHub release (default EN). Held as configured defaults rather than code literals, so they can later move to a database or a per-organization setting. The app changelog store is not here — it negotiates its languages per app (see [internal-protocol.md](internal-protocol.md)). |
| `repository → changelog app` | staging/release | The integrated app's internal base URL, or nothing. No key — the internal network is the boundary (see [internal-protocol.md](internal-protocol.md)). |
| Version increment policy | staging/release | How a push advances the semver components (see [versioning.md](versioning.md)). |

## Global settings

Beyond the per-push resolution, Herald holds a small set of global settings, all from
the environment and never hard-coded:

- **GitHub App credentials** — App ID, private key, and webhook secret, used to verify
  incoming pushes and to authenticate as each installation (see
  [ingestion.md](ingestion.md)).
- **Telegram bot token** — the bot that posts to the resolved channels.
- **LLM backend** — the Ollama URL and model. In development Ollama is reached over an
  SSH tunnel; in production Herald sits next to Ollama on the server.

## Evolution of the backing store

The seam exists so the backing store can move without breaking anything that reads it:

1. **Environment / static config** — the current stage. The maps are small and known;
   an empty changelog map is valid and simply leaves that channel inactive.
2. **Database** — organizations, repositories, channels, and app mappings move into
   persistent storage as the number of tracked repositories grows.
3. **Multi-tenant GUI** — organizations self-manage their repositories, channels, and
   access rights through an interface, turning Herald into a service usable by many
   organizations at once.

This progression is the reason routing state is never read inline. When it arrives, a
GUI changes only what backs the resolver — the delivery and summarization code sees no
difference. Per-app access keys, unnecessary while Herald is co-located with the apps,
enter at the point the multi-tenant stage crosses a network boundary.
