# Home Agent Backup, Restore & Archive Specification

**Version:** 0.1-draft
**Status:** Normative design contract

## Purpose
Protect operational data and original source material without making Drive part of the runtime database. Operational backup, logical export, permanent source archive and external ingest are separate functions.

## Storage roles
Local Home Agent storage is the operational source of truth and holds the database, durable processing state, mappings and audit/history needed to resume safely.

Google Drive is for permanent original-source archive when applicable, off-device backups, logical exports/snapshots and optional Inbox ingestion. Drive is not the runtime database. GitHub contains code/specs only, never private house backups or secrets.

## Artifact classes
**Operational backup** restores Home Agent operation and preserves permanent IDs, relations, processing state and required history.

**Logical export** is a portable representation for inspection, migration or diagnostics. It is not automatically a complete disaster-recovery backup.

**Permanent source archive** stores unchanged original evidence such as photos, PDFs, manuals and invoices. Metadata/provenance remains separate.

## Backup integrity
Backup creation is deterministic backend work and requires no semantic approval. Each artifact records a backup ID, format/schema version, creation time, checksum, scope/manifest and verification status.

Database backup must represent a transactionally consistent state. A live SQLite file must not be copied using a method that can produce an inconsistent database.

A backup is successful only after its artifact and integrity are verified.

## Drive failure
Local commits never wait for Drive. Off-device backup/archive work is asynchronous and retryable. Drive failure does not invalidate a successful local commit and must not be reported as a successful backup.

## Scheduling and retention
Support scheduled, explicit manual and appropriate pre-risk/schema-migration backups. Retention is deterministic policy, not AI judgment. Rotation must never remove the only verified recoverable backup.

Exact cadence and retention counts are deployment policy and are intentionally deferred until operating/storage behavior is measured.

## Restore
Restore is an explicit risky administrative operation and requires confirmation.

Flow:
**Select backup → verify manifest/checksum/version → validate compatibility → protect current state → restore in controlled location → validate database/schema/references → activate → record restore event**

Failed validation must not silently replace working state. Restored entities retain their permanent IDs; device replacement never regenerates identity.

## Restore verification
Uploaded files alone do not prove recoverability. Home Agent must support non-destructive restore verification that can read the artifact, verify manifest/checksums, open/validate the database, check schema/migration compatibility and detect missing required components.

Periodic automated restore verification is a target capability; exact cadence is deployment policy.

## Permanent source archive
Archiving a Source is separate from database backup.

**Physical storage is for human findability and preservation. Semantic organization belongs to Home Graph.** Archive paths, folders and filenames never encode required domain relationships or identity.

The archive is deliberately human-browsable using coarse, stable categories rather than Room/Asset/System trees. Recommended Drive shape:

```text
Home Agent/
  Inbox/
  Archive/
    Photos/
      YYYY/
        MM/
    Documents/
      Manuals/
      Invoices/
      Receipts/
      Warranties/
      Other/
    Other/
  Backups/
  Exports/
```

Document categories may add year subfolders when volume justifies it. The system must not require pre-creating empty folders.

Files should receive a human-readable archive filename based on date + short description + short Source-ID hint, for example:
`2026-10-08_heat-pump-rating-plate__src-a81f3c.jpg`

The short suffix is a convenience hint, not identity. The complete permanent Source ID remains in the database. Original filename is retained as metadata.

Renaming/moving an archive file does not change Source identity. File contents/original bytes are not modified by archival naming.

A Source may relate simultaneously to Room, Asset, System, Project and Event without copies being placed in corresponding semantic folders. Those relationships exist in Home Graph.

Archive operations record external storage references and verification state locally.

## Drive Inbox handoff and cleanup
Drive Inbox is a temporary ingest/drop zone.

**Discover → create IngestOccurrence → import/copy → resolve canonical Source by checksum → verify Home Agent custody → process → archive when applicable → verify archive → clean IngestOccurrence/external Inbox item**

Never delete the only verified copy. If permanent Drive archive is required, cleanup happens only after archive verification.

Cleanup is deterministic, auditable and retryable. Exact delete-vs-move behavior and grace period remain deployment policy, but successfully handled items must not accumulate indefinitely in Drive Inbox.

## Duplicate ingest
If Drive Inbox contains bytes already represented by a canonical Source, exact dedupe happens before expensive processing. Home Agent verifies safe custody, records the ingest occurrence as needed, avoids creating a duplicate canonical archive object, then uses the normal safe cleanup path.

## External references
Drive/provider IDs, paths and filenames are external storage references, not Home Agent identity. Provenance survives cleanup of temporary ingest occurrences.

## Security
Backups and archives contain private household data and never belong in the public Git repository. Credentials/tokens are not embedded in portable backup manifests/exports. Credential storage and Drive authorization scope follow `SECURITY_RUNTIME.md`. Encryption-at-rest/backup encryption policy remains to be selected before production use.

## Disaster recovery target
A replacement Home Agent installation can recover operational state from a verified backup and reconnect archived sources using stored IDs/checksums/references. Recovery must not depend on chat memory, legacy textual room IDs or a particular Raspberry Pi filesystem path.

## Operational status
Home Agent should expose last verified backup, backup failure/pending state, last restore verification, archive failures and external Inbox cleanup failures without making storage mechanics dominate normal UI.
