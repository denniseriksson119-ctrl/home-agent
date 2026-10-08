# Home Agent Data Model Specification

**Version:** 0.2-draft  
**Status:** Normative design contract

## 1. Scope
Defines identity, provenance, source custody and persistence semantics independently of the current SQLite implementation.

## 2. Permanent identity
Every persistent entity has an opaque, immutable, machine-generated internal ID. Target format: **UUIDv7**.

Names, slugs, addresses, filenames, model numbers and other mutable values are attributes, never identity. Internal relations use permanent internal IDs. External/legacy identifiers are mappings only.

This applies to Home, Person, Membership, Floor, Room, Space, System, Component, Asset, Document, Source, IngestOccurrence, InboxItem, Event, Project, Maintenance, FollowUp, Expense, Warranty, Proposal and other persistent entities.

## 3. Legacy migration
Textual IDs imported from bootstrap/YAML are legacy import keys. Migration assigns permanent IDs and retains old keys only where useful for traceability. Renaming never changes identity.

## 4. Source
A **Source** is the canonical Home Agent representation of original evidence: photo, PDF, document, captured text or other source material.

A Source records at minimum permanent ID, media/type, original name when relevant, cryptographic checksum when bytes exist, capture/import timestamps and storage references.

Original bytes are preserved unchanged. Extracted metadata, AI interpretations and Home Graph facts are separate records/relations.

## 5. IngestOccurrence
An **IngestOccurrence** represents one arrival/observation of source material through a channel such as Home Agent upload, camera or Drive Inbox.

It has its own permanent ID and records channel, external provider/path/reference when relevant, observed/imported timestamps, cleanup state and the resolved Source ID.

Several IngestOccurrences may resolve to one Source after exact dedupe. This preserves the fact that material arrived again without duplicating the canonical original.

## 6. InboxItem
An **InboxItem** represents persistent processing work. It references a Source and, when useful, the IngestOccurrence that created the work.

InboxItem is not the original file and is not a Home Graph fact. It exists so work can be paused, reviewed, retried and resumed without relying on chat/AI memory.

A Source can remain valid after its InboxItem is completed and after an external IngestOccurrence is cleaned up.

## 7. Source custody
Before destructive cleanup of an external ingest location, Home Agent must have verified custody of the canonical Source.

Custody means Home Agent has a durable controlled copy or an already verified canonical copy with matching identity/checksum sufficient to continue processing safely.

Semantic classification is not required to establish custody.

## 8. Deduplication
Exact binary duplicates are detected deterministically, normally using SHA-256. Repeated identical bytes reuse the canonical Source while retaining distinct IngestOccurrence history as needed.

Near-duplicate content may be flagged semantically/perceptually; uncertain matches are not silently destroyed.

Different Sources depicting/describing the same real-world entity are separate evidence and may reference the same Asset/Event/etc.

**Deduplicate representation, not evidence.**

## 9. Processing state model
Processing state is durable and explicit. At minimum Home Agent represents these semantic states/transitions:

**captured → dedupe_checked → parsed → analyzed → proposal_pending/review_pending when needed → registered when accepted/automatic → archive_pending → archived → cleanup_pending → completed**

Not every Source requires every state. Rejection may produce **rejected/completed** without registration. A failure produces a retryable failure state associated with the stage that failed rather than erasing earlier successful stages.

Important invariants:
- analyzed does not mean registered;
- registered does not mean archived;
- archived does not mean external ingest cleanup succeeded;
- completed means no required processing/cleanup remains for that InboxItem;
- pause occurs only at a durable safe boundary;
- retry resumes from the failed/pending stage and does not repeat successful side effects.

Implementation may use separate stage/status fields rather than one enum if that better preserves these distinctions.

## 10. Facts, confidence and provenance
Extracted observations retain Source provenance. Structured facts/relations may carry Confirmed, Likely or Unknown confidence where useful. Conflicting supported claims are explicit rather than silently overwritten.

## 11. Proposals and writes
AI output is a proposal, not a direct mutation. Proposals reference permanent IDs and Source evidence. Backend validates references and performs atomic domain write + audit/history.

Manual low-risk edits may bypass AI but use the same identity, validation and audit rules.

## 12. History and deletion
Important history is event-based. Edits do not silently erase relevant prior state. Deletion preserves required audit/provenance; hard deletion of evidence-bearing records is not the default.

## 13. Storage independence
SQLite is the current implementation, not the domain model. Schema migrations are deterministic/versioned. YAML is bootstrap/import/export/diagnostic material, not runtime identity or operational source of truth.
