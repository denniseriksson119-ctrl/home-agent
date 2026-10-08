# Home Agent Data Model Specification

**Version:** 0.1-draft  
**Status:** Normative design contract

## 1. Scope
Defines identity, provenance and persistence semantics independently of the current SQLite implementation.

## 2. Permanent identity
Every persistent entity has an opaque, immutable, machine-generated internal ID. Target format: **UUIDv7**.

Names, slugs, addresses, filenames, model numbers and other mutable values are attributes, never identity. All internal relations use permanent internal IDs. External/legacy identifiers are stored separately as mappings.

This applies to Home, Person, Membership, Floor, Room, Space, System, Component, Asset, Document, Source, InboxItem, Event, Project, Maintenance, FollowUp, Expense, Warranty, Proposal and other persistent entities.

## 3. Legacy migration
Textual IDs imported from bootstrap/YAML are legacy import keys, not future primary keys. Migration assigns permanent IDs and retains legacy keys only where needed for traceability. Renaming an object never changes its internal ID.

## 4. Source material and provenance
Original source material is distinct from extracted metadata and Home Graph facts.

A Source records at minimum: permanent ID, media/type, origin channel, original name when relevant, cryptographic checksum when bytes exist, capture/import timestamps, storage references and processing state.

Extracted observations retain provenance to one or more Source IDs. AI interpretations never overwrite originals.

## 5. Inbox
InboxItem represents work waiting in Home Agent's persistent processing queue. It references source material rather than making that material a Home Graph fact.

Capture, parsing, analysis, proposal/review, registration, archival and external-ingest cleanup are separate states. State is persisted locally and must not depend on chat/LLM memory.

## 6. Deduplication
Exact binary duplicates are detected deterministically, normally using SHA-256. A repeated ingest of identical bytes must not create a second canonical original merely because filename or channel differs.

Near-duplicate content may be flagged semantically/perceptually; uncertain matches are not silently deleted.

Different sources depicting/describing the same real-world entity are not source duplicates. They remain separate evidence and may reference the same Asset/Event/etc.

**Deduplicate representation, not evidence.**

## 7. Facts, confidence and evidence
Structured facts and relations may carry Confirmed, Likely or Unknown confidence where useful. Important claims retain evidence/provenance. Conflicting supported claims are represented explicitly rather than silently overwritten.

## 8. Proposals and writes
AI output is a proposal, not a direct database mutation. Proposals reference permanent IDs and source evidence. Backend validates all references and performs atomic domain write + audit/history.

Manual low-risk edits may bypass AI but still use the same identity, validation and audit rules.

## 9. History and deletion
Important history is event-based. Edits do not silently erase relevant prior state. Deletion semantics must preserve required audit/history; hard deletion of evidence-bearing records is not the default.

## 10. Storage independence
SQLite is the current implementation, not the domain model. Schema migrations are deterministic and versioned. YAML is bootstrap/import/export/diagnostic material, not runtime identity or operational source of truth.
