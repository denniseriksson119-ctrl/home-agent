# Changelog

## 0.1.5

- Opt-in Home Agent-läsverktyg via MCP: objektindex, aktuella NIBE-uppgifter och explicit kopplade original.
- Klistra in Home Agents läsnyckel på Ingress-sidan; nyckeln verifieras före sparande och visas aldrig i status eller verktygssvar.
- Hämta SHA-256-verifierade PDF-/bildkopior till arbetsmappen. Lägg till pdftotext/pdftoppm för faktisk PDF-läsning.
- Behåll befintlig ChatGPT-inloggning och användarfiler; uppgradera endast exakt genererade äldre arbetsinstruktioner.
- Ingen produktionsvolym, host-port, ändringsfunktion eller betald modell-API-nyckel läggs till. Verkligt hus-/bildprov på Pi återstår.

## 0.1.4

- Visa att en klar anslutning kan användas för att fortsätta den befintliga Codex-konversationen, även efter omstart.
- Förtydliga att parkod behövs vid första anslutningen, för en ny mobil eller när appen begär ny parkoppling.
- Dokumentera ägarens lyckade Pi-/Android-prov med 0.1.3: testmarkör, filskrivning/läsning och fortsatt konversation efter omstart.

## 0.1.3

- Begär parkod från samma Codex app-server som fjärranslutningen använder. Tidigare startades en förgrundsprocess medan parkodskommandot sökte en separat bakgrundsserver.
- Använd en privat Unix-socket inne i containern, utan ny nätverksport eller systemd-beroende.
- Visa faktisk OpenAI-anslutningsstatus och tillåt parkod först vid ansluten status.
- Visa vänteläge och säkra felmeddelanden direkt vid parkodsknappen. Ett parkodsfel tolkas inte som bevis för saknat kontostöd.
- Kontrollera det riktiga Unix/WebSocket-protokollet med CLI 0.164.0 i offline-containerprov på ARM64 och amd64. Verklig OpenAI-/Android-parkoppling återstår.

## 0.1.2

- Läs om sparad inloggning vid sidöppning och via knappen Kontrollera sparad inloggning.
- Skilj kontrollfel/okänd status från faktiskt utloggad; visa enbart säker diagnostik om filens existens och kontrolltid.
- Spärra ny enhetsinloggning när en ChatGPT-inloggning redan finns. Kontrollera också omedelbart före start, eftersom CLI:n rensar gammal auth när en ny inloggning startas.
- Tvinga samma filbaserade credentials-store och ChatGPT-metod för alla CLI-anrop utan att skriva över befintliga credentials.
- Tester för sparad inloggning, siduppdatering, sena svar och fel; CI återläser en syntetisk auth-cache med riktig CLI före/efter containeromstart utan nätåtkomst.

## 0.1.1

- Lås Debian/Node-basen i Dockerfile så att Supervisors BUILD_FROM-argument inte kan välja Alpine.
- Ta bort den äldre build.yaml och kontrollera Debian, apt och Node före paketinstallationen.
- CI bygger på ARM64 och amd64 med avsiktligt motstridigt Alpine-argument och verifierar rätt bas samt tidigare container-/omstartsprov.

## 0.1.0

- Isolerat ARM64/amd64-anslutningsprov med Codex CLI 0.164.0.
- Home Assistant Ingress-sida för ChatGPT-enhetsinloggning, fjärrprocess och manuell parkod.
- Privata, beständiga testfiler/sessioner; ingen montering av Home Agent-data.
- Syntetiska tester och containerprov i CI. Verklig Android-parkoppling återstår.
