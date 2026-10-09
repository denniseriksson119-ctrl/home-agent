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


## DD-011 — Capture and processing are separate
**Status:** Accepted

Users must be able to capture source material immediately without being forced to run AI analysis or complete structured registration at that moment. The product supports both “analyze now” and “save to Inbox for later”.

## DD-012 — Inbox belongs to Home Agent
**Status:** Accepted

Inbox is a Home Agent queue/domain concept for unprocessed source material and can receive input from multiple channels. Google Drive Inbox may remain a convenient ingest/drop channel, but it is not the operational Inbox or source of truth.

## DD-013 — Batch analysis is first-class
**Status:** Accepted

Users can later analyze multiple Inbox items together. Joint analysis is allowed and encouraged when several sources may describe the same event, object or work, while every extracted fact retains source provenance.


## DD-014 — Analyze Inbox is the default
**Status:** Accepted

The normal Inbox action is **Analysera Inbox**. Users should not need to preselect files or understand which sources belong together before analysis. Home Agent works through the queue and groups likely related material when useful. Manual selection remains a secondary option.

## DD-015 — Inbox is a persistent stateful work queue
**Status:** Accepted

Backend state, not AI/chat memory, records Inbox progression. Analysis, proposal/review, structured registration and archival are distinct states. Processing can be paused and resumed later without redoing completed work.

## DD-016 — Analysis can pause and resume
**Status:** Accepted

A long Inbox run can stop at a safe boundary via **Fortsätt senare**. The next run resumes from persisted local state and clearly distinguishes completed, waiting-for-review and remaining work.


## DD-017 — Opaque permanent internal IDs
**Status:** Accepted

Every persistent entity uses an opaque immutable machine-generated internal ID, targeting UUIDv7. Names, slugs, addresses, filenames, model numbers and legacy/external IDs are mutable attributes or mappings and never internal identity. Imported textual IDs are migration aliases only.

## DD-018 — Layered deduplication
**Status:** Accepted

Home Agent distinguishes exact byte-level source deduplication, probable semantic/perceptual source duplication and domain entity matching. Exact duplicates are handled deterministically before expensive processing. Distinct evidence is preserved even when several Sources describe the same real-world entity.

## DD-019 — Resumable staged processing pipeline
**Status:** Accepted

Inbox processing is staged: ingest, dedupe, parse/extract, semantic matching/grouping/analysis, proposal, review, commit, archive and cleanup. Durable state is persisted so processing can pause/retry/resume without AI/chat memory or repeating completed work.

## DD-020 — Drive Inbox cleanup only after verified custody
**Status:** Accepted

Drive Inbox is a temporary ingest channel. An item is removed only after Home Agent has verified safe custody and, where applicable, successful permanent archival. Cleanup failure remains retryable and does not invalidate successful local processing.


## DD-021 — AI returns proposals, never direct writes
**Status:** Accepted

AI output is untrusted structured semantic input. The backend validates IDs, schema, operations, authorization and current state, assigns permanent IDs for new entities, and owns all database writes and side effects.

## DD-022 — AI context is bounded and source-aware
**Status:** Accepted

Backend supplies only relevant source material/extractions, existing entities with permanent IDs and task context. AI distinguishes source observations, committed facts, explicit user input and inference. Missing facts remain unknown.

## DD-023 — Proposal facts retain evidence
**Status:** Accepted

Confidence belongs to individual claims/matches. Proposed operations retain supporting Source IDs/evidence. Grouped analysis never removes per-source provenance.

## DD-024 — Proposal application is idempotent and stale-safe
**Status:** Accepted

Proposal/run identity is stable. Replaying an accepted proposal cannot duplicate effects. Backend revalidates current state before commit and does not blindly apply proposals based on stale context.


## DD-025 — Backup, export and source archive are separate
**Status:** Accepted

Operational backup, logical export and permanent original-source archive are distinct artifact classes with different purposes.

## DD-026 — Local commits do not depend on Drive backup
**Status:** Accepted

A validated atomic local commit is complete without waiting for Drive. Backup/archive synchronization is asynchronous, verified and retryable.

## DD-027 — Restore preserves permanent identity
**Status:** Accepted

Restore or device replacement preserves stored permanent entity IDs and validates integrity/compatibility before active state is replaced.

## DD-028 — Backups require restore verification
**Status:** Accepted

Uploaded artifacts alone do not prove recoverability. Backup design includes checksum/manifest validation and a non-destructive restore verification path.

## DD-029 — Archive paths are not identity
**Status:** Accepted

Source/domain identity remains permanent when archived files move or are renamed. Drive paths and provider IDs are external references only.


## DD-030 — Public repo contains no private household data
**Status:** Accepted

The public repository contains reusable code/specs and synthetic fixtures only. Real household data, source material, production snapshots and credentials stay in private runtime/archive storage.

## DD-031 — Secrets are runtime configuration
**Status:** Accepted

Provider credentials are not domain data, model context or portable exports. Backend owns credentials and external integrations use least privilege.

## DD-032 — Home Assistant hosts but does not own Home Agent data
**Status:** Accepted

The current deployment is a Home Assistant OS add-on using platform persistent storage. Home Agent remains a separate service/domain and integrates with Home Assistant through supported APIs rather than a shared database.

## DD-033 — Runtime state is portable across hosts
**Status:** Accepted

Domain identity and recovery semantics do not depend on Raspberry Pi disk paths, container paths, SQLite row IDs or Home Assistant internals. Permanent IDs and verified restore enable later host migration.

## DD-034 — External integration failure is isolated
**Status:** Accepted

AI, Drive or Home Assistant outages must not corrupt local operational state or unnecessarily disable unrelated local operations. Integration work is validated, retryable and idempotent where applicable.


## DD-035 — Source, IngestOccurrence and InboxItem are separate identities
**Status:** Accepted

Source is canonical evidence, IngestOccurrence records each arrival/channel occurrence, and InboxItem records persistent processing work. Exact duplicate arrivals may resolve to one Source without losing ingest provenance.

## DD-036 — Source custody precedes semantic classification
**Status:** Accepted

Home Agent secures/verifies local custody and checksum before relying on AI classification or cleaning an external ingest location. Classification is not required to preserve an original safely.

## DD-037 — Archive is human-browsable but semantically neutral
**Status:** Accepted

Physical archive folders and filenames optimize human findability and preservation. Home Graph references carry Room/Asset/System/Project/Event meaning. Archive paths never encode required domain relationships or identity.

## DD-038 — Archive uses coarse type/time organization
**Status:** Accepted

Default archive organization uses coarse categories such as Photos by year/month and Documents by stable document type, optionally year. It does not create canonical per-room/per-asset/per-system folder trees.

## DD-039 — Human-readable archive names do not define identity
**Status:** Accepted

Archived files may be renamed to date + short description + short Source-ID hint while original filename remains metadata and original bytes remain unchanged. Full permanent Source ID and checksum remain authoritative.

## DD-040 — Processing state transitions are explicit and resumable
**Status:** Accepted

Captured, dedupe-checked, parsed, analyzed, review/proposal, registered, archive, cleanup and completion are distinguishable durable states. Failure/retry never erases prior successful stages; analyzed does not imply registered and archived does not imply cleanup completed.

## DD-024 — Asset-first resource presentation
**Status:** Accepted

Start with one canonical Asset detail page displaying a lead image, thumbnails and a complete **Bilder & dokument** section. Files are immutable Sources with explicit permanent-ID links, not copies in semantic folders. Contextual manual upload and reuse of existing Sources are supported. Room/System navigation can link to the same Asset page later. Legacy Drive paths are provenance, not the storage model.
