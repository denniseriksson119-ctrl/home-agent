# Home Agent Processing & AI Workflow Specification

**Version:** 0.1-draft  
**Status:** Normative design contract

## 1. Goal
Turn captured source material into traceable structured Home Agent knowledge without making the user manage files, database fields or processing mechanics.

## 2. Default pipeline
**Capture/Ingest → Exact dedupe → Parse/Extract → Semantic match/dedupe → Group → Analyze → Proposal → Review when required → Commit → Archive → Cleanup ingest source**

Stages may be skipped only when their purpose is not applicable. Each completed stage persists enough deterministic state to resume safely.

## 3. Capture / ingest
Backend first secures and registers the source locally with permanent IDs, origin and checksums. Ingest must not require AI.

For external channels such as Drive Inbox, successful discovery alone is not sufficient to remove the source. Home Agent first verifies that material is safely under its control.

## 4. Exact dedupe
Before expensive processing, backend checks deterministic identity such as SHA-256. Previously ingested identical content reuses the canonical source/evidence representation and records the new ingest occurrence as needed.

## 5. Parse / extract
Each source is processed into reusable extracted material: text, document fields, visible identifiers, technical metadata and other source-level observations. Extraction is stored separately from both original bytes and committed Home Graph facts.

Parsing should not need to be repeated merely because analysis is resumed later.

## 6. Semantic matching and grouping
AI may compare extracted/source information with existing Home Graph entities and other Inbox material. It may identify likely same assets, events, projects or related source groups.

This stage must distinguish:
- duplicate source material,
- different evidence about the same entity/event,
- genuinely new entities/events.

Uncertain semantic matches remain proposals.

## 7. Analysis
AI reasons over relevant grouped sources, extracted information and selected Home Graph context. It identifies useful facts, conflicts, missing information, relations and possible actions.

AI must not invent unsupported topology or facts.

## 8. Proposal
The normative AI input/output and proposal contract is defined in `docs/ai/AI_CONTRACT.md`.

Analysis produces structured semantic proposals with:
- intended operation,
- target permanent IDs when known,
- proposed new entities when necessary,
- evidence/source IDs,
- confidence,
- conflicts/unknowns,
- user decision required when applicable.

The model does not write directly to the operational database.

## 9. Review
Approval depends on origin and risk. High-confidence mechanical processing need not create pointless approvals. Uncertain semantic relationships, destructive changes and structurally significant changes receive understandable review.

The user reviews meaning, not YAML, checksums, filenames or database mechanics.

## 10. Commit
Backend validates the proposal and references, applies the accepted change atomically to the local operational database and records audit/history. Commit is distinct from analysis and archive.

## 11. Archive
Normative storage, verification and recovery semantics are defined in `docs/architecture/BACKUP_RESTORE_ARCHIVE.md`.

Once source classification/relations are sufficiently established, backend places original material in its permanent archive destination and verifies the resulting storage reference. Archive failure does not roll back a successful Home Graph commit; it remains retryable operational work.

## 12. External ingest cleanup
External drop zones such as Drive Inbox are temporary. After Home Agent has safely ingested the source and any required permanent archival has been verified, backend removes/moves the handled copy from the external Inbox.

Never delete the only verified copy. Cleanup is deterministic, retryable and separately tracked.

## 13. Persistent processing state
Normal user action is **Analysera Inbox**. Backend selects the next eligible work and AI may group likely related items automatically. Manual selection is secondary.

Processing is resumable. A user can choose **Fortsätt senare** at a safe boundary. Already completed stages are not repeated unless inputs, processing version or explicit retry policy require it.

At minimum the system must distinguish source capture, parsing, analysis, proposal/review, registration, archive and cleanup state. “Analyzed” never implies “registered”.

## 14. Idempotency and retry
Every deterministic stage must be safe to retry. Operations use stable IDs/idempotency keys as appropriate. Failures retain enough state and error information for later retry without duplicating facts, sources or archive objects.

## 15. Batch behavior
Home Agent may process many Inbox items in one run and return only meaningful decisions. Example outcome: many items completed automatically, some proposals awaiting review, and some unresolved items requiring more information.

The user does not need to decide which files belong together before analysis.
