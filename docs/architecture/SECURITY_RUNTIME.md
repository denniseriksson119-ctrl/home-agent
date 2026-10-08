# Home Agent Security & Runtime Specification

**Version:** 0.1-draft
**Status:** Normative design contract

## Purpose
Define trust boundaries, secret handling, authorization, deployment and runtime behavior for Home Agent as a Home Assistant add-on without coupling the domain model to Home Assistant OS.

## Trust boundaries
Home Agent separates browser/UI, backend, local database/source storage, Home Assistant API, AI provider, Google Drive and the public GitHub repository. External responses and AI output are untrusted inputs and are validated before affecting local state.

## Private data and public repository
The public repository contains reusable code, schemas, tests, synthetic examples and specifications only. It must not contain real household addresses/names, private room/home data, production snapshots, source documents/photos, credentials, API keys, access tokens or passwords.

## Secrets
Secrets are runtime configuration, never domain data and never committed to Git. Provider credentials are supplied through supported runtime secret/configuration mechanisms.

Secrets are not written to normal logs/audit, included in portable exports, sent to the AI as contextual data or exposed through ordinary UI/API responses. Credential rotation never changes Home Graph identity.

## Authentication and authorization
Authorization is enforced by backend operations, not hidden UI controls. Future multi-user permissions scope Person/Membership/Home access using permanent IDs. Until full multi-user authorization exists, UI visibility is not treated as a security boundary.

Destructive administrative operations such as restore require confirmation and appropriate authorization.

## AI boundary
AI has no database, Drive or Home Assistant credentials. It receives bounded context through backend and returns untrusted structured proposals according to the AI contract. It cannot directly commit, remove data, archive, restore or invoke privileged integrations.

## Integration least privilege
Each integration gets only permissions required for its role. Drive access should be scoped to Home Agent-managed locations/functions where provider capabilities permit. Home Assistant uses a supported API/service boundary and never shares its internal database with Home Agent. Provider IDs are mappings, not identity.

## Home Assistant add-on runtime
Current deployment is a Home Assistant OS custom add-on. It runs as a separate service, persists operational data in the platform-provided add-on data mapping, exposes its own UI/API and later communicates with Home Assistant through supported APIs.

Home Assistant is host/orchestrator, not Home Agent's domain database.

## Persistent storage
Runtime code depends on the platform persistent-storage contract, not a physical disk path. In the current add-on the mapped data directory is `/data`.

Ephemeral container filesystem locations must never hold the only copy of operational data or unarchived source material.

## Database and migrations
SQLite is the current implementation. At startup backend verifies schema version before serving writes. Migrations are deterministic, ordered and auditable. Failed migration fails safely rather than running against a partially understood schema.

Risky migrations use a verified pre-migration backup according to the backup/restore contract.

SQLite row numbers, filenames and legacy textual IDs are never persistent domain identity.

## Service lifecycle
Startup conceptually follows:
**load config/secrets → verify persistent storage → open database → verify/migrate schema → recover interrupted jobs → start API/UI → resume eligible background work**

Shutdown stops new work and checkpoints/finishes active work at a safe boundary. Resumable jobs remain in durable state.

## Health and readiness
Machine-readable health/readiness is separate from normal UI and distinguishes process health, database usability, schema compatibility, writable persistent storage and critical startup/migration failure.

Drive, AI or Home Assistant may be degraded without disabling unrelated local operations.

## Failure isolation
Failure in AI, Drive or Home Assistant must not corrupt local state. Integration work is explicit, retryable and idempotent where applicable. External responses are validated.

## Logging and audit
Operational logs and durable domain audit are separate. Logs support diagnostics and rotate; source bodies and secrets are avoided by default. Audit records durable changes and important administrative events using permanent IDs.

Sensitive values are redacted from errors where feasible.

## Network/API exposure
Expose only required endpoints. State-changing endpoints validate input and authorization server-side.

Production deployment avoids unnecessary public internet exposure. Future remote access uses an authenticated supported boundary rather than direct exposure of the add-on service.

## Dependencies and updates
Runtime dependencies/base images are versioned in Git. Upgrades are deliberate and tested against migration/backup expectations. Application updates must not silently replace or destroy persistent data.

## Portability
Home Agent may later move away from Raspberry Pi/Home Assistant hosting. Domain contracts therefore stay independent of container paths; permanent IDs survive migration; integrations are adapters; SQLite details do not become public domain contracts; restore is the supported recovery/device-replacement path.

## Current implementation
The current 0.6.x add-on is an incremental prototype. Older implementation behavior is not automatically normative. New work converges on this contract through small testable slices rather than a full rewrite.
