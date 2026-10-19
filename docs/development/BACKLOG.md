# Home Agent — aktiv backlog

**Uppdaterad:** 2026-10-19.
Detta är en avgränsad fortsättningsbacklog för Drive/ChatGPT-spåret, inte en fullständig inventering av projektets återstående funktioner.

Principer: [konton och lagring](../architecture/GOOGLE_DRIVE_ACCOUNTS_AND_STORAGE.md), [backup/återställning](../architecture/BACKUP_RESTORE_ARCHIVE.md).
Dokumenterat arbete innebär inte att funktionerna är byggda eller att en implementation har godkänts. Kodändringar följer [utvecklingsflödet](DEVELOPMENT_WORKFLOW.md).

## BL-DRIVE-001 — Använd den befintliga delade roten för ChatGPT-läsunderlag

**Prioritet:** Nästa leverans. **Status:** Öppen; auktoriseringsväg behöver verifieras.

Problem: Exporten i 0.8.6 skapar en separat appmapp på Home Agent-kontot. Ägaren har redan en Home Agent-mapp på huvudkontot, delad med extrakontot.

Omfattning och acceptans:
- Välj och verifiera en Google-stödd auktoriseringsväg till den befintliga roten. Kontots redigeringsrätt och enbart mapp-ID räcker inte som bevis för appåtkomst med `drive.file`.
- Behåll Home Agent-kontot som Pi-/ChatGPT-identitet och telefonen som daglig arbetsyta. Inga huvudkontocredentials på Pi.
- Spara vald rot privat, kontrollera rätt konto/mapp/skrivåtkomst och begränsa skrivningar till tjänstens avsedda objekt inom roten.
- Återanvänd verifierade befintliga originalreferenser där möjligt; dokumentera när en ny kopia faktiskt krävs. Ingen omorganisation eller radering av befintligt material.
- Hantera eventuell redan skapad export/state uttryckligen, utan tysta kontobyten, förlorade ID:n eller dubbla rötter vid återförsök.
- Verifiera nekad åtkomst, omstart/idempotens och att lokal drift fungerar utan Drive. Versionshöj installerad funktion i samma PR.

## BL-DRIVE-002 — Befintliga filer: ägaröverföring i batch

**Prioritet:** Före större arkiv-/backupdrift. **Status:** Öppen; begärd till backlog av ägaren.

Omfattning och acceptans:
- Inventera godkänd rot och samtliga undermappar. Visa vilka filer/mappar Home Agent-kontot äger, vilka huvudkontot redan äger och eventuella andra ägare. Förhandsgranska urvalet före körning.
- Begär överföring enbart från Home Agent-kontot till det konfigurerade huvudkontot. Överför inte annat innehåll på extrakontots Drive.
- Stöd acceptans från huvudkontot i batch: manuellt via `pendingowner:me` eller separat auktoriserad hjälpkörning. Att överföra en mapp får inte räknas som överföring av innehållet.
- Bevara fil-ID:n, byte, mappstruktur, befintliga länkar och provenance. Säkerställ fortsatt avsedd läs-/redigeringsåtkomst efter ägarbyte.
- Registrera väntande/accepterat/misslyckat per fil och kontrollera faktiskt ägarskap efteråt. Återförsök ska tåla delvis färdig batch och redan överförda filer.
- Ingen kopiering, flytt eller radering som genväg till ägarbyte. Verifiera kvot-/behörighetsfel och avbruten körning.

## BL-DRIVE-003 — Nya original och säkerhetskopior: löpande ägaröverföring

**Prioritet:** Del av planeringen för Drive-backup/arkiv. **Status:** Öppen; mekanism föreslagen, inte implementerad.

Föreslaget flöde: Home Agent-kontot laddar upp → verifierar artefakten → begär ägarbyte → separat mottagare under huvudkontot accepterar → Home Agent verifierar ny ägare.

Omfattning och acceptans:
- Prova huvudkontots schemalagda Google Apps Script som mottagare. Godkänn dess OAuth-behörigheter separat; ge inte Pi eller ChatGPT huvudkontots token.
- Mottagaren accepterar endast avsedd avsändare/mottagare och filer vars placering under godkänd rot verifierats. Kontrollera verklig föräldrastruktur, inte bara filnamn eller egen appmetadata.
- Verifiera Googles tvåstegsflöde mellan de faktiska privata kontona och att Home Agent behåller avsedd åtkomst efteråt.
- Beständigt skilj uppladdad, integritetsverifierad, väntande ägarbyte och verifierad huvudkontoägare. Redovisa väntetid, fel och lagringsbelastning innan överföringen är klar.
- Återuppta efter fel, avvisad acceptans, kvotbrist och omstart utan dubbeluppladdning eller förlust av den enda verifierade kopian.
- Definiera om små härledda läsunderlag också ska överföras; anta inte att alla artefaktklasser har samma livscykel.
- Komplett backup behöver dessutom konsekvent databasbackup, manifest/checksummor och icke-destruktivt återställningsprov. Ägarbyte ensamt gör inte en export till backup. Retention/radering är ett separat beslut.

## BL-DRIVE-004 — Verkligt läsprov: Pi → Drive → ChatGPT Plus

**Prioritet:** Direkt efter BL-DRIVE-001. **Status:** Väntar på mapp-/auktoriseringslösningen.

Acceptans:
- Koppla de fyra avsedda originalen uttryckligen till NIBE S1255 om de ännu bara ligger i Inbox.
- Slutför Google-konfiguration/inloggning från telefonen med Home Agent-kontot.
- Verifiera publicering i rätt delade rot, aktuellt index/revision, rätt NIBE-uppgifter och original, inklusive PDF på 11,8 MB. Mät Pi-minne.
- Be ChatGPT läsa aktuellt index, följa kontextlänken och hämta innehåll ur relevant PDF; metadata eller installerad plugin räcker inte.
- Prova en kontrollerad uppdatering, nätavbrott och omstart. Gammalt underlag ska märkas som gammalt och oförändrade källor återanvändas.
- Ingen separat betald modell-API-integration eller inkommande publik Pi-endpoint krävs för detta spår.

## Därefter — strukturerad retur av AI-förslag

Efter lyckat läsprov: specificera och implementera import av ChatGPT-förberedda förslag via befintlig Inbox, med validering, semantisk granskning, godkännande och lokal commit. Detta är separat från läspublicering och finns inte som färdig AI-import i 0.8.6.
