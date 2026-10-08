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

## Development flow
**Idea → discussion/prototype → decision → spec/decision update → implementation → test against spec → PR → merge**

Experimental implementation does not automatically become product policy.
