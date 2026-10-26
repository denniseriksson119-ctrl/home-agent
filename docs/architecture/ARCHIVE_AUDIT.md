# Skrivskyddad arkivkontroll

Leverans: Home Agent **0.8.10** och Codex Remote Test **0.1.7**.
Rapporten är en kontrollfunktion, inte en filflytt, import eller backup.

Från Home Agent **0.8.11** använder rapporten `archive-0.8.11` och skiljer
arkitekturens granskade namn från `technical_preserved` och äldre format.
[Separat namnförhandsgranskning](REVIEWED_ARCHIVE_NAMES.md) genomför godkända
namnbyten; själva arkivkontrollen är fortsatt skrivskyddad. Den befintliga
MCP-transporten i 0.1.7 är kompatibel utan nytt lässcope eller ny nyckel.

## Lokal användning

Öppna **Mer → Arkivkontroll**. Rapporten visar högst tio registrerade Sources
per sida och erbjuder **Nästa sida** och kontroll av ett enskilt Source-ID.
Ingen schemaändring, databasuppdatering, filflytt, namnändring, reparation,
Drive-åtgärd eller ny åtkomst till Home Assistant ingår.

Per källa visas:

- permanent Source-ID och registrerat originalnamn;
- relativ sökväg inom Home Agents Source-lager, aldrig en extern absolut sökväg;
- om referensen pekar på en vanlig, läsbar lokal fil;
- uppmätt storlek och SHA-256 jämförd med den registrerade checksumman;
- registrerad custody-status, som inte automatiskt ändras av en lyckad hashning;
- mapp-/namnkontroll enligt lokala 0.8.9-regeln;
- explicita Source-kopplingar med permanenta objekt-ID:n, typer och namn,
  inklusive besked om saknade mål, okopplade källor eller begränsad kopplingslista.

Nuvarande Source-schema sparar ingen separat referensstorlek. Rapporten visar
därför `expected_size_bytes: null` och `size_check: unknown_no_recorded_size`.
Den uppmätta storleken får inte beskrivas som en genomförd storleksjämförelse.
Matchande SHA-256 är en separat kontroll av originalets byte.

I rapportversion 0.8.10 betydde `current` att den tekniska lokala mapp/namnregeln
följdes. Från 0.8.11 kallas detta `technical_preserved`; det är inte ett färdigt
arkitekturnamn. `architectural` respektive `architectural_undated` anger de nya,
granskade arkivnamnen. `legacy_preserved` betyder
bevarad äldre lagring direkt under Source-lagret med Source-ID som filnamn;
det får inte beskrivas som den nya mappstrukturen. `deviation` markerar andra
placeringar/namn eller bristande kopplingar. Status måste läsas tillsammans med
de separata kontrollfälten; en tids-/storleksgräns är inte verifiering.
Den tekniska intagsregeln använde `Photos`, `Documents/Manuals`,
`Documents/Invoices` och `Documents/Other`, med fullt Source-ID + portabelt
originalnamn. Från 0.8.11 kontrolleras även datum, beskrivande arkivnamn och
år/månad-mappar från arkitekturen; namnbytet sker i det separata granskade flödet,
aldrig genom rapportläsningen. Inga semantiska kopplingar gissas.

## Begränsat Codex-läsverktyg och explicit delning

Lokal visning kräver inte Codex-delning. Under **Mer → Anslut Codex** finns
ett separat val **Dela arkivrapport med Codex**. Det beskriver att rapporten
omfattar även andra registrerade Sources än NIBE, deras relativa sökvägar,
filnamn, checksummor och kopplade objekts namn/ID:n. Valet är avstängt som standard.
Befintliga nycklar får inte automatiskt rapportåtkomst efter uppdatering.
Valet sparas privat och kan stängas av utan att NIBE-läsningen upphör.
En ny/roterad nyckel återställer rapportvalet; återkallad nyckel nekar allt.

MCP-verktyget `home_agent_archive_audit` anropar endast den fasta autentiserade
GET-endpointen `/v1/archive-audit`. Det tar högst ett av:

- `source_id`: kontrollera en registrerad källa;
- `after`: opak Source-ID-markör från föregående sidas `next_after`.

Utan argument hämtas första sidan. Följ `next_after` tills värdet är null innan
hela den registrerade samlingen sägs vara genomgången. Alla argument utöver
dessa nekas; inga filsystemssökvägar, URL:er eller ändringsoperationer accepteras.
Den befintliga nyckeltransporten är kompatibel. `home_agent_source` behåller sitt
tidigare, uttryckligen NIBE-kopplade filscope. Arkivrapporten ger ingen möjlighet
att hämta ytterligare original, databasfiler, privata inställningar eller nycklar.
Egna AGENTS-instruktioner bevaras; endast exakt genererade äldre mallar uppgraderas.

## Genomförande och gränser

Backend läser SQLite via `mode=ro`, `query_only` och en sammanhängande lästransaktion.
Filer läses först efter kontroll av deras registrerade referens. Varje sökvägskomponent
öppnas relativt kontrollerad katalog med `O_NOFOLLOW`; symboliska länkar och
icke-reguljära filer följs inte. Filer utanför lagret varken öppnas eller får sin
absoluta sökväg publicerad. Filens storlek/mtime/ctime/inod kontrolleras före/efter
hashning; en förändring under läsningen rapporteras som ej verifierad.

En rapport tillåter högst 2 000 registrerade Sources, 10 000 källkopplingar,
512 KiB JSON och tio Sources per sida. Enstaka filhashning begränsas till 256 MiB.
En sida har en arbetsbudget på åtta sekunder; ofärdig hashning får uttryckligt
`not_checked_time_limit`. Prova enskilt Source-ID i det fallet. En läsning/hashning
åt gången delas mellan lokala rapportvyn och Codex-tjänsten. Ingen stor fil läses
i sin helhet i minnet. Filsystemets långsamma I/O kan fortfarande påverka svarstiden;
detta är inte en generell lösning för tidigare blockerad webbläsaruppladdning.

Rapporten innehåller tidpunkt, käll-/kopplingsrevision och reglernas version.
Varje sida är en ny kontroll; identisk metadatarevision över sidorna garanterar
inte ett atomiskt filsystemssnapshot. Filkontrollerna görs efter metadataavläsning.
Den semantiska riktigheten i en registrerad rum-/utrustningskoppling bevisas inte
av att ID:t existerar. Oregistrerade filer, övergivna temporärfiler, import-ZIP och
backupkopior ingår inte. Kontrollen är inte ett återställningsprov eller backupbevis.

## Verifiering efter installation på Pi

1. Uppdatera båda tilläggen. Kontrollera att lokal Arkivkontroll visar befintliga
   original och att relativa sökvägar/mapp-/namnstatus går att läsa.
2. Kontrollera att rapportläsning via Codex nekas innan separat delning aktiveras.
3. Aktivera rapportdelningen och be Codex följa alla sidor, redovisa avvikelser,
   legacy-format och sådant som inte kunnat verifieras. Ändra inga filer.
4. Stäng av rapportdelningen och verifiera att rapportverktyget nekas medan
   NIBE-underlaget fortfarande kan läsas. Omstart ska bevara det valda läget.
5. Kontrollera att källornas ID:n, länkar, originalinnehåll och filnamn är oförändrade.

Automatiska tester använder syntetiska data. CI provar verklig HTML/CSRF-delning,
HTTP-/MCP-rapport och oförändrad databas i ARM64-/amd64-containrar. Faktisk
Pi-prestanda och ägarens verkliga arkiv måste verifieras efter installation.
