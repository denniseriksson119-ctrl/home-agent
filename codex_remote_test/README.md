# Codex Remote Test — Home Assistant OS

Separat experimentellt tillägg, version **0.1.1**, med **Codex CLI 0.164.0** för ARM64 och amd64.
Det testar om ChatGPT-appen på Android/iOS kan styra en Codex-session på denna enhet utan en dator som mellanled.

Tillägget är inte en färdig Home Agent-integration. Det har egen privat lagring,
syntetiskt testmaterial och inget monterat Home Agent-/Home Assistant-innehåll.
Det kräver ingen separat modell-API-nyckel; logga in med ditt ChatGPT-konto och dess normala Codex-gränser.

Se [installations- och provguiden](DOCS.md). Ett lyckat containerbygge bevisar inte
att OpenAI tillåter direkt mobilparkoppling för kontot. Provets slutliga acceptans sker på Pi och telefon.
