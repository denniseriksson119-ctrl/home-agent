---
document: home_agent_specification
spec_version: "1.2"
created_at: "2026-09-13T18:11:55+02:00"
---

# Home Agent – specifikation

## 1. Syfte

Home Agent är en digital husförvaltare som hjälper till att samla, strukturera, förstå och förvalta information om ett eller flera hem.

Målet är att skapa en långsiktigt användbar modell där dokument, bilder, apparater, tekniska system, komponenter, installationer, underhåll, projekt, kostnader, garantier och historik kan kopplas till rätt verkliga objekt.

AI:n ska vara ett intelligent gränssnitt och analyslager. Den strukturerade datan ska vara source of truth.

## 2. Flera hem

Systemet ska stödja flera hem från början.

Exempel:
- hus
- lägenhet/bostadsrätt
- fritidshus
- framtida ytterligare bostäder

Varje hem ska ha ett stabilt unikt ID.

YAML-strukturens rot ska använda `homes:` så att ytterligare hem kan läggas till utan att datamodellen behöver göras om.

Övergripande modell:

`Homes → Floors / Rooms / Spaces / Systems / Components / Assets / Projects / Documents / Maintenance / Expenses`

## 3. Flera användare

Systemet ska på sikt stödja flera personer och behörigheter.

Grundmodell:

`Person → Membership → Home`

Exempel på roller:
- Owner
- Member
- Viewer
- Admin

Behörighet ska i den framtida backend-lösningen hanteras på databasnivå, inte bara genom att dölja information i gränssnittet.

## 4. Home Graph / objektmodell

Home Agent ska modellera hemmet som verkliga objekt och relationer, inte enbart som ett hierarkiskt dokumentträd.

Centrala objekttyper är bland annat:
- Home
- Floor
- Room
- Space
- System
- Component
- Asset
- Document
- Project
- Maintenance
- Event
- Expense

Objekt ska ha stabila unika ID:n. Ett ID ska normalt behållas när ett objekt byter namn, klassificering eller andra egenskaper.

### Floors, Rooms och Spaces

`Floor` representerar en våning.

`Room` representerar ett normalt rum.

`Space` representerar ett fysiskt utrymme som inte lämpligen är ett vanligt rum, exempelvis inspektionsutrymme, kryputrymme, installationsutrymme eller liknande.

Fysisk placering ska hållas separat från systemtillhörighet. Ett objekt kan därför vara placerat i ett visst rum eller space samtidigt som det ingår i ett tekniskt system som betjänar flera platser.

### Systems

`System` representerar en funktionell teknisk helhet, exempelvis:
- värmesystem
- elsystem
- ventilationssystem
- vattensystem
- avloppssystem
- nätverk
- poolsystem

System ska definieras centralt under hemmet. Våningar, rum och spaces ska referera till systemen som betjänar dem i stället för att innehålla duplicerade systemobjekt.

### Components

`Component` är en generell central objekttyp för fysiska eller logiska delar av tekniska system, exempelvis:
- fördelare
- ventil
- pump
- givare
- termostat
- värmeslinga
- radiator
- säkring
- relä
- nätverkskomponent

Komponenter ska inte dupliceras inne i olika system. System och platser ska i stället referera till centralt definierade komponenter.

En komponent ska kunna:
- användas av ett eller flera system när det är relevant
- ha en fysisk placering
- betjäna en eller flera platser
- ha relationer till andra komponenter
- ha systemspecifika egenskaper som attribut

Generella typer bör användas när det är praktiskt, medan mer specifika egenskaper kan lagras som attribut.

### Assets

`Asset` representerar en identifierbar produkt eller ägd enhet där produktinformation och livscykeldata är viktig.

Exempel:
- vitvara
- värmepump
- laddbox
- verktyg
- gräsklippare
- poolpump
- möbel
- annan utrustning

En asset kan innehålla:
- id
- namn
- kategori
- fabrikat
- modell
- serienummer
- inköpsdatum
- inköpspris
- leverantör
- garanti
- dokument
- bilder
- servicehistorik
- underhåll
- problem
- reparationer
- anteckningar

En asset kan samtidigt realisera eller vara kopplad till en komponent i ett system. Informationen ska inte dupliceras; relationer ska användas.

## 5. Systemtopologi och relationer

Tekniska samband ska kunna beskrivas som en graf av referenser mellan centrala objekt.

Exempel på relationer:
- `uses`
- `contains`
- `supplies`
- `feeds`
- `serves`
- `located_in`
- `implemented_by`
- `connected_to`

Relationer får endast registreras med den styrka som källmaterialet stödjer.

Exempel på vattenburen värmedistribution:

`Bergvärmepump → huvudfördelare → matningskrets → golvvärmefördelare → golvvärmeslinga → rum`

Modellen ska även kunna beskriva exempelvis:

`Bergvärmepump → huvudfördelare → radiatorkrets → radiator → rum`

Distributionen får vara hierarkisk. En huvudfördelare kan mata flera kretsar eller underfördelare, vilka i sin tur kan mata ytterligare kretsar och värmeavgivare.

Samma grundmodell ska kunna användas för värme, el, ventilation, vatten, nätverk, pool och framtida tekniska system.

Systemtopologi ska inte konstrueras genom antaganden. Saknade mellanliggande komponenter eller relationer ska lämnas okända tills de kan bekräftas.

## 6. Platsreferenser och betjäningsrelationer

Floors, rooms och spaces ska kunna referera till relevanta system och komponenter.

Ett rum kan exempelvis referera till:
- system som betjänar rummet
- värmeslinga
- radiator
- temperaturgivare
- termostat
- ventilationskomponent
- elkomponent
- nätverkskomponent

En förberedd installation ska inte automatiskt behandlas som en aktiv betjäningsrelation. Exempelvis innebär en förberedd nätverksdosa inte i sig att ett aktivt nätverkssystem betjänar rummet.

Systemdefinitionen ska finnas centralt. Platsobjekt ska endast bära de referenser och platsspecifika fakta som behövs.

## 7. Dokument och bilder

Originaldokument och originalbilder ska betraktas som källmaterial.

Exempel:
- manualer
- kvitton
- fakturor
- garantibevis
- offerter
- besiktningsprotokoll
- intyg
- produktblad
- foton
- installationsbilder
- serviceprotokoll

AI:n ska kunna extrahera metadata och föreslå relationer, exempelvis:

`Dokument → Asset`

`Dokument → System / Component`

`Dokument → Project`

`Bild → Room / Space / Asset / Event`

Originalet ska inte ersättas av AI:ns tolkning.

## 8. Informationssäkerhet och tillförlitlighet

Home Agent får aldrig hitta på saknade fakta.

Information ska om möjligt klassificeras som:
- Confirmed
- Likely
- Unknown

Källan ska sparas för viktiga uppgifter när det är möjligt.

Vid konflikt mellan uppgifter ska konflikten uppmärksammas i stället för att tyst lösas.

Viktig historik ska vara spårbar.

En tekniskt sannolik relation är inte automatiskt en bekräftad relation. Exempelvis ska en mellanliggande krets eller komponent inte skapas enbart för att den sannolikt finns.

## 9. Agentens självständighet

Home Agent ska ha balanserad självständighet.

Den får automatiskt:
- registrera entydig information
- klassificera uppenbara dokument
- föreslå relationer
- skapa tydliga underhållsförslag
- identifiera uppenbara deadlines
- upptäcka saknad information

Den ska fråga innan:
- osäkra objekt kopplas
- motstridiga fakta avgörs
- information raderas
- större eller strukturella ändringar görs
- kostnader uppstår
- externa eller irreversibla åtgärder genomförs

## 10. Huvudlägen

Home Agent ska kunna arbeta i flera lägen:

### Fråga
Besvara frågor om hemmet.

### Registrera
Lägga till eller uppdatera information.

### Tolka
Analysera dokument, bilder och annan information.

### Underhåll
Identifiera och planera underhåll.

### Projekt
Hantera renoveringar och andra projekt.

### Ekonomi
Sammanställa kostnader och ekonomisk historik.

### Historik
Visa vad som hänt och när.

### Övervaka
Proaktivt identifiera sådant som bör uppmärksammas.

## 11. Proaktivitet

Home Agent ska aktivt kunna upptäcka:
- kommande underhåll
- försenat underhåll
- utgående garantier
- saknade dokument
- saknade serienummer eller modellnummer
- projekt som står still
- deadlines
- säsongsuppgifter
- återkommande kostnader
- återkommande service
- möjliga problem

Prioritering:

🔴 Gör nu  
🟡 Planera  
🟢 Senare

Varje rekommendation ska helst ha en kort motivering.

Home Agent ska prioritera kvalitet framför mängden notiser.

## 12. Underhåll

Underhåll ska kunna vara:
- återkommande
- engångsuppgift
- säsongsuppgift
- service
- rengöring
- inspektion
- filterbyte
- kontroll
- reparation

En underhållspost bör kunna innehålla:
- id
- namn
- relaterat hem
- relaterat objekt/system/component/asset
- beskrivning
- intervall
- förfallodatum
- senaste genomförande
- nästa förfallodatum
- prioritet
- status
- källa
- kostnad
- utförare

Underhåll ska kunna skapa historik när det genomförs.

Rekommenderat underhåll och faktiskt genomfört underhåll ska hållas isär.

## 13. Historik

Historik ska vara händelsebaserad.

Exempel:

`2026-09-12 – Filter byttes`

`2026-10-03 – Service genomfördes`

`2026-10-10 – Ny offert mottagen`

Tidigare information ska inte försvinna bara för att en ny uppgift registreras.

Korrigeringar och viktiga förändringar ska kunna spåras.

## 14. Projekt och renoveringar

Projekt ska hållas separata från vanligt underhåll.

Exempel:
- renovera badrum
- installera laddbox
- byta fönster
- bygga altan
- måla om
- installera solceller

Projektstatus:
- Idea
- Planning
- Active
- Paused
- Done
- Cancelled

Ett projekt ska kunna innehålla:
- mål
- beskrivning
- nästa steg
- deadline
- budget
- offerter
- fakturor
- faktisk kostnad
- dokument
- bilder
- beslut
- historik
- relaterade assets
- relaterade systems/components
- relaterade rooms/spaces

Home Agent ska kunna upptäcka projekt som verkar ha stannat och föreslå ett konkret nästa steg.

## 15. Ekonomi

Home Agent ska kunna hantera hushållsrelaterad kostnadsinformation.

Exempel:
- inköp
- kvitton
- fakturor
- servicekostnader
- leverantörer
- offerter
- projektbudget
- faktisk projektkostnad
- kostnader per asset/system/component
- garantirelaterade kostnader
- historiska kostnader

Home Agent är inte avsedd att ersätta ett fullständigt bokföringssystem.

## 16. Garantier

Garantier ska kunna innehålla:
- startdatum
- slutdatum
- garantins längd
- förlängd garanti
- garantidokument
- inköpsunderlag
- serviceärenden
- reklamationer/claims
- kostnader

Home Agent ska kunna varna när en garanti närmar sig sitt slut.

## 17. Dokumentrelationer

Dokument ska kunna kopplas till flera relevanta objekt när det behövs.

Exempel:

`Kvitto → Asset`

`Manual → Asset`

`Produktblad → Component`

`Offert → Project`

`Faktura → Project + Supplier`

`Serviceprotokoll → Asset/Component + Maintenance Event`

Relationerna ska kunna kompletteras över tid.

## 18. Observation → Förslag → Beslut → Genomfört

Home Agent ska skilja mellan:

### Observation
Vad systemet faktiskt ser eller vet.

### Förslag
Vad systemet rekommenderar.

### Beslut
Vad användaren har bestämt.

### Genomfört
Vad som faktiskt har hänt.

Ett AI-förslag är inte ett beslut. Ett beslut är inte genomfört förrän åtgärden faktiskt har utförts.

## 19. Säsongsförvaltning

Home Agent ska kunna identifiera relevanta säsongsuppgifter baserat på vad som faktiskt finns i hemmet.

Exempel:
- vår
- sommar
- höst
- vinter

Säsongsuppgifter ska inte skapas enbart för att de är generellt vanliga. De ska i första hand baseras på registrerade system, utrustning och behov.

## 20. Versionshantering

Home Agent använder tre separata och oberoende versionsserier:

- `spec_version` = version av Home Agent-specifikationen
- `schema_version` = version av datamodellen/schemaformatet
- `home_vNNN_YYYY-MM-DD_HHMM.yaml` = version av faktisk Home Agent-data

En förändring i en versionsserie innebär inte automatiskt att någon av de andra ska ändras.

### 20.1 Specifikationsversion

`spec_version` beskriver versionen av Home Agent-specifikationen.

Specifikationsfiler ska vara fullständiga, unika och oföränderliga snapshots med filnamn enligt:

`HOME_AGENT_SPEC_vX.Y_YYYY-MM-DD_HHMM.md`

Specifikationsfilens metadata ska följa:

```yaml
---
document: home_agent_specification
spec_version: "X.Y"
created_at: "<ISO 8601 timestamp>"
---
```

Filnamnets versionsnummer, datum och tid ska överensstämma med dokumentets metadata.

Aktuell specifikation är den senast verifierade och uttryckligen godkända specifikationsversionen. En fil blir inte automatiskt aktuell för att den:

- har högst versionsnummer
- har senaste tidsstämpel
- laddades upp senast
- själv påstår att den är aktiv

`status: active` ska inte användas för att avgöra vilken specifikation som är aktuell. Aktuell status avgörs av verifieringsprocessen.

Om flera specifikationsfiler finns får information från dem inte blandas. Om det inte säkert går att avgöra vilken som senast verifierats och uttryckligen godkänts ska användaren tillfrågas.

En ny `spec_version` innebär inte automatiskt:

- en ny `schema_version`
- en ny YAML-dataversion
- någon förändring av faktisk Home Agent-data

### 20.2 Livscykel för en ny specifikationsversion

1. Läs den senaste verifierade och uttryckligen godkända specifikationen.
2. Föreslå ändringen och nästa `spec_version`.
3. Inhämta godkännande när det krävs.
4. Skapa en ny fullständig och unikt namngiven specifikationskandidat.
5. Behåll all specifikationstext som inte omfattas av den godkända förändringen.
6. Ladda upp kandidatfilen till projektet.
7. Läs om kandidatfilen direkt från projektets källor.
8. Verifiera metadata, filnamn, innehåll, konsekvens och informationsbevarande.
9. Inhämta eller registrera ett uttryckligt godkännande.
10. Först därefter blir kandidatversionen aktuell specifikation.
11. Föregående verifierade version blir då historisk.

Om verifieringen misslyckas ska föregående verifierade specifikationsversion fortsätta vara aktuell.

En underkänd eller historisk specifikationsfil ska inte skrivas över. En korrigering ska skapas som en ny kandidatversion.

### 20.3 Schema-version

`schema_version` beskriver versionen av den strukturerade datamodellen och dess schemaformat.

Aktuell schema-version är:

`schema_version: "1.0"`

Schema-versionen ändras endast när förändringar i datamodellens format motiverar det enligt schema-versioneringsprincipen.

En ny specifikationsversion eller datasnapshot innebär inte automatiskt en ny `schema_version`.

### 20.4 Dataversion

Dataversionen beskriver en konkret fullständig snapshot av Home Agent-datan.

Datafiler ska namnges:

`home_vNNN_YYYY-MM-DD_HHMM.yaml`

Här betyder:

- `vNNN` = dataversion
- `YYYY-MM-DD` = datum då kandidatversionen skapades
- `HHMM` = tid då kandidatversionen skapades

Aktuell verifierad dataversion är:

`home_v004_2026-09-13_0855.yaml`

Versionsnumret ökas med exakt 1 för varje ny kandidatversion.

Datum, tid, versionsnummer och filnamn ska bestämmas automatiskt när det är möjligt.

En ny specifikationsversion eller schema-version innebär inte automatiskt att en ny dataversion ska skapas.

### 20.5 Livscykel för en ny dataversion

1. Läs senaste verifierade source of truth.
2. Föreslå förändringen.
3. Inhämta godkännande när det krävs.
4. Skapa en ny fullständig YAML-snapshot.
5. Behåll all data som inte omfattas av den godkända förändringen.
6. Ladda upp kandidatversionen till projektet.
7. Läs om kandidatfilen från projektets källor.
8. Verifiera struktur, referenser, semantik och informationsbevarande.
9. Först efter godkänd verifiering blir kandidatversionen aktuell source of truth.
10. Föregående version blir då en historisk snapshot.

Om verifieringen misslyckas ska föregående verifierade version fortsätta vara source of truth.

En underkänd kandidat ska inte skrivas om i efterhand. En korrigerad version ska skapas som nästa dataversion.

Det ska normalt bara finnas en aktuell Home Agent-YAML-fil bland projektets aktiva källor. Historiska snapshots ska inte blandas med aktuell data.

## 21. Verifiering och migrationssäkerhet

Vid schema- eller datamigrering ska Home Agent kontrollera bland annat:
- giltig YAML-struktur
- korrekt rotstruktur
- korrekt data- och schemaversion
- bevarade stabila ID:n
- bevarade faktiska uppgifter
- giltiga referenser
- inga oavsiktliga dubbletter
- inga nya föräldralösa objekt
- inga oavsiktliga semantiska förändringar
- inga nya obekräftade fakta eller tekniska relationer
- ingen oavsiktlig informationsförlust

Teknisk validering är inte tillräcklig. Även semantisk kvalitetskontroll ska göras.

Kända, icke-blockerande normaliseringsbehov får finnas kvar om informationen är bevarad och de inte innebär felaktiga fakta.

## 22. Framtida databas

Datamodellen ska från början utformas så att den senare kan migreras till PostgreSQL eller motsvarande relationsdatabas.

Exempel på framtida huvudtabeller:
- homes
- people
- memberships
- floors
- rooms
- spaces
- systems
- components
- system_relations
- assets
- documents
- document_links
- projects
- maintenance
- events
- expenses
- suppliers
- warranties
- reminders

Relationer mellan system, komponenter, assets och platser bör i en framtida relationsdatabas kunna representeras med referenser/relationstabeller i stället för duplicerad information.

Dokument och bilder ska i framtiden lagras separat från metadata.

## 23. Grundprincip för data

Strukturerad data är source of truth.

Originaldokument och bilder är källmaterial.

AI:n ska:
- läsa strukturerad data
- tolka källmaterial
- föreslå förändringar
- svara på frågor
- hjälpa användaren fatta beslut
- identifiera konflikter och saknad information

AI:n ska inte ensam vara den enda platsen där viktig information existerar.

## 24. Framtida integrationer

Arkitekturen ska kunna utökas med:
- Raspberry Pi
- Home Assistant
- lokal SSD-lagring
- molnbackup
- PostgreSQL/Supabase
- OpenAI API
- notifieringar
- kalender
- externa API:er
- andra hemautomationssystem

Dessa integrationer är inte krav för v1.

## 25. Designprincip

Home Agent ska byggas stegvis.

Prioritet:
1. Stabil datamodell
2. Korrekt information
3. Dokument och källor
4. Underhåll och historik
5. Projekt och ekonomi
6. Proaktivitet
7. Fleranvändarstöd
8. Externa integrationer och automation

Modellen ska vara generell nog att representera verkliga samband, men inte göras mer komplicerad än de faktiska behoven kräver.

Grundprincipen är:

> Struktur först. AI ovanpå strukturen. Automation sist.
