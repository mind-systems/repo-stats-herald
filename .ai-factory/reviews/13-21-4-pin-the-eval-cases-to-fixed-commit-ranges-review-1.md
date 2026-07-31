# Review: 21.4 — Pin the eval cases to fixed commit ranges

## Scope
Sole code change is `evals/cases.yaml`. The staged plan artifacts (`.ai-factory/plans/*`, `.ai-factory/plan-reviews/*`) are non-code and out of review scope.

## Verification performed
- **Diff is minimal and on-target.** Only the three `range` values changed (`herald-recent`, `herald-recent-en`, `herald-localize`), each from `HEAD~3..HEAD` to `0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe`, plus explanatory comments. No `name`, `type`, `repo`, `lang`, or `langs` field was altered.
- **Guards honored.** Case names unchanged, so no output/reference filename moves. The two rangeless cases (`mind-features`, `herald-self-query`) are untouched. No reference note authored or seeded.
- **Both commits exist** (`git cat-file -t` → `commit` for each) and the range resolves **non-empty** — 3 commits (`366e882`, `e3972ec`, `1bb7597`) — so linked-change resolution will not be empty.
- **YAML parses.** `yaml.safe_load` succeeds: 6 cases, the three pinned ranges present, two `<none>` rangeless cases intact.
- **Comment accuracy.** Every reference file named in the new comments exists under `evals/reference/` (`herald-recent.md`, `herald-recent-en.md`, `herald-localize.md`).
- **Pattern consistency.** The pinned range and comment style mirror the pre-existing `herald-narrate` case exactly.

No bugs, security issues, or correctness problems found. There is no runtime code, migration, or type surface touched — this is a fixture-config change.

REVIEW_PASS
