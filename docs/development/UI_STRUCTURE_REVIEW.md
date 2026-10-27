# Numbered UI review — 2026-10-27

The owner approved progressing with the existing architecture, knowledge-first
presentation and a prototype-led, staged delivery. Numbers below are stable
conversation references, not implementation or release status.

| No. | Scope | Decision / remaining work |
| --- | --- | --- |
| 1 | Inline note edit, Save/Cancel | Behavior approved; layout review pending. |
| 2 | Note delete beside the note, with confirmation | Behavior approved; audit retained. |
| 3 | Calendar date only in notes | Approved; precise timestamps stay internal. |
| 4 | Original date and discreet edited marker | Approved; prior state remains traceable. |
| 5 | Note purpose, object links, event date, AI analysis | Paused; no new semantics authorized. |
| 6 | System / Component / Asset / location | Keep existing model; inspect data separately before proposing corrections. |
| 7 | Human-readable supported relationships | Direction approved; specific labels/layout to review. |
| 8 | System overview and detail panel | Prototype direction approved; final layout pending. |
| 9 | Structure-review table | Candidate for later prototype; no automatic corrections. |
| 10 | Context on object pages | Direction approved; final layout pending. |
| 11 | Prototypes and staged rollout | Approved; no all-at-once production rollout. |
| 12 | Registered knowledge first, sources as evidence | Approved direction; retain provenance and immutable originals. |

## Review and delivery

First review A (object context, knowledge, note actions), then B (system
navigation, functional component and physical product presentation). Use synthetic
fixtures for tracked examples. Real household working examples stay private and
outside the public repository.

Check on mobile as well as desktop: understand context without technical IDs;
follow a real supported relationship; navigate back without losing place; edit,
cancel and confirm deletion; see only dates; distinguish registered knowledge,
unknowns and illustrative/proposed data; inspect evidence when needed.

Implement note controls as one bounded release after layout review, then the
selected object/system presentation as separately reviewable changes. No database
reclassification, entity merge, source relinking or automatic AI write is implied.
Existing asset/source links and permanent IDs remain intact. Installed add-on
changes require their own version bump, automated checks, PR and owner Pi
acceptance. This documentation-only change needs no add-on version bump.

The private HTML prototype is exploratory, not the production UI contract. Final
UI details and exact release boundaries remain to be agreed after review.
