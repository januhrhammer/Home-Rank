# 1. Record architecture decisions

Date: 2026-10-21

## Status

Accepted

## Context

Home-Rank will make decisions that are hard to reverse: the licence, the styling approach, the job
queue design, parts of the data model. Months later nobody remembers why a choice was made, and
re-arguing settled questions wastes time.

## Decision

We record significant decisions as Architecture Decision Records in `docs/adr/`, in Michael
Nygard's format: Context, Decision, Consequences.

- Files are numbered and named `NNNN-short-title.md`.
- An accepted ADR is not rewritten. To change a decision, write a new ADR that supersedes it and
  set the old one's status to "Superseded by NNNN".

## Consequences

- The reasoning behind a decision lives next to the code and is reviewed in the same PR.
- Writing an ADR takes some effort, so we write one only for decisions that are hard to undo or
  likely to be questioned later.
