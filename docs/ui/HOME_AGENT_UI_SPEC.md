# Home Agent UI Specification

**UI spec version:** 0.1-draft  
**Status:** Living design contract

## Purpose

This document defines how users interact with Home Agent. It complements the system specification and workflows; it does not replace them.

## Locked principles

1. **House-first, not database-first.** Normal views describe the home. Stable IDs, raw data, explicit relations and audit details belong under technical details.
2. **Mobile first.** Primary workflows must be fast and natural on a phone and scale cleanly to desktop.
3. **Context locally, work centrally.** Information belongs to its natural object, while items requiring attention are aggregated in a central **Att göra** view.
4. **One object, multiple views.** An open follow-up can appear both on its room/system/asset and in central **Att göra**, but it is the same underlying object.
5. **Central information entry.** Global **+ Lägg till** is the primary entry for unstructured text, photos and documents.
6. **AI assists interpretation.** Users should not need to choose database fields, YAML structure or archive folders. AI interprets incoming material, matches existing objects and proposes understandable changes.
7. **Approval depends on origin and risk.** Ordinary explicit manual edits can save directly. AI-proposed, destructive or structural changes require appropriate review/confirmation.
8. **Context-specific shortcuts remain.** Obvious actions such as adding a room note can be performed directly where the user already has the right context.
9. **Additive information stays additive.** Notes, observations and events are separate records rather than silently replacing previous information.
10. **History is preserved without dominating the UI.** User-facing activity is human-readable; detailed audit information is available separately.
11. **Follow-up and maintenance are distinct.** A follow-up is something to investigate or act on; maintenance is planned/recurring service or care. Both may surface centrally in **Att göra**.
12. **Human-friendly presentation.** Technical timestamps remain in storage; normal UI uses localized, readable dates and times.

## Navigation direction

Current design direction:

**Hem · Att göra · + Lägg till · Sök · Mer**

This is a design direction, not yet a frozen navigation specification.

## Room view

A room view should prioritize:
- room identity and floor/location
- concise overview
- relevant systems and equipment
- open actions/follow-ups for that room
- notes
- documents
- useful activity/history

Technical IDs, raw relations, raw YAML/data and audit details should not dominate the normal room view.

### Notes

Notes live inside a single **Anteckningar** section.

- **+ Lägg till** is an action in the section header.
- Activating it opens a small inline editor.
- Existing notes have discreet actions for **Redigera** and **Ta bort**.
- Delete requires confirmation.
- Edit/delete operations must remain traceable in history/audit.
- Display dates are human-friendly; storage timestamps remain machine-safe.

## Central Att göra

Actions belong to their source context but are aggregated centrally.

Examples include:
- open follow-ups
- due/overdue maintenance
- other actionable items defined later

The central view must not duplicate domain records.

## Central + Lägg till / AI intake

The global intake accepts at least:
- free text
- photo/camera input
- document upload

Target flow:

**Input → AI analysis → match existing objects → proposal → user review when required → local commit → deterministic archival/snapshot processes**

The user reviews semantic meaning, not implementation details such as YAML, filenames or database fields.

Simple manual context-specific input can bypass AI when interpretation is unnecessary.

## Technical details

Normal UI describes the home. Technical details describe Home Agent's representation of the home.

Technical details may include:
- stable IDs
- explicit stored relationships
- audit log
- raw structured data
- diagnostic information

## Areas still to specify

Home, floor, asset, system/component, document, maintenance, activity/history, search, central Att göra, central + Lägg till, AI proposal/review, edit/delete semantics, empty/loading/error states, responsive layout, accessibility, language and formatting.

## Design process

Use:

**Discuss → prototype → test → decide → update spec/decision log → implement → verify against spec**

Feature implementation should remain frozen at the current stable application baseline while the initial UI contract is being established.
