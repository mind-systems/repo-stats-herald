# Version Increment Policy (concept)

A forward-looking design. [Versioning](../behavior/delivery.md#versioning) assigns a
version to every staging and default-branch push that carries new work, but the
increment component — whether a bump advances the major, minor, or patch part of the
semver — is a fixed configuration value today, applied identically to every push. This
concept describes how that fixed value becomes a **policy seam**, with the reasoner
standing behind it as the judge of a change's significance. It is written as the target
contract; it is not built, and the fixed default stays the shipping behavior until the
reasoner-driven policy earns its place.

## The number moves, but its size says nothing

A version bump today is uniform: patch by default, every time, whether the change is a
breaking rewrite, a new capability, or a one-line fix. The version still climbs — a
consumer sees `v1.2.0` become `v1.2.1` and knows *something* shipped — but the semver
convention itself carries a promise the fixed increment never keeps: that the *size* of
the jump reflects the *size* of the change. A breaking change and a typo fix read
identically in the version history.

## The policy seam

The increment stops being a value and becomes a policy. The versioner consumes an
increment-policy abstraction rather than reading a fixed component directly; the
current fixed-component behavior becomes the trivial policy and stays the default. Two
further policies stand behind the same seam:

- a **manual override**, for a human who wants to state the significance explicitly
  rather than have it inferred;
- a **reasoner-driven judgment**, which infers it from the change itself.

Because the seam is the same one the fixed policy already occupies, adopting either
richer policy is a configuration change, not a rewrite of versioning.

## Reasoner-driven policy

The reasoner-driven policy's input is the change set since the last version — the same
deploy-anchored accumulation the release note itself narrates, already resolved for
that purpose. Its output is one of `major`, `minor`, or `patch`. The reasoner judges
this the way it judges everything else: grounded in the project's own standing memory,
not in a diff line count. A change that breaks a public contract reads as major; a
genuinely new capability reads as minor; a fix or an internal adjustment reads as patch.
The judgment is a semantic read of *what the change means to the project*, the same
faculty the reasoner already brings to narration — turned here toward a single
three-way classification instead of prose.

## Precedence

The three policies do not compete freely; they resolve in a fixed order. A manual
override — an explicit signal a human attaches to the change, such as a commit trailer
or a label — wins outright when present. Absent that, the reasoner's judgment applies.
Absent both, the configured default component is the floor every push always has.

## Degradation

A release is never blocked on the reasoner's availability. When the reasoner cannot be
reached, or its judgment carries too little confidence to trust, the policy falls back
to the configured default component and the version is still cut — the same
never-blocks stance the changelog channel already takes when an integrated app is
unreachable: a richer channel's absence degrades the outcome, never halts it.

## The determinism boundary

Versioning today is pure git-derivation: given the same tags and history, the same
version comes out, every time. A reasoner-driven judgment breaks that purity — it is a
model call, and model calls are not guaranteed reproducible. This concept accepts that
departure deliberately, but bounds it tightly: the judgment runs exactly once, at the
moment the version is assigned, and its result is recorded as the git tag itself — the
same authoritative record versioning already treats as ground truth. Every read of the
version afterward comes from that tag, never from a second invocation of the policy, so
reproducibility holds on every side of the one moment where judgment enters.

## Open

Left to decomposition, not resolved here:

- how the reasoner's significance judgment maps onto the three semver components —
  what it reads, and how that reading is prompted;
- how a manual override is signaled and where it is read from;
- whether a confidence threshold gates the fallback, and what "unsure enough to
  degrade" means concretely.
