# Home Agent Workflow Core v1.2

## Syfte

Workflow Core innehåller gemensamma operativa regler för Home Agents workflows.

Home Agent-specifikationen beskriver systemets datamodell, source-of-truth-principer och övergripande regler.

Workflow-filerna beskriver hur återkommande arbetsuppgifter ska utföras.

Workflow-regler får inte ändra eller kringgå Home Agent-specifikationen.

## Grundflöde

Arbeta normalt enligt:

**Källa → Analys → Förslag → Godkännande → Arkivering → Verifiering → Väntande registrering → Reconciliation → Commit**

Alla uppgifter behöver inte gå igenom samtliga steg, men source-of-truth får aldrig ändras utan det definierade commit-flödet.

## Source of truth

Endast den senaste:

- kompletta
- verifierade
- uttryckligen godkända

Home Agent-datasnapshotten är strukturerad source of truth.

Home Agent-data lagras i:

- `Home Agent/System/Data Snapshots/Current/`
- `Home Agent/System/Data Snapshots/History/`

`Current/` ska normalt innehålla exakt en komplett, verifierad och uttryckligen godkänd YAML-snapshot. Endast snapshotten i `Current/` är aktuell strukturerad source of truth.

`History/` innehåller tidigare godkända snapshots. Historiska snapshots får inte blandas med aktuell snapshot eller användas som ersättning om `Current/` inte kan läsas.

Om `Current/` eller dess snapshot tillfälligt inte kan läsas ska detta behandlas som ett åtkomst-/synkroniseringsproblem. Använd inte en historisk snapshot som aktuell bas.

Nya observationer ändrar inte source of truth automatiskt.

Information som ännu inte genomgått commit ska anges som:

**Väntande registrering i strukturerad data**

## Källor och evidens

Använd den faktiska källan för varje påstående.

Gissa inte information som inte kan läsas eller verifieras.

Relevanta källor kan bland annat vara:

- fysisk märkplåt eller etikett
- originaldokument
- fotografi
- verifierad Google Drive-fil
- officiell extern dokumentation
- aktuell verifierad datasnapshot
- uttrycklig information eller bekräftelse från användaren

Användarens uttryckliga bekräftelse är giltig källa för det användaren faktiskt bekräftar, exempelvis vilken fysisk produkt som fotograferats eller var den finns.

Utvidga inte användarens bekräftelse till andra tekniska fakta som inte uttryckligen bekräftats.

## Förvaltningsrelevant dokumentdata

Följ principen:

**Extrahera brett men registrera selektivt utifrån långsiktigt förvaltningsvärde.**

Dokument får analyseras brett för att förstå innehåll och sammanhang. Som väntande strukturerad registrering ska endast uppgifter med långsiktigt värde för förvaltningen tas vidare.

Kostnader får registreras för historik över hem, service, underhåll och projekt.

Betalnings- eller fakturaadministration ska däremot inte registreras enbart därför att uppgifterna finns i ett dokument. Detta omfattar exempelvis:

- betalningsstatus
- förfallodatum
- betalningsvillkor
- bankuppgifter
- kundnummer

## Confidence

Använd:

**Confirmed** — direkt och tillräckligt styrkt.

**Likely** — starkt stöd men inte fullt verifierat.

**Unknown** — otillräckligt stöd.

En uppgift får inte uppgraderas från Likely eller Unknown utan ytterligare stöd.

Registrering i en snapshot gör inte i sig en osäker uppgift mer säker.

## Källprioritet och källomfattning

Källors auktoritet beror på vilket påstående som ska styrkas.

För en fysisk installerad produkts egna identifierare är en läsbar märkplåt normalt starkare än en generell manual.

För dokumentets innehåll och modellomfattning är dokumentet självt primär källa.

För aktuell Drive-placering är aktuell Drive-inventering primär källa.

För en användarbekräftad fysisk koppling eller placering kan användarens uttryckliga bekräftelse vara primär källa.

Använd därför inte en enda generell källhierarki för alla typer av fakta.

## Google Drive

Google Drive är permanent dokumentarkiv.

`Home Agent/Inbox` är en tillfällig arbetsyta för nya original.

En fil får endast beskrivas som befintlig i en viss Drive-mapp om den faktiskt returneras vid aktuell inventering av just den mappen.

Project Sources, scratch, projektkontext eller tidigare kända filnamn är inte bevis för aktuell Drive-placering.

Om en känd källa tillfälligt inte kan läsas ska detta behandlas som ett åtkomstproblem, inte som bevis för att källan eller informationen saknas.

Fråga inte användaren på nytt efter redan registrerad information enbart på grund av ett tillfälligt källåtkomstfel.

När korrekt Drive-gren är relevant för arkivering, snapshotplacering eller annan strukturell verifiering ska målobjektets Drive-ID och den relevanta parentkedjan verifieras upp till den definierade Home Agent-roten. Mappnamn eller en textuell sökväg räcker inte som verifiering.

Verifieringen ska utgå från det faktiska målobjektet eller målmappen och följa parent-ID:n genom den relevanta strukturen. En destination är inte verifierad om endast den omedelbara mappen har rätt namn men dess relevanta parentkedja inte har verifierats.

Efter strukturella Drive-writes, exempelvis flytt av fil eller mapp, ska den faktiska parentkedjan verifieras på nytt.

Denna regel ägs av Workflow Core. Specialiserade workflows ska referera till den i stället för att definiera egna varianter av parentverifiering.

## Originalfiler

Originaldokument och originalbilder ska bevaras oförändrade.

Ändra normalt inte:

- filinnehåll
- filformat
- originalfilnamn

Skapa inte onödiga dubbletter.

Extraherad metadata, transkription och AI-tolkning ska hållas separerade från originalet.

## Inbox

Inventera alltid den faktiska Drive Inbox innan Inbox-filer behandlas.

Behandla endast filer som hör till aktuell uppgift.

Andra Inbox-filer ska lämnas orörda.

Inbox är en kö, inte permanent arkiv.

## Fysisk utrustning

Skapa inte ett nytt asset/component bara därför att ny eller mer exakt information hittas.

Försök först matcha mot befintliga objekt i aktuell source of truth.

Förbättrad stavning, exakt modellbeteckning eller mer precis identifiering ska normalt behandlas som precisering av befintligt objekt när källorna visar att det är samma fysiska produkt.

Exempel:

`FLM30` → `FLM 30`

är inte automatiskt ett modellbyte eller ett nytt asset.

## Dokument och modeller

Skilj mellan:

- exakt fysisk individ
- exakt variant
- grundmodell
- produktfamilj
- generell dokumentation

Dokumentation för en grundmodell får inte automatiskt behandlas som variantspecifik.

En variantspecifik supportsida kan däremot styrka att tillverkaren själv kopplar ett grundmodelldokument till den exakta varianten.

Bevara båda nivåerna separat.

## Dokumentavvikelser

Om tillförlitliga dokument anger olika värden ska respektive värde bevaras med sin källkontext.

Normalisera inte automatiskt bort skillnaden.

Dra inte slutsatsen att ett dokument är fel utan stöd.

## Installerat tillstånd

Manualer och ritningar kan beskriva möjliga, projekterade eller normala installationer.

Detta bevisar inte automatiskt aktuell fysisk konfiguration.

Skapa inga tekniska relationer enbart därför att de normalt förväntas finnas.

## Gamla ritningar

Originalritningar beskriver projekterat/originalt utförande om inte annat verifierats.

De bevisar inte automatiskt nuvarande byggtillstånd.

Använd vid behov:

- `source_confirmed`
- `projected_design`
- `current_state_not_verified`

## Arkivering

Flytta inte original från Inbox innan materialet är tillräckligt identifierat och klassificerat, om inte användaren uttryckligen godkänt ett automatiserat flöde.

Efter godkänd arkivering:

1. flytta originalet till rätt permanent Drive-plats
2. bevara filnamn, format och innehåll
3. verifiera destinationen
4. återläs originalet från destinationen
5. verifiera läsbarhet
6. verifiera att det flyttade originalet inte längre finns i Inbox

När korrekt Drive-gren är relevant ska destinationen och dess parentkedja verifieras enligt avsnittet `Google Drive`, inklusive ny verifiering efter den strukturella Drive-writen.

Misslyckad verifiering ska rapporteras.

## Väntande registrering

Analys, arkivering och strukturerad registrering är separata steg.

Nya fakta ska samlas som väntande registreringsunderlag tills de genomgått reconciliation och commit.

Pending information får inte vara beroende av att agenten långsiktigt minns gamla chattar.

När systemets capabilities tillåter bör pending-paket kunna bevaras separat och strukturerat.

## Lokal filskrivning

Lokal filskrivning är en capability, inte ett krav.

Kontrollera inte genom antagande att lokal skrivning fungerar bara därför att den fungerade i en tidigare körning.

Om lokal exekveringsmiljö eller filskrivning misslyckas:

- ändra inte source of truth
- öka inte versionsnummer
- skapa inte en låtsaskandidat
- behandla inte felet som saknad Home Agent-data
- behåll informationen som pending

Workflowet ska kunna fortsätta säkert utan lokal filskrivning.

## Minimalt verifieringskvitto

För flerfasiga operationer som kan behöva återupptas får ett minimalt verifieringskvitto användas.

Kvittot är operativt körningstillstånd. Det är aldrig Home Agent source of truth, pending data eller ett godkännande att utföra en write.

Kvittot får inte innehålla hela YAML-filen eller hela change-setet.

Minsta fält är:

- `workflow`
- `workflow_version`
- `phase`
- `base_snapshot_drive_id`
- `base_snapshot_hash`
- `reconciliation_approval_ref`
- `candidate_filename`
- `candidate_hash`
- `candidate_drive_id` när ett sådant faktiskt finns
- `last_verified_phase`
- `next_allowed_action`

En lokal temporär sökväg får aldrig användas som beständig kandidatidentitet eller som enda grund för återupptagning.

Vid återupptagning ska externa tillstånd som kan ha förändrats verifieras på nytt. Ett verifieringskvitto ersätter aldrig föreskriven Drive-inventering, parentverifiering eller readback efter write.

Kvittot får endast beskrivas som beständigt om en faktisk beständig lagringscapability och en faktisk lagringsplats finns och har verifierats. Denna workflowrevision skapar ingen ny Drive-mapp eller permanent kvittofil.

Om beständig lagring saknas ska workflowet uttryckligen begränsa återupptagningen till sådant som kan återetableras från aktuell `Current/`, en faktiskt identifierad Drive-kandidat och nya readbacks. Fullständig cross-session-resume får då inte utlovas.

Ett verifieringskvitto får inte automatiskt ge tillstånd till en write. Alla tillämpliga användargodkännanden och externa verifieringar gäller fortfarande.

## Work-effektivitet

Minimera antalet separata Work-/Drive-körningar utan att minska källsäkerhet eller verifieringsnivå.

Batcha filer när de hör till samma logiska uppgift.

Undvik onödiga omläsningar inom samma körning.

Efter faktisk filflytt eller snapshot-skrivning ska föreskriven readback-verifiering däremot alltid genomföras.

När ett verifieringskvitto används får fortfarande giltiga verifieringsresultat återanvändas endast när de underliggande externa objekten och deras identitet fortfarande kan verifieras. Tillstånd som kan ha förändrats ska läsas på nytt.

Använd inte Work/Drive för resonemang som kan göras utan extern åtkomst.

## Rapportering

Rapportera kompakt:

- vad som verifierades
- vad som är nytt
- vad som är osäkert
- vilka befintliga objekt informationen gäller
- vad som arkiverades
- vad som är pending
- eventuella konflikter eller åtkomstproblem

Upprepa inte workflowtexten i resultatrapporten.

## Regelprioritet och konflikter

Home Agent-specifikationen sätter systemets övergripande regler och datamodell.

Workflow Core sätter gemensamma operativa regler.

Specialiserade workflows preciserar hur en viss arbetsuppgift ska utföras inom dessa regler.

Användarens uttryckliga instruktion bestämmer den aktuella uppgiftens mål, omfattning och godkännanden.

En specialiserad instruktion får precisera ett generellt workflow men ska inte tyst kringgå source-of-truth-, källsäkerhets-, historik- eller verifieringsregler.

Om två tillämpliga regler faktiskt är oförenliga och konflikten påverkar dataintegritet eller källsäkerhet ska konflikten rapporteras istället för att agenten hittar på en lösning.
