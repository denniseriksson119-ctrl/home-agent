# ChatGPT Plus via en automatisk Drive-läskopia — första leverans

> **2026-10-26:** Drive-publicering är pausad som AI-huvudspår. Använd [Codex-läskopplingen](CODEX_HOME_AGENT_READ.md). Detta dokument beskriver den tidigare vägen; Drive-backup/arkiv planeras separat.

**Beslut:** Godkänt av ägaren 2026-10-18 ("då kör vi").
**Version:** Add-on 0.8.5. Ingen databasändring.
**Status:** Implementerat för kodgranskning. Riktig OAuth, Pi-publicering och läsning i telefonens ChatGPT måste verifieras efter installation.


## Förtydligande 2026-10-19 — befintlig delad mapp

Ägaren använder ett huvudkonto med befintligt lagringsabonnemang och en befintlig Home Agent-mapp som delas med det separata Home Agent-/ChatGPT-kontot. Endast mappen är delad, inte Google One-lagringen. Se [kontoprincipen](GOOGLE_DRIVE_ACCOUNTS_AND_STORAGE.md) och [backlog](../development/BACKLOG.md).

**Nuvarande implementation skapar en separat appmapp på det autentiserade kontot. Den är ännu inte anpassad till den befintliga delade roten.** Stegen nedan beskriver den levererade implementationen, inte en färdig lösning för denna installation. Nästa leverans ska först verifiera appauktorisering och publicering till rätt rot (BL-DRIVE-001); därefter återupptas Google-/Pi-/ChatGPT-provet. Enbart mapp-ID eller kontots delningsrätt löser inte appåtkomst med `drive.file`. Ägaröverföring och återställningsbar backup ingår inte i 0.8.6.


## Syfte och ansvar

Pi publicerar ett litet navigerbart läsunderlag automatiskt. Användaren ställer sin fråga i vanliga ChatGPT med befintlig Drive-anslutning. ChatGPT väljer relevanta publicerade uppgifter och öppnar källor utifrån frågan. Home Agent behöver därför inte gissa varje framtida fråga eller köra en språkmodell på Pi.

Detta är en härledd läskopia, inte operativ databas, backup, permanent arkivering eller ett nytt ingest-flöde. Pi förblir operativ source of truth. Publicering kräver ingen inkommande internetåtkomst, Site, egen MCP-plugin eller modell-API-nyckel. Den befintliga read-only-importen från Drive påverkas inte.

Första leveransen ersätter valet av plugin-transport i utkast PR #38. Denna PR utgår direkt från main och förutsätter inte #38. Båda använder 0.8.5 som alternativa leveranser; slå inte ihop båda utan en ny samordnad version/granskning.

## Vad publiceras?

- Ett stabilt `Home Agent — husindex.txt`: permanenta ID:n, namn och objekttyper för registrerade objekt samt uttryckligen lagrade relationer. Objektens privata rådata/snapshot ingår inte.
- Ett versionsbundet `Home Agent — NIBE S1255.txt`: valda lagrade fält för det befintliga Asset med legacy-mapping `eq_heat_pump_nibe_s1255`, dess explicita relationer och kopplade Event/ServiceHistory/Maintenance/FollowUp-poster där implementationen har ett uttryckligt stöd.
- Originalfiler som har en uttrycklig `source_link` till detta permanenta Asset-ID. Source-ID, ursprungligt namn och SHA-256 följer med i underlaget. Byte är oförändrade. En fil får vara högst 25 MiB; alla valda filer måste gå att läsa och matcha sin SHA-256 för att indexet ska uppdateras.

Alla filer skapas privat i en separat app-skapad mapp `Home Agent — ChatGPT läsunderlag`. Källkopior ligger i `Källor`; revisionsbundna läsunderlag ligger i egna mappar. Dessa är publicerade analyskopior, inte den permanenta arkivstruktur som regleras i `BACKUP_RESTORE_ARCHIVE.md`.

Husindex är navigering för hela den registrerade modellen. Fullständiga uppgifter/original för andra objekt publiceras inte i denna första leverans. Okopplade Inbox-filer antas aldrig höra till NIBE utifrån filnamn. Avsaknad av kopplad serviceinformation betyder inte att service aldrig utförts. En manual bevisar inte att ett tillbehör är installerat.

## Urval och begränsningar

SQLite öppnas med `mode=ro`, `query_only=ON`, schema 5 och en lästransaktion. Funktionen initialiserar/migrerar aldrig databasen. Gränser: 2 000 objekt, 10 000 relationer, 50 kopplade original och 512 KiB serialiserad kontext. Överskridande avbryter publiceringen utan tyst trunkering.

Objektets serialiserade YAML används bara internt. `house_context.FIELDS` väljer kända semantiska fält, exempelvis modell, tillverkare, serienummer, anteckningar, datum och underhållsuppgifter. Okända fältnamn exporteras inte. En del äldre domänfält kan därför saknas; Pi-provet måste kontrollera att meningsfulla NIBE-uppgifter faktiskt kommer med innan urvalet utökas.

Kopplade service-/underhållsposter identifieras genom explicita lagrade relationer eller fälten `asset_ref(s)`, `equipment_ref(s)`, `target_ref(s)` och `related_asset_refs`. Fritextmatchning används inte. Historiska ändringsloggar och fullständig servicefunktion byggs inte här.

Kontextrevision är SHA-256 för det valda läsunderlaget, inte en global databasversion. Tidsstämplar är UTC. Indexets tid avser när aktuell publicering läste databasen. Ett oförändrat revisionsbundet NIBE-underlag återanvänds med sin ursprungliga lästid; indexets aktuella revisionslänk anger att samma innehåll fortfarande valdes vid senaste kontrollen.

Källmaterial behandlas som evidens, inte instruktioner. ChatGPT ska skilja lagrade uppgifter, källpåståenden och egna slutsatser samt ange Source-ID/sida när det behövs. Saknade värden förblir okända. Inga livevärden från HA ingår. Underlaget kan inte verkställa ändringar eller svara på opublicerade databasfrågor.

## Publicering, fel och återstart

En separat bakgrundstråd försöker vid uppstart och därefter cirka var 15:e minut (15 minuter efter föregående försök). Lokal UI/commit väntar inte på Drive. Konfigurationen läses på nytt inför varje försök.

Ordning: konsekvent databasläsning → verifiera och publicera källkopior → revisionsbundet NIBE-underlag → uppdatera stabilt husindex sist. Drive-kopior kontrolleras mot uploadens MD5 för transportintegritet; SHA-256 förblir Home Agents källidentitet. Ingen flagga i source-/Inbox-tabellerna ändras av denna läspublicering.

Drive-ID reserveras och sparas lokalt **före** varje create. App-egenskaper identifierar installation/artefakt och varje skrivmål begränsas till egna skapade mappar/objekt. Om svaret på en lyckad create tappas kan nästa försök hitta samma fil. Inga filnamn används som identitet. Inga generella URL:er, externa mål, flytt-/delete-/share-operationer eller godtyckliga befintliga Drive-mappar stöds. Uppladdningsanrop följer inte redirectar.

Tidigare index kvarstår om ett tidigare steg misslyckas. Ett avbrott precis efter indexuppdatering kan lämna ny Drive-kopia men äldre lokal framgångsstatus; nästa försök återhämtar detta. Metadata/checksumma som ändrats på en tidigare oföränderlig kopia stoppar publiceringen för granskning. Flytta, redigera eller radera inte maskinens filer under provet.

Gamla revisioner och källkopior raderas inte automatiskt. De kan vara sökbara även efter att en relation tagits bort lokalt: börja **alltid med husindex** och följ dess aktuella länk. Frånkoppling/radering lokalt återkallar inte redan publicerat material. Retention, kvotvarningar och rensning är ett separat nästa steg före större drift. Oförändrade original kopieras inte om; förändrad kontext skapar ett nytt litet revisionsunderlag. En originalfil åt gången hålls i minnet. Filer över 5 MiB använder Googles resumable-protokoll med separat sessionsstart och en PUT; avbruten ofärdig överföring börjar om vid nästa publiceringsförsök, medan färdig fil återanvänds. Små filer använder multipart med extra buffertar. Mät Pi-minne vid provet.

## Engångsanslutning (på ägarens dator)

**Från 0.8.6:** Den rekommenderade vägen för telefonanvändning finns i [Google Drive från telefonen](GOOGLE_DRIVE_MOBILE_CONNECT.md). Klientuppgifter anges i Home Assistants konfiguration och Pi genomför enhetsinloggningen. Skriptvägen nedan finns kvar som äldre alternativ för separata installationer.

Detta steg är separat från ChatGPTs Drive-plugin och från Home Agents befintliga read-only-import. ChatGPTs anslutning ger inte automatiskt Pi en Google-token.

1. Använd ett **separat Google OAuth Desktop-klient-ID** för publicering. Aktivera Drive API och lägg till rätt testanvändare om OAuth-projektet är i testläge. Behörighet är `openid email https://www.googleapis.com/auth/drive.file`, inte full åtkomst till alla Drive-filer. Google kan begränsa refresh-token-livslängden för appar i testläge; återauktorisering kan behövas tills OAuth-konfigurationen är stabil.
2. Kör från repots `tools/` på datorn där webbläsaren finns:

   ```sh
   python3 drive_oauth_setup.py CLIENT_ID CLIENT_SECRET EXPECTED_EMAIL --chatgpt-export
   ```

   Välj det Google-konto som ChatGPT ska kunna läsa från. Alternativt måste ägaren senare dela just den nya mappen med kontot som är anslutet i ChatGPT; koden delar inga filer automatiskt. PKCE/state och kontroll av förväntad e-post används. Skriptet skapar en separat `chatgpt_drive_oauth.json` med 0600 och vägrar skriva över en befintlig fil. Den gamla importfilen används/ändras inte.
3. För över filen säkert till **Home Agent-add-onens egen** `/data/chatgpt_drive_oauth.json`, med behörighet 0600. `/data` i ett annat Terminal-/SSH-add-on är inte samma katalog. Använd ägarens befintliga administrativa överföringsväg; posta aldrig innehållet i Git eller chatt. Ingen tokenmatning i vanlig produkt-UI byggs i denna leverans.
4. Starta om Home Agent eller vänta på nästa publiceringsförsök. `enabled: true` och rätt `purpose` i filen aktiverar publicering. Ingen fil eller `enabled: false` stänger av framtida försök. Ta inte bort konfiguration/state mitt under en pågående överföring; stoppa add-onen först vid återkallelse.
5. Runtime-state sparas privat i `/data/chatgpt_drive_state.json`. Den innehåller installations-ID, reserverade externa ID:n och senaste status, inte OAuth-hemligheter. Behåll den över uppgraderingar/omstart. Radera inte state för att "försöka igen"; det kan skapa en separat ny publicering. Byte av Google-konto kräver en avsiktlig ny konfigurering.

UI **Mer → ChatGPT via Drive** visar aktivering, senaste framgång, säkert felmeddelande och en länk till index. Credentials visas aldrig. Befintlig UI kräver fortsatt lokal åtkomst; denna funktion öppnar ingen publik Pi-endpoint.

## Verifiering på Pi och telefon (ägaren)

1. Installera versionen efter GitHub-merge. Kontrollera att befintlig Inbox, rum och filöppning fungerar med exporten oansluten.
2. Öppna NIBE i **Utrustning** och koppla de fyra originalen uttryckligen om de ännu bara ligger i Inbox. Öppna originalen lokalt. Denna leverans gissar inga kopplingar.
3. Gör engångsanslutningen ovan. Kontrollera under **Mer** att en publicering lyckats. Öppna index och följ NIBE-länken. Verifiera att lagrade produktuppgifter, permanenta ID:n, rätt antal källor och fungerande original-länkar finns. Bekräfta att 11,8 MB-manualen går att öppna i Drive och att minnet på Pi räcker under uppladdning.
4. I telefonens ChatGPT, välj Google Drive och be: **"Läs Home Agent — husindex.txt. Ange tidstämpel och kontextrevision, följ den aktuella NIBE-länken och beskriv vad som är registrerat om min NIBE. Öppna relevanta original. Skilj lagrade uppgifter från vad manualerna säger och ange vad som är okänt."**
5. Kontrollera att svaret faktiskt läst filerna och återger rätt revision. Att Drive-pluginen är installerad bevisar inte läsning av dessa filer; sökindex kan vara fördröjt. Om filsökning inte hittar index, öppna det från Home Agent och använd dess länk i chatten. Verifiera även att ChatGPT kan läsa PDF-innehållet, inte bara metadata. Pluginen kan behöva ny behörighet/synk beroende på kontot.
6. Lägg till en syntetisk/tillfällig tydlig NIBE-anteckning via ett befintligt godkänt lokalt arbetssätt. Kontrollera efter nästa försök att revisionen ändras och ChatGPT läser aktuellt innehåll. Återställ anteckningen via samma arbetssätt.
7. Bryt tillfälligt Pi:s Drive-åtkomst. Lokal Home Agent ska fortsätta fungera. Tidigare publiceringsdatum ska stå kvar och fel visas; efter återställd åtkomst ska nästa försök lyckas utan nya kopior av oförändrade original. Kontrollera omstart på samma sätt.

**Inte verifierat av automatiska tester:** Google OAuth/scope i ägarens konto, Drive-serverns verkliga multipart-/resumable-beteende, konto-/filåtkomst i ChatGPT, hur Drive indexerar textfiler, faktisk PDF-läsning på telefon, eller verklig Pi-minnesförbrukning. Dessa är acceptanspunkter, inte påstådda resultat.

API-underlag: [Google Drive uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads), [reserverade fil-ID:n](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/generateIds), [drive.file-behörighet](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## Fortsättning efter lyckat läsprov

Utöka kontextpaket till fler objekt vid verkliga frågor, mät färskhet/kvot och specificera retention. Strukturerad retur av AI-förslag genom validering/review/commit är ett separat spår; ingen sådan import eller automatisk godkännandemotor ingår här.
