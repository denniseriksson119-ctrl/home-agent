# Utveckling i Codex-sessionen på Pi

**Godkänt av ägaren:** 2026-10-26. **Version:** Codex Remote Test 0.1.6.
Home Agent ligger kvar på 0.8.8. Ingen husdatamigration eller ny skrivåtkomst ingår.

## Använd från mobilen

1. Merga utvecklingsmiljöns PR och uppdatera **Codex Remote Test till 0.1.6**.
2. Öppna tillägget och vänta på **Ansluten till OpenAI**. Befintlig inloggning,
   läsnyckel, arbetsfiler och konversation behålls.
3. Skicka i den anslutna Codex-konversationen:

> Läs /data/workspace/DEVELOPMENT.md, kör verktygskontrollen och förbered Home Agents kodprojekt under /data/workspace/projects. Läs projektets arbetsinstruktioner och redovisa aktuell revision. Ändra inga husdata.

Codex hämtar projektet när katalogen saknas, eller inventerar befintligt lokalt
arbete innan någon uppdatering. Ingen automatisk clone, pull, reset eller
installation av Home Agent sker vid tilläggsstart. Om en gammal konversation
fortsätter använda äldre arbetsgränser: be den läsa de aktuella instruktionerna
igen eller skapa en ny konversation på samma Pi och `/data/workspace`.

Nästa produktuppgift planeras därefter tillsammans med ägaren: inventering av
det äldre materialet och en migrationsplan. Befintliga objekt och ID:n ska
bevaras. Original behöver säkras, dedupliceras och kopplas uttryckligen genom
Home Agents kontrollerade flöde. Lokal kodåtkomst innebär inte att Codex får
skriva direkt i produktionsdatabasen eller göra en massimport.

## Verktyg och persistens

Imagen innehåller Git, ripgrep, Python 3, PyYAML 6, python3-venv, Node 22/npm,
Codex CLI 0.164.0 och PDF-verktygen. Paketen installeras vid containerbygget,
så Codex behöver inte root/apt vid normal utveckling. Extra Python-paket kan
läggas i projektets egen `.venv`, med normala Codex-godkännanden.

Debian Bookworm använder Python 3.11. Projektets vanliga GitHub-CI använder
Python 3.12; hela testsviten körs dessutom i de faktiska ARM64-/amd64-imagerna.
Versionsskillnaden är avsiktlig och ska redovisas, inte döljas som identiska miljöer.

`python3 /app/development.py --check` provar de fasta verktygen, PyYAML och
skapande av en tillfällig venv med fungerande pip. Den gör inga nätanrop, läser
inga credentials och verifierar inte GitHub-/Drive-behörigheter.

- Kodprojekt: `/data/workspace/projects/home-agent`.
- Startguide: `/data/workspace/DEVELOPMENT.md`.
- Arbetsinstruktioner: `/data/workspace/AGENTS.md`, sedan projektets instruktioner.
- Privata originalkopior: `/data/workspace/home-agent-sources`, utanför kodrepot.

Exakt genererade äldre AGENTS-mallar uppgraderas för utveckling och husläsning.
Egna AGENTS-/DEVELOPMENT-filer bevaras; ägaren kan behöva anpassa egna instruktioner.
Ett symlinkat projektdir nekas. Befintlig kod, Git-historik, auth och läsnyckel
skrivs inte över. Projektfilerna ligger i tilläggets beständiga `/data`, som
fortsatt måste behandlas som privat i Home Assistant-backuper.

## Git, Drive, CI och installation

Ägaren har verifierat GitHub och Drive i Pi-sessionen. Uppdateringen återanvänder
anslutningarna och tillför ingen ny autentisering. Git CLI och anslutna GitHub-
verktyg kan ha olika behörigheter; utgå från den faktiskt fungerande vägen.
Testa vid behov PR-/CI-åtkomst för uppgiften utan att läsa tokenfiler eller
dumpa miljövariabler. Inventering av Drive-material görs enligt ägarens uppdrag;
inga Drive-ändringar ingår i verktygsförberedelsen.

Arbetsflödet är **uppdrag → kodgren → tester → PR → CI → ägarens merge → ägarens installation**.
Följ [projektets utvecklingsflöde](DEVELOPMENT_WORKFLOW.md) och
[överlämningsinstruktionerna](AI_DEVELOPER_HANDOFF.md). Containerbyggen sker i
GitHub Actions. Codex får varken host-Docker, Supervisor-/Home Assistant-API,
extra volymer eller behörighet att installera i det körande Home Agent-tillägget.

## Verifiering

CI bygger samma image på ARM64 och amd64, provar den faktiska verktygskontrollen
som UID 10001 och kör hela projektets tester med en offentlig källkodsarkivkopia.
En syntetisk lokal Git-gren/ändring/commit samt bevarande efter omstart verifieras.
Inga GitHub-skrivningar, Drive-operationer eller OpenAI-anrop ingår i containerprovet.
Tidigare inloggnings-/läsnyckel-/PDF-/bildprov körs fortsatt.

Ägaren verifierar efter uppdatering att Pi-konversationen kan läsa guiden,
förbereda kodprojektet, köra tester och använda sina faktiska GitHub-/Drive-
anslutningar. Lyckad CI är inte bevis för verklig PR-behörighet i den sessionen.
