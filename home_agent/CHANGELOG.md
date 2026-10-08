# Changelog

## 0.7.0d1

- Room-note snapshot persistence and audit logging now commit atomically in one SQLite transaction.
- Keeps the 0.7c schema-v3 Source, IngestOccurrence, and InboxItem persistence foundation.
- Release-verification slice only; no AI, Drive integration, or broad UI changes.
