# Conversation

How a person asks Herald about the projects it understands and gets a reasoned answer. Conversation is the read side of Herald's memory: the same understanding that drives [narration](narration.md) is here turned toward a question instead of a push. Narration and conversation are two projections of one [reasoner](../architecture.md#the-two-engines-over-the-event-stream) — one speaks on a change, the other answers a question.

## What it is for

A person can ask Herald about any project without opening an agent in that repository and rehydrating it from scratch each time. Herald is always in the know — it holds a standing model of every project it serves and a log of how each has changed — so a question is answered from what it already understands, not from a fresh read of the code.

A question can be about:

- **a project's present** — what it is now: its features, direction, and what is built versus remaining, from its [semantic memory](understanding.md#per-project-knowledge-model);
- **a project's evolution** — what a feature was, when it changed, why something was dropped, from its [episodic memory](../architecture.md#the-two-engines-over-the-event-stream), the log of how the project changed;
- **the ecosystem** — how projects connect and what a change in one moves in another, across the [project graph](understanding.md#project-graph) and org-wide retrieval.

## How a question is answered

A question reaches the reasoner. The reasoner retrieves what bears on it — the relevant slices of the project's present and its history, and the neighbouring projects it touches — and synthesises a single reasoned answer in human language. This synthesis is Herald's own: retrieval surfaces related material, and the reasoner turns it into an answer rather than returning a list of matches.

The answer is grounded in what Herald holds. Where no memory bears on a question, Herald says so rather than inventing one.

## Scope of a question

A question carries an optional project scope. Scoped to a project, the answer reasons from that project's memory first and reaches to its neighbours where they bear on the question. Unscoped, the question is answered across the ecosystem — Herald draws on every project it serves.

## Single question, standing memory

Each question is self-contained: it is answered from Herald's standing memory, not from a memory of the conversation itself. The depth of an answer comes from what Herald knows about the subject, not from what was asked before it.

## The surface

The interaction is a plain request and response — a question, with its optional scope, in; a reasoned answer out. This surface is channel-agnostic: it is the seam a front-end speaks to, whether that front-end is a chat interface, the same bot that carries Herald's announcements, or a command line. The surface holds no reasoning of its own; it carries the question to the reasoner and the answer back.

## The model that answers

The reasoner sits behind a model-agnostic boundary (see [the LLM boundary](narration.md#the-llm-boundary)). The model that answers is a configured choice over one knowledge base: a local model answers by default, and a larger hosted model answers where a richer analysis is wanted. The tier changes the reader, not the index — the same memory backs every answer, so a stronger model reasons over the same ground rather than requiring a different one.
