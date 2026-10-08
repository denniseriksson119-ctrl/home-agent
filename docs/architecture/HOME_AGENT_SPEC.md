# Home Agent System Specification

**Spec version:** 2.0-draft
**Status:** Architecture reset / living design contract

## 1. Syfte
Home Agent är en digital husförvaltare för ett eller flera hem. Systemet samlar, strukturerar, förstår och förvaltar information om byggnaden, rum, tekniska system, komponenter, utrustning, dokument, bilder, underhåll, projekt, kostnader, garantier och historik.

Home Agent ska vara användbart även utan AI. AI är ett semantiskt lager ovanpå en deterministisk applikation och strukturerad data.

## 2. Aktuell målarkitektur
**Home Agent på Raspberry Pi → lokal databas → Home Agent backend → UI/API**

Kompletterande lager:
- **AI/LLM:** tolkning, matchning, resonemang och förslag.
- **Home Assistant:** live state, sensorer, enheter och automation.
- **Google Drive:** permanent dokumentarkiv samt backup/export/snapshots.
- **GitHub:** kod, specifikationer, designbeslut, PR:er och versionshistorik.

Rollerna ska hållas separata.

## 3. Source of truth
### Operativ data
Home Agents lokala databas är primär operativ source of truth för strukturerad Home Agent-data.

En ändring är operativt genomförd när backenden har validerat den, skrivit den atomärt till den lokala databasen och registrerat nödvändig historik/audit. Drive-synk får inte vara ett krav för en normal lokal commit.

### Originalmaterial
Originaldokument och originalbilder är källmaterial och bevaras oförändrade. Metadata, relationer och AI-tolkningar lagras separat.

### Arkiv och backup
Google Drive är inte den operativa databasen. Drive används för permanent dokumentarkiv och deterministiskt skapade backup/export/snapshot-artefakter. Misslyckad Drive-synk får inte göra en lyckad lokal commit ogiltig.

### Kod och specifikationer
GitHub är source of truth för Home Agent-kod och aktuella utvecklingsspecifikationer. Git-historik och PR:er är förändringshistorik. Stabila milstolpar kan taggas/versioneras.

## 4. Ansvarsfördelning
### Backend
Deterministisk kod ansvarar för validering, databastransaktioner, stabila ID:n/referenser, audit/historik, checksummor, snapshots/export, backup/synk, dubblettskydd och integrationsanrop.

### AI/LLM
AI tolkar text/bilder/dokument, identifierar produkter, extraherar källstödda fakta, matchar mot befintliga objekt, upptäcker konflikter/saknad information och föreslår relationer och strukturerade förändringar.

AI ska inte ensam vara den enda platsen där viktig information existerar.

### Home Assistant
Home Assistant ansvarar för live state, sensorer, enheter och automation. Home Agent ansvarar för kunskap, historik, dokument, underhåll och semantisk modell. HA Areas/Floors är inte Home Agents kanoniska fysiska modell; integration sker via stabila mappings. HA-state blir inte automatiskt permanent Home Agent-fakta.

## 5. Home Graph
Grundmodell:
**Person → Membership → Home → Floors / Rooms / Spaces / Systems / Components / Assets / Documents / Projects**

Därutöver finns bland annat Maintenance, Event, Expense, Warranty och Follow-up.

Beständiga objekt ska ha opaka, permanenta maskinskapade interna ID:n enligt `DATA_MODEL.md` (målformat UUIDv7). Namn, sluggar och legacy-/externa ID:n är attribut/mappings och får aldrig vara intern identitet.

Floor är våning. Room är normalt rum. Space är ett fysiskt utrymme som inte lämpligen är ett vanligt rum. Fysisk placering hålls separat från systemtillhörighet.

System representerar funktionella tekniska helheter och definieras centralt. Component är en generell central del av ett tekniskt system. Asset är en identifierbar produkt/ägd enhet med produkt- och livscykeldata. Information ska relateras snarare än dupliceras.

## 6. Relationer och topologi
Tekniska samband representeras med explicita referenser/relationer, exempelvis uses, contains, supplies, feeds, serves, located_in, implemented_by och connected_to.

Topologi får inte konstrueras enbart från vad som tekniskt brukar vara sannolikt. Saknade komponenter/relationer lämnas okända tills de kan stödjas.

## 7. Tillförlitlighet
Home Agent får aldrig hitta på saknade fakta. När relevant används Confirmed, Likely och Unknown. Viktiga uppgifter bör kunna spåras till källa. Konflikter synliggörs, inte löses tyst.

## 8. Ändringsmodell och godkännande
Godkännande styrs av **ursprung och risk**, inte av tekniska transportsteg.

- Vanliga explicita manuella låg-riskändringar kan sparas direkt efter deterministisk validering.
- AI-föreslagna beständiga förändringar presenteras semantiskt för granskning/justering när det krävs.
- Radering, större strukturändringar och andra riskfyllda operationer kan kräva confirmation.

Användaren ska inte godkänna YAML-generering, checksummor, filtransport, backup eller Drive-rotation.

## 9. Central intake
Ny ostrukturerad information ska kunna komma in centralt via text, foto/kamera och dokument.

**Input → lokal registrering av källmaterial → AI-analys → matchning mot Home Graph → semantiskt förslag → godkännande när det krävs → lokal commit → automatisk arkivering/backup**

Enkla kontextbundna åtgärder får gå direkt till rätt objekt utan AI när tolkning inte behövs.

## 9.1 Capture now, process later

Capture och processing är separata steg. Användaren ska kunna samla text, bilder och dokument snabbt utan krav på omedelbar AI-analys eller klassificering.

Home Agent har därför en egen **Inbox** som domän-/kökoncept för obehandlat källmaterial. Material i Inbox är inte i sig strukturerade fakta i Home Graph.

Två likvärdiga ingångar stöds:

**Direkt:** Input → analys → semantiskt förslag → eventuell review → lokal commit.

**Senare:** Input → lokal Inbox → senare batchanalys → semantiskt förslag → eventuell review → lokal commit.

Google Drive Inbox får användas som en extern ingest-kanal. Home Agent kan importera/synkronisera material därifrån till sin egen Inbox, men Drive-mappen är inte Home Agents operativa kö eller source of truth.

Normalfallet är **Analysera Inbox**: Home Agent arbetar själv igenom den persistenta kön, grupperar sannolikt relaterat material och skapar förslag utan att användaren först måste välja filer. Manuellt urval är ett sekundärt specialfall.

Inbox har beständigt bearbetningstillstånd. Backend, inte AI-minne eller chattsessionen, håller deterministiskt reda på progressionen. Ett Inbox-objekt kan exempelvis vara nytt, analyserat, kopplat till förslag, väntande på granskning, registrerat och arkiverat. Analysstatus och registreringsstatus ska hållas isär.

Bearbetning ska kunna pausas och återupptas utan att redan färdigbehandlat material behöver analyseras om. Vid återupptagning fortsätter Home Agent från sparat lokalt tillstånd.

Batchanalys ska kunna analysera flera Inbox-objekt tillsammans när det förbättrar kontexten, exempelvis bilder, faktura och dokument från samma arbete.

## 9.2 Processing pipeline
Normativ ingestion, deduplicering, parsing/extraktion, AI-analys, proposal, commit, arkivering, extern Inbox-cleanup, pause/resume och retry definieras i `docs/workflow/PROCESSING_AI_WORKFLOW.md`. Identitet, provenance och source-/dedupe-semantik definieras i `docs/architecture/DATA_MODEL.md`.

## 10. Dokument och bilder
Original bevaras. Metadata och relationer kan koppla dokument/bilder till Asset, System, Component, Project, Room, Space och Event. Drive-arkivering är en backend-funktion; användaren ska inte behöva känna till Drive-mappar.

## 11. Historik
Historik är händelsebaserad. Tidigare information ska inte försvinna när ny information registreras. Edit/delete ska ha definierad audit-semantik utan att audit behöver dominera normal UI.

## 12. Observation → Förslag → Beslut → Genomfört
Observation är vad systemet ser/vet. Förslag är rekommendation. Beslut är vad användaren bestämt. Genomfört är vad som faktiskt hänt. Ett AI-förslag är inte ett beslut och ett beslut är inte genomfört förrän åtgärden utförts.

## 13. Follow-up och underhåll
Follow-up och Maintenance är separata domänbegrepp. Follow-up är något att undersöka/besluta/följa upp. Maintenance är planerad eller återkommande service, kontroll, rengöring, byte eller reparation. Båda kan visas centralt i Att göra men behåller relationen till ursprungsobjektet.

## 14. Projekt, ekonomi och garantier
Projekt hålls separata från normalt underhåll och kan relatera till rum, assets, systems/components, dokument, beslut, budget och faktisk kostnad.

Ekonomidata kan omfatta inköp, kvitton, fakturor, servicekostnader, leverantörer, offerter och projektkostnader. Home Agent ersätter inte fullständig bokföring.

Garantier kan innehålla period, underlag, serviceärenden och claims och generera relevanta uppföljningar.

## 15. Proaktivitet
Home Agent kan identifiera relevanta kommande/försenade åtgärder, garantier, saknad information och projektstopp. Kvalitet prioriteras framför mängden notiser. Proaktivitet baseras på registrerad information och källstöd, inte generella antaganden.

## 16. Flera hem och användare
Systemet stödjer flera hem och ska på sikt stödja flera personer/behörigheter.

**Person → Membership → Home**

Behörighet verkställs i backend/databas, inte bara genom UI.

## 17. Persistens, schema och migration
Nuvarande implementation använder lokal SQLite. Domänmodellen ska inte göras beroende av SQLite; senare migrering till PostgreSQL eller annan lämplig databas ska vara möjlig.

Schemaförändringar versionshanteras och migreras deterministiskt.

YAML är inte operativ databas. YAML kan användas för bootstrap, import/export, diagnostik eller snapshots. Den importerade bootstrap-snapshotten är historiskt källunderlag för den lokala databasen, inte ett krav på framtida runtime-lagring.

## 18. Backup och återställning
Normativa regler för operativ backup, logisk export, permanent källarkiv, Drive Inbox-handoff/cleanup, retention och restore finns i `docs/architecture/BACKUP_RESTORE_ARCHIVE.md`.

Lokal commit är oberoende av Drive. Backup/export/arkiv är separata artefaktklasser och backupversion är inte samma sak som varje domänändring.

## 19. Specifikationer och Git-flöde
Aktuella utvecklingsspecifikationer finns i Git-repot:
- System Specification
- Data Model / Schema Specification
- AI & Workflow Specification
- UI Specification
- Design Decisions

**Diskussion/prototyp → beslut → spec/decision update → implementation → test mot spec → PR → merge**

Om kod och spec skiljer sig avgörs explicit vilken som ska ändras. Experimentell implementation blir inte automatiskt produktprincip.

## 20. Designprincip
> **Strukturerad lokal data som operativ grund. Deterministisk kod för mekanik. AI för semantik. Home Assistant för live state. Drive för arkiv/backup. Git för kod och designhistorik.**

Systemet ska optimeras för användarens arbetsflöde, inte för begränsningar i ChatGPT-, Drive- eller filverktyg.
