# Summarization

Summarization turns the commits behind a push into release notes — a digest of the
key changes written for a human reader, not a mechanical list of commit messages. The
LLM is the whole point: it decides what matters and phrases it, rather than
concatenating a log.

## From commits to a digest

The pipeline runs in stages, each a self-contained boundary:

1. **Collection** — Herald reads the commits behind the push directly from git:
   messages, changed file paths, and per-file diffstats, immutable value objects with
   no network or mutation. The range collected depends on the branch role (see
   [Range and accumulation](#range-and-accumulation)).
2. **Context building** — the collected commits are rendered into a plain-text prompt.
   Richer input raises quality more than a bigger model does, so the context carries
   the commit messages, changed paths, and diffstats, and grows to include PR titles
   and bodies and a short per-repository project map where available.
3. **Two-stage generation** — stage one produces an atomic summary per commit or PR;
   stage two aggregates those into a single digest. Splitting the work keeps each LLM
   call inside the model's competence zone instead of asking one call to reason over
   an entire push at once.

The output is always a digest of key moments. Even a day-to-day push is summarized by
what is significant, never as one line per commit.

## Range and accumulation

How far back the collected range reaches depends on the branch role:

| Role | Range | Digest covers |
|------|-------|---------------|
| `dev` and other non-release branches | commits since the last push to that branch | the key changes in this push |
| `staging`, `release` | commits accumulated since the previous deploy to that environment | the key changes across the whole period, by highlight |

For staging and release branches, notes are built from history collected since the
last deploy, never from a single push in isolation — so a release note reflects
everything that has landed since the previous release, condensed to what matters.

## The LLM boundary

The LLM sits behind a model-agnostic boundary: business logic depends on an abstract
client that exposes a single "generate text from a prompt" operation and names no
Ollama concept. The concrete backend — a local Ollama model today — is wired in only
at the composition root and swaps for a larger or hosted model without touching the
summarization logic. Timeouts and transport errors surface as failures rather than a
silently empty summary.

## Languages of generation

The summary is generated in every language the push's active channels require, and
each language is a separate generation. The set of required languages is the union
across the active channels for this `(organization, repository, branch)`:

- a `dev` push needs only Russian — Telegram's one language;
- a `release` push to a repository with no integrated app needs Russian for Telegram
  and English for the GitHub release — two single-language channels, one generation each;
- a `release` push to a repository whose app declares `["ru", "en"]` needs the same
  Russian and English, but now the app store consumes both while Telegram still takes
  only Russian and the GitHub release only English.

Each fixed channel — Telegram and the GitHub release — delivers in exactly one
language; only the app changelog store carries several. Generating the union means a
language produced once feeds every channel that asks for it, not that any fixed channel
becomes multilingual. Which channel consumes which language is a delivery concern — see
[delivery.md](delivery.md). Summarization's responsibility ends at producing each
required language.

## Quality is measured, not eyeballed

Summary quality is checked against fixed cases rather than judged ad hoc. A case set
pins `{repository, range, language}` inputs against user-authored reference notes, and
the harness writes one output per case under stable filenames for diffing against the
references. Any change to the prompt or the model is run through the harness before it
is trusted, and approved notes fold back into the case set and the few-shot prompt so
quality compounds over time.
