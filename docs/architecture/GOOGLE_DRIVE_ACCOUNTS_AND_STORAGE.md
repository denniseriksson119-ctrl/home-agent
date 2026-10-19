# Google Drive — konton, åtkomst och lagring

**Beslutad princip:** Ägarens förtydligande 2026-10-19. Se DD-043.
**Status:** Kontoupplägget finns redan. Anpassning av läspublicering och ägaröverföring är backlog, inte implementerade funktioner.

## Kontonas roller

- **Huvudkontot** äger den befintliga Home Agent-rotmappen och har det befintliga betalda lagringsabonnemanget. Målet är att även beständiga original och säkerhetskopior ska ägas av huvudkontot.
- **Home Agent-kontot** är ett separat privat Google-konto som används av Home Agent och ChatGPT. Huvudkontot delar endast den avsedda Home Agent-mappen med redigeringsrätt till detta konto.
- Endast mappen är delad; Google One-lagringen är inte delad mellan kontona. Mappdelning och abonnemangsdelning är olika saker.
- Pi autentiseras som Home Agent-kontot. Huvudkontots credentials ska inte lagras på Pi eller lämnas till ChatGPT.
- Ett Google Cloud-projekt/OAuth-klient är integrationskonfiguration, inte ett nytt Drive-konto, nytt lagringsabonnemang eller en ny operativ databas.

Dokumentera verkliga kontoadresser, mapp-ID:n, privata länkar och hemligheter i skyddad installationskonfiguration, aldrig i det publika Git-repot.

## Befintlig mapp och local-first

Återanvänd den befintliga delade rotmappen och dess material. Skapa inte en ny fristående Home Agent-rot på extrakontots Min enhet som standard. Tjänsteskapade undermappar kan användas inom den godkända roten utan att omorganisera befintliga Inbox, System eller Homes.

Pi och den lokala databasen förblir operativ source of truth. Drive har separata roller för originalarkiv, backup, export, extern Inbox och härledda läsunderlag för ChatGPT Plus. Ett läsunderlag är inte en återställningsbar backup.

Återanvänd befintliga verifierade originalreferenser när åtkomst, innehåll/checksumma och provenance kan styrkas. Filnamn eller liknande innehåll räcker inte för att anta att det är samma källa. Undvik onödiga nya originalkopior; saknad verifierad referens får inte leda till felaktig koppling.

## Mappbehörighet är inte appbehörighet

Home Agent-kontots redigeringsrätt till en delad mapp ger inte automatiskt OAuth-appen åtkomst till den. Scope `drive.file` avser appskapade eller uttryckligen appauktoriserade filer. Ett inställt mapp-ID ensamt är därför ingen bevisad lösning för befintlig rot.

Nästa implementation ska välja och verifiera en stödd auktoriseringsväg för just denna befintliga mapp, med fortsatt telefonanvändning och minsta praktiska behörighet. Googles enhetsflöde stöder begränsade Drive-scopes; full Drive-åtkomst får inte antas fungera genom att bara ändra scope-strängen.

Ägaren av Google Cloud-projektet behöver inte vara samma konto som autentiseras för Drive. Det förväntade Drive-kontot är Home Agent-kontot.

## Filägare avgör lagringsbelastning

För vanliga privata Google Drive-konton gäller:

- Befintliga filer som huvudkontot äger fortsätter att belasta dess lagring. Läsning skapar ingen ny kopia och ändrar inte ägare.
- En ny fil som Home Agent-kontot laddar upp ägs normalt av det kontot, även inne i huvudkontots delade mapp, och belastar extrakontots lagring.
- Ägarbyte av en mapp överför inte automatiskt ägarskapet för dess innehåll.
- Efter godkänt ägarbyte belastar filen den nya ägarens lagring. Fram till dess behöver uppladdarkontot ha utrymme.

Att skriva i rätt mapp löser därför inte ensamt lagringsfrågan.

## Ägaröverföring — mål och föreslagen mekanism

Målet är att huvudkontot ska kunna ta över befintliga filer i batch och nya original/säkerhetskopior löpande. Detta är ett separat utvecklingsarbete, inte en funktion i 0.8.6. Se [backlog BL-DRIVE-002 och BL-DRIVE-003](../development/BACKLOG.md).

Mellan två privata Google-konton kräver Google två behörighetssteg:

1. Nuvarande ägare begär överföring till huvudkontot (`pendingOwner`).
2. Huvudkontot accepterar överföringen (`transferOwnership`).

En batchkörning behöver behandla varje berörd fil; det finns ingen rekursiv ägarändring genom enbart rotmappen. Begränsa urvalet till godkänd rot och underträd samt förväntad nuvarande ägare. Bevara fil-ID:n, originalbyte och befintliga relationer/provenance. Filer som redan har rätt ägare lämnas orörda.

För löpande drift är ett schemalagt Google Apps Script, separat godkänt av huvudkontot, en föreslagen mottagare. Det kan kontrollera avsändare och faktisk mappplacering före acceptans. Huvudkontots behörighet stannar då hos Google. Apps Script är en designkandidat som ska provas, inte en redan verifierad installation. Skriptets OAuth-behörigheter kan vara bredare än mappen; kontroller i koden är inte samma sak som en mappbegränsad OAuth-behörighet.

## Backupstatus och fel

Spåra uppladdning, verifierad integritet, väntande ägarbyte och bekräftad ägare separat. En verifierad uppladdning får inte presenteras som slutförd ägaröverföring. Den avsedda lagringsplaceringen är klar först när huvudkontot är verifierad ägare.

Ägarbyte ersätter inte manifest/checksumma och icke-destruktivt återställningsprov enligt [backupkontraktet](BACKUP_RESTORE_ARCHIVE.md). Fel/kvotbrist ska vara synliga och återförsökbara; lokala commits fortsätter oberoende av Drive. Ingen automatisk radering eller retention aktiveras genom detta principbeslut.

## Nuläge och nästa leverans

0.8.6 är mergad och ägaren har installerat versionen samt öppnat anslutningssidan. Verklig Google-inloggning, publicering på Pi och ChatGPT-läsning av aktuell export är ännu inte verifierade.

Nuvarande exporter skapar en egen appmapp på det autentiserade kontot och stöder inte vald befintlig rot, ägaröverföring eller en komplett återställningsbar Drive-backup. Det avviker från kontoprincipen ovan. Före nästa installationssteg ska BL-DRIVE-001 lösa och verifiera mappåtkomsten; därefter provas kedjan Pi → Drive → ChatGPT med NIBE-underlaget.

## Google-underlag

- [Scope och filspecifik appåtkomst](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Enhetsflödets tillåtna scopes](https://developers.google.com/identity/protocols/oauth2/limited-input-device)
- [Ägaröverföring mellan privata konton via API](https://developers.google.com/workspace/drive/api/guides/transfer-file)
- [Ägarbyte, batchgodkännande och lagringsbelastning](https://support.google.com/drive/answer/2494892?hl=sv)
- [Schemalagda Apps Script-körningar](https://developers.google.com/apps-script/guides/triggers/installable)
