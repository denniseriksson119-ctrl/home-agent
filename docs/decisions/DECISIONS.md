# Home Agent Design Decisions

This log records important product/design decisions and their rationale. Git history records document changes; this file records why a direction was chosen.

## DD-001 — Context locally, actions centrally
**Status:** Accepted

Domain information belongs to the object where it originated (room, asset, system, project, etc.). Items requiring attention are also aggregated in a central **Att göra** view. Aggregation must not create duplicate domain records.

## DD-002 — Central AI-assisted intake
**Status:** Accepted

Unstructured new information should primarily enter through a global **+ Lägg till** flow supporting text, photos and documents. AI helps interpret and connect the information. Users should approve semantic proposals when required rather than manage storage structure.

## DD-003 — Keep contextual shortcuts
**Status:** Accepted

Central intake does not replace obvious local actions. For example, adding a simple note while viewing a room should be possible directly in that room.

## DD-004 — Approval depends on origin and risk
**Status:** Accepted

Ordinary explicit manual edits can save directly. AI-proposed changes require semantic review. Destructive or structurally risky manual operations may require confirmation.

## DD-005 — Living UI specification
**Status:** Accepted

UI design is specified incrementally alongside prototypes. Important decisions are added to the UI spec and this decision log before implementation so later ideas can be checked against earlier principles.
