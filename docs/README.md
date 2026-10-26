# Home Agent documentation

This directory contains the normative design and engineering documentation for Home Agent.

## Active document hierarchy
1. **System architecture** — `architecture/HOME_AGENT_SPEC.md`
2. **Data model / identity / provenance** — `architecture/DATA_MODEL.md`
3. **Security / runtime / deployment** — `architecture/SECURITY_RUNTIME.md`
4. **Backup / restore / archive** — `architecture/BACKUP_RESTORE_ARCHIVE.md`
5. **Processing workflow** — `workflow/PROCESSING_AI_WORKFLOW.md`
6. **AI / proposal contract** — `ai/AI_CONTRACT.md`
7. **UI specification** — `ui/HOME_AGENT_UI_SPEC.md`
8. **Design decisions** — `decisions/DECISIONS.md`
9. **Implementation** — code conforms to the applicable contracts above.

## Legacy workflow material
Older imported Drive-era workflow documents are historical/superseded unless an active specification explicitly references a still-valid rule. They do not override the local-first architecture, data model or processing workflow.

## Developer collaboration and release checks
- [Development workflow](development/DEVELOPMENT_WORKFLOW.md)
- [AI developer handoff](development/AI_DEVELOPER_HANDOFF.md)

## Development flow
**Idea → discussion/prototype → decision → spec/decision update → implementation → test against spec → PR → merge**

Experimental implementation does not automatically become product policy.

## Current implementation plan
- **0.7 — Permanent local data foundation** — `implementation/0.7_PLAN.md`
- **ChatGPT Plus via automatically published Drive read model (0.8.5; Pi/phone acceptance pending)** — [setup, scope and acceptance](architecture/CHATGPT_DRIVE_READ_MODEL.md)
- **Google Drive connection from a phone (0.8.6; real Google acceptance pending)** — [mobile setup and security boundary](architecture/GOOGLE_DRIVE_MOBILE_CONNECT.md)


## Active backlog and Drive account policy
- [Drive/ChatGPT backlog and next acceptance steps](development/BACKLOG.md)
- [Existing shared Drive folder, account boundary and storage ownership](architecture/GOOGLE_DRIVE_ACCOUNTS_AND_STORAGE.md) — owner clarification 2026-10-19; current exporter still needs adaptation.

## Codex on Home Assistant OS — isolated connection experiment
- [Codex Remote Test 0.1.4: phone setup, boundaries and acceptance](../codex_remote_test/DOCS.md) — owner confirmed direct Android connection, file read/write and resumed conversation after restart on Pi with 0.1.3; 0.1.4 clarifies returning-user guidance. Independent of Home Agent 0.8.6 and the Drive workstream.
