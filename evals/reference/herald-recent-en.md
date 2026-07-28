Herald now carries a release all the way through — from working out what the deployment covers to a published GitHub release and a notification that names the version.

- **Since-last-deploy window** — a release note covers everything accumulated since the previous deployment to that environment rather than a fixed calendar period. It lands as its own module, with tests.
- **The note is a report** — the release note is built by the shared reporting engine instead of a second, parallel mechanism of its own.
- **The release reaches its channel** — a push to a release branch cuts a GitHub release carrying the note, and the Telegram message gains a version header. A GitHub Releases client is added, wired through event intake, delivery, and the application root.
