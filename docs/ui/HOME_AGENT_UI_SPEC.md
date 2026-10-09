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
13. **Capture and processing are separate.** Users can quickly collect material now and analyze it later. Immediate AI processing must never be required just to preserve new source material.
14. **Inbox is a Home Agent concept.** Drive Inbox may be an ingest channel, but the product's Inbox/queue belongs to Home Agent and can receive material from multiple sources.

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

The intake supports two first-class paths.

### Analyze now

Input is captured safely first. The normative technical pipeline is defined in `docs/workflow/PROCESSING_AI_WORKFLOW.md`; the UI continues directly into analysis/review when requested.

### Save for later

Input is captured safely into Home Agent Inbox. Later processing follows `docs/workflow/PROCESSING_AI_WORKFLOW.md`, normally agent-led across the queue with manual selection as a secondary option.

The first screen should therefore support a primary **Analysera nu** action and a secondary **Spara i Inbox** action.

Saving to Inbox is capture, not registration of extracted facts. It must be fast and must not require the user to classify the material first.

Inbox can contain multiple related items and later analysis may consider likely related items together. This supports workflows such as collecting photos, an invoice and a manual during work in the home and processing them later.

A Drive Inbox may remain as an optional import channel. Files discovered there should be imported/registered into Home Agent Inbox; the Drive folder itself is not the operational queue or source of truth.

The user reviews semantic meaning, not implementation details such as YAML, filenames, database fields, checksums or Drive transport.

The intake offers two intents:
- **Analysera nu** — continue directly into AI analysis/review.
- **Spara i Inbox** — preserve the source quickly and defer processing.

Simple manual context-specific input can bypass AI when interpretation is unnecessary.

## Inbox / batch analysis

Inbox is the central queue for captured but not yet processed source material.

The default action is **Analysera Inbox**. The user should not normally have to select items first. Home Agent determines the next unprocessed work, groups likely related sources when useful and advances through the queue.

It should support:
- quick capture without classification
- text, photos and documents
- visible progress and understandable processing state
- default whole-Inbox processing
- automatic grouping of likely related items
- pause / **Fortsätt senare**
- deterministic resume from persisted local state
- manual selection as a secondary/advanced option
- retaining source provenance
- later semantic review before structured facts are committed

The UI must distinguish **analyzed** from **registered in Home Graph**. An item can be fully analyzed while a semantic proposal is still waiting for user review.

A Drive Inbox can remain a convenient external drop location. Home Agent imports/synchronizes those files into its own Inbox rather than treating the Drive folder as the operational queue.

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

## Asset page: linked images and documents (first delivery)

An Asset has one canonical detail page, reachable initially from **Utrustning** and later via Room/System navigation. Display a lead image and up to four thumbnails when images exist, plus a complete **Bilder & dokument** list. Images/PDFs open from verified local Source custody. Explicit manual upload or linking of an existing Source is supported without AI; source originals and names are preserved. Relationships use permanent Asset and Source IDs, not paths or filename matching. A Source may be linked to multiple assets without copying bytes. The first delivery does not infer Room/System membership or import Drive automatically.
