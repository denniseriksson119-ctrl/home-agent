# Codex Remote Test — Home Assistant OS

Separat tillägg, version **0.1.6**, med **Codex CLI 0.164.0** för ARM64 och amd64.
Det testar om ChatGPT-appen på Android/iOS kan styra en Codex-session på denna enhet utan en dator som mellanled.

Tillägget har egen privat lagring och inget monterat Home Agent-/Home Assistant-innehåll.
Från 0.1.5 finns opt-in Home Agent-läsverktyg: objektindex, NIBE S1255-underlag och
uttryckligen kopplade original. Anslut med läsnyckeln från Home Agent 0.8.8.
Se [läskopplingen och telefonprovet](../docs/architecture/CODEX_HOME_AGENT_READ.md).
Import/godkännande av ändringsförslag och Drive-backup återstår.
Det kräver ingen separat modell-API-nyckel; logga in med ditt ChatGPT-konto och dess normala Codex-gränser.

Från 0.1.6 ingår utvecklingsverktyg och testberoenden. Be Codex läsa
`/data/workspace/DEVELOPMENT.md` för att förbereda projektet i den beständiga
kodmappen. [Utveckling från mobilen](../docs/development/CODEX_PI_DEVELOPMENT.md).
GitHub-/Drive-anslutningar återanvänds; faktisk PR-/CI-åtkomst kontrolleras i sessionen.

Se [installations- och provguiden](DOCS.md). Ägaren har med 0.1.3 bekräftat direkt
Android-anslutning, läsning/skrivning och fortsatt konversation efter omstart på sin Pi.
Ett lyckat containerbygge bevisar inte att direkt mobilparkoppling fungerar för andra konton eller enheter.
