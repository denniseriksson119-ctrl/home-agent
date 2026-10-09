# Google Drive import – security and delivery plan

## Trust boundary

- The owner's private Google account owns the original archive and future backups.
- A dedicated import Google account has read access only to an explicitly shared source tree.
- Home Agent import must use that dedicated account, never a token for the owner's private account.
- Backup to the private account is a separate future integration, with separate credentials and permissions.
- No Drive cleanup, moves, edits or deletions are permitted from import.

## Initial transport (this branch)

`drive_import.py` provides a read-only Google Drive API transport for a *caller-provided*
short-lived OAuth access token. It retrieves metadata and streams a binary file into a
temporary local file while hashing SHA256 and enforcing a size limit.

**Not yet wired into the application.** There is no sign-in screen, token persistence,
folder traversal authorization, import transaction, UI action, or backup feature in this
branch. It must not be described as a working end-to-end Drive importer.

## Requirements before enabling import

1. Configure a Google OAuth client and implement a safe sign-in/callback flow for the
   dedicated import account. Do not store access tokens in logs, YAML snapshots, or
   unencrypted backup archives.
2. Validate the signed-in Google account against an explicit approved identity.
3. Validate the selected file is under the configured shared root by traversing its
   parent chain; fail closed if the chain cannot be established. A UI folder filter
   alone is not an authorization boundary.
4. Decide and document the requested Drive OAuth scope. Broad `drive.readonly`
   access can read everything the dedicated account can access, not only a UI-selected
   folder. The shared-account isolation is an additional control, not a scope guarantee.
5. Atomically register Source and IngestOccurrence with external provider/ref metadata,
   deduplicate on SHA256, and link to an explicit permanent Asset ID. Preserve original
   bytes and filenames; do not mirror the Drive folder tree.
6. Stream into the content-addressed store with cleanup on error, bounded disk usage,
   and explicit verification. Avoid loading 11.8 MB manuals into Pi RAM all at once.
7. Add tests for revoked credentials, malformed IDs, wrong account, files outside the
   shared tree, interrupted downloads, oversized files, SHA256 duplicates, and repeat
   imports. Review file serving and network access protections before release.
8. Add explicit user-facing confirmation before importing selected files.

## First acceptance case

Asset `eq_heat_pump_nibe_s1255`: import the already identified JPEG, product sheet,
installer handbook and user handbook, with independent per-file success/failure results.
The JPEG's content has not yet been visually verified; do not label it a confirmed
rating-plate photo until inspected.

## Future backup

Backup belongs to a distinct subsystem. It must create a consistent SQLite snapshot,
include original Source bytes and a verifiable manifest, encrypt before upload, preserve
multiple restore points, and support a restore test. The import token must never acquire
write access to the owner's private Drive.
