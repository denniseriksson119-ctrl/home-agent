# ChatGPT Plus → Home Agent: avgränsat NIBE-läsprov

## Status och avsikt

Implementerad lokal prototyp. Inte publicerad som Site/plugin och inte verifierad
mot ägarens Pi eller Plus-konto. Denna text är ingen bekräftelse på fungerande
fjärråtkomst. Ägaren har bekräftat att 0.8.4 är installerad och att de uppladdade
NIBE-originalen kan öppnas i Inbox; detta verifierar inte den nya anslutningen.

Målet är ett enda läsanrop från ChatGPT till aktuell data på Pi utan modell-API.
Pi förblir operativ sanningskälla. Ingen manuell snapshot-export behövs vid normal
användning av det färdiga läsprovet. Förslagsimport och Drive-automation ingår inte.

## Avgränsat kontrakt

`GET /api/chatgpt/nibe` returnerar bara befintligt Asset med legacy-mappningen
`eq_heat_pump_nibe_s1255`, dess permanenta ID och lagrade YAML-representation samt
metadata för uttryckligen kopplade Sources. Legacy-ID väljer prototypens objekt;
svaret bevarar dess permanenta identitet. Ingen namnbaserad matchning görs.

Svaret innehåller `retrieved_at`, `context_revision`, kontraktsversion och explicit
scope. Revisionen identifierar just detta urval, inte hela husdatabasen. Underlaget
är lagrad information, inte en ny kontroll av de fysiska förhållandena i huset.

Högst 50 källor och 64 KiB svar tillåts. Överskridande ger ett tydligt fel, aldrig
tyst trunkering. Originalbytes, interna Source-lagringssökvägar, token, hela
hus-snapshoten och okopplade Inbox-filer lämnas inte ut. Om filerna bara finns i
Inbox kommer de därför inte automatiskt med. Tom källista bevisar inte att manualer
saknas. `custody_status_recorded` är databasens lagrade status; filintegriteten
kontrolleras inte på nytt av detta metadataanrop.

Databasen öppnas med SQLite `mode=ro` och `query_only`. Anropet varken initierar
databasen, migrerar schema, skapar ID:n eller ändrar bearbetningsstatus. Schema v5
krävs. Okänd databasversion och driftfel ger 503, saknat objekt 404.

## Åtkomst

Läsprovet är avstängt tills `/data/chatgpt_read_token` finns med en slumpmässig
token, 32–128 tecken från `A-Z a-z 0-9 _ -`, och filbehörighet 0600. Saknad,
ogiltig, symboliskt länkad eller för öppet läsbar konfiguration ger 401.
Klienten skickar `Authorization: Bearer <token>`. Token ska aldrig läggas i Git,
chatt, modellunderlag eller webbläsarkod. Alla svar har `Cache-Control: no-store`.

Exempel på engångsskapande **inne i add-on-miljön**, efter installation av denna
version. Skriptet skriver ingen hemlighet till terminalen och ersätter inte en
befintlig token:

```python
import os, secrets
fd = os.open('/data/chatgpt_read_token', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write(secrets.token_urlsafe(32) + '\n')
```

Fjärråtkomst behöver en separat, verifierad anslutning. Befintlig port 8099 och
övriga äldre UI-endpoints ska inte göras offentliga för detta prov. En eventuell
HTTPS-brygga ska bara vidarebefordra den avgränsade läs-endpointen. Utformningen
beror på ägarens faktiska åtkomstlösning och ingår inte som påstådd befintlig funktion.

## ChatGPT-verktyget

`integrations/chatgpt-nibe/worker/index.js` exponerar ett stateless `POST /mcp` med
initialize, ping, notifications/initialized, tools/list och tools/call. Det enda
verktyget är `home_agent_read_nibe`, utan argument och deklarerat read-only.
Upptäckt lämnar inte ut husdata. Dataanrop kräver Sites-autentiserad användaridentitet.

Avsedd publicering är en **owner-private Site** med `capabilities: ["mcp"]`.
Sites ska sköta OAuth och användaridentiteten. Denna Worker får inte publiceras på
en allmän host där en klient kan förfalska Sites identitetsheader.

Serverkonfiguration som ska sättas säkert vid framtida publicering:

- `HOME_AGENT_ORIGIN`: verifierad HTTPS-origin för den begränsade bryggan.
- `HOME_AGENT_READ_TOKEN`: samma hemlighet som på Pi, som serverhemlighet.

Klienten kan inte ange alternativ URL, Asset eller databasfråga. Vidarekopplingar
följs inte. Anrop har 10 sekunders timeout och begränsad svarsstorlek. Fel,
inloggningssidor och svar med fel kontrakt ger tydligt verktygsfel utan cachad
ersättningsdata. Ingen OpenAI API-nyckel eller modell-SDK används.

Skillnad mellan verifieringsnivåer:

1. Lokala tester verifierar kod med syntetiska data och simulerad transport.
2. Sites-publicering verifierar hosting, inte anslutning till Pi.
3. Plugin-installation verifierar inte ett dataanrop.
4. Först ett lyckat verktygsanrop mot aktuell Pi-data verifierar hela läsprovet.

## Körda och återstående kontroller

Lokalt: Python-testsviten, Python-syntax, åtta Node-kontraktstester och
versionskontroll mot granskat grundläge. Alla data i testerna är syntetiska.
GitHub CI måste kontrolleras mot PR:ns faktiska commit.

Pi efter ägarens merge/installation:

1. Kontrollera att befintliga Hem, Inbox, rum och filöppning fungerar.
2. Utan token ska läs-endpointen svara 401.
3. Skapa token säkert och verifiera att fel token ger 401.
4. Rätt token ska ge 200 för befintlig NIBE eller 404 om objektet saknas.
5. Kontrollera permanenta ID:t och att endast explicita källkopplingar visas.
6. Upprepa läsningen: inga nya Sources, importhändelser eller ändringar ska skapas.
7. Efter privat plugin-publicering/installation, fråga ChatGPT vad som är lagrat
   om NIBE. Kontrollera hämtningstid, innehåll och scope mot Pi.
8. Bryt anslutningen: verktyget ska rapportera åtkomstfel och inte visa gammal data.

Publicering är i denna exekveringsmiljö blockerad av att Sites-paketets lokala
`scripts/site-workflow.mjs` och övriga publiceringshjälpare inte finns tillgängliga.
Ingen Site har registrerats och inget plugin-ID har skapats. Pi-adress och
fjärråtkomst måste också fastställas innan ett verkligt anslutningstest.
