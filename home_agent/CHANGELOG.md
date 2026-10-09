# Changelog

## 0.7.0d1

- Room-note snapshot persistence and audit logging now commit atomically in one SQLite transaction.
- Keeps the 0.7c schema-v3 Source, IngestOccurrence, and InboxItem persistence foundation.
- Release-verification slice only; no AI, Drive integration, or broad UI changes.

## 0.8.2
- First asset resource view with image preview and linked documents.
- Explicit local Source-to-Asset links and contextual file upload/reuse.
- Database schema v5; original bytes remain unchanged.
