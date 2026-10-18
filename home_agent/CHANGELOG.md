# Changelog

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

