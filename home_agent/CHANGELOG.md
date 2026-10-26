# Changelog

## 0.8.8

- Rätta formulärkontrollen för Codex-läsnyckeln när en mobilwebbläsare skickar Origin: null. En giltig CSRF-kod krävs alltid; uttryckliga främmande origin och cross-site-anrop nekas fortfarande.
- Använd Referrer-Policy: same-origin för sidan så att lokal formulärnavigering behåller normalt ursprungsunderlag.
- Containerprovet skapar nu nyckeln genom en riktig GET och formulär-POST innan MCP-/PDF-/bildprovet körs.

## 0.8.7

- Opt-in Codex-läsning från den anslutna mobilkonversationen: aktuellt objektindex, begränsade NIBE-uppgifter och uttryckligen kopplade original.
- Läsnyckel skapas och återkallas från Mer → Anslut Codex. Separat autentiserad lästjänst på internt tilläggsnät, utan ny host-port eller skrivfunktion.
- SHA-256-verifiera original och behåll databasen/källagret i Home Agent.
- Pausa Drive-publicering som AI-huvudspår utan att radera befintliga inställningar eller filer. Backup/återställning och förslagsimport återstår.

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

