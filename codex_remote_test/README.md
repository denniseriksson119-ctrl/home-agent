# Codex Remote Test — Home Assistant OS

Separat experimentellt tillägg, version **0.1.4**, med **Codex CLI 0.164.0** för ARM64 och amd64.
Det testar om ChatGPT-appen på Android/iOS kan styra en Codex-session på denna enhet utan en dator som mellanled.

Tillägget är inte en färdig Home Agent-integration. Det har egen privat lagring,
syntetiskt testmaterial och inget monterat Home Agent-/Home Assistant-innehåll.
Det kräver ingen separat modell-API-nyckel; logga in med ditt ChatGPT-konto och dess normala Codex-gränser.

Se [installations- och provguiden](DOCS.md). Ägaren har med 0.1.3 bekräftat direkt
Android-anslutning, läsning/skrivning och fortsatt konversation efter omstart på sin Pi.
Ett lyckat containerbygge bevisar inte att direkt mobilparkoppling fungerar för andra konton eller enheter.
