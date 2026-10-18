# Changelog

## 0.8.6

- Connect Google Drive from a phone using Google's device authorization flow: Pi requests/polls, the user enters a code and approves at Google.
- Separate client ID, client secret and expected account in Home Assistant configuration. No terminal, desktop script or manual token-file transfer for this setup path.
- Account/scope validation, expiring/cancellable persisted attempts, safe retries/restart and local Origin/Host/CSRF checks. Credentials stay on Pi; existing manual connections remain supported.
- Successful connection wakes the existing Drive publisher immediately. Real Google/Pi/phone acceptance still required.

## 0.8.5

- Opt-in automatic publication of a small house index, selected NIBE facts, explicit service/maintenance references and SHA-256-checked linked originals to a separate private Drive folder.
- Separate `drive.file` OAuth setup; existing read-only Drive import unchanged. No model API, new public Pi endpoint or domain writes.
- Resumable publication with reserved Drive IDs, sources/context before index, revision/timestamps and status under Mer. Retries every 15 minutes after each attempt.
- Pi/Google/ChatGPT phone acceptance required; no proposal return/import or retention cleanup in this slice.

## 0.7.0d1

- Room-note snapshot persistence and audit logging now commit atomically in one SQLite transaction.
- Keeps the 0.7c schema-v3 Source, IngestOccurrence, and InboxItem persistence foundation.
- Release-verification slice only; no AI, Drive integration, or broad UI changes.

## 0.8.2
- First asset resource view with image preview and linked documents.
- Explicit local Source-to-Asset links and contextual file upload/reuse.
- Database schema v5; original bytes remain unchanged.

