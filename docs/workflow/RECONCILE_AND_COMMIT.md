# RECONCILE_AND_COMMIT v1.2

## Syfte

Sammanföra verifierade väntande ändringar, jämföra dem med aktuell Home Agent source of truth och efter uttryckligt godkännande skapa nästa kompletta datasnapshot.

Workflowet är den kontrollerade vägen från pending information till ny strukturerad source of truth.

Workflowet följer Home Agent-specifikationen och Workflow Core.

## Grundflöde

**Verifierad Current-snapshot → Pending → Reconciliation → Godkännande → Komplett kandidat → Readback → Verifiering → Slutligt godkännande → Rotation → Drive-slutverifiering → Ny source of truth**

Ingen del av detta flöde får kringgå kravet på komplett snapshot, verifiering och uttryckligt godkännande.

## 1. Fastställ basversion

Inventera den faktiska Google Drive-mappen:

`Home Agent/System/Data Snapshots/Current/`

Läs och verifiera den kompletta, verifierade och uttryckligen godkända snapshot som finns där. `Current/` ska normalt innehålla exakt en YAML-snapshot, och endast denna får användas som bas.

Historiska snapshots i `Home Agent/System/Data Snapshots/History/` får inte blandas in som aktuell data eller användas som ersättning om `Current/` inte kan läsas.

Om `Current/` eller dess snapshot inte kan verifieras i den aktuella körningen ska ingen ny kandidat skapas. Behandla detta som ett åtkomst-/synkroniseringsproblem, inte som att aktuell data saknas.

## 2. Samla pending

Identifiera relevanta väntande ändringspaket.

Ett pending-paket bör när möjligt innehålla:

- logiskt namn
- berörda objekt-ID:n
- föreslagna nya eller ändrade fakta
- confidence
- källor
- dokumentrelationer
- verifierad Drive-status när relevant
- konflikter
- öppna frågor
- commit-ready: yes/no

Pending kan komma från exempelvis:

- `EQUIPMENT_IDENTIFICATION`
- `INBOX_ANALYSIS`
- användarbekräftelser
- projektarbete
- teknisk inventering
- äldre verifierat men ännu oregistrerat arbete

## 3. Gamla chattar

Gamla chattar är inte source of truth och ska inte behandlas som databas.

Information från äldre arbete får användas som kandidatunderlag när den ursprungliga källan kan identifieras.

Återverifiera källan när detta krävs för säker commit.

Tidigare AI-sammanfattningar ersätter inte originalkällan.

## 4. Drive-status

När ett pending-paket bygger på att en fil finns på en viss Drive-plats ska detta verifieras genom aktuell Drive-inventering.

Tidigare känd sökväg, Project Sources, scratch eller chattkontext är inte bevis för aktuell Drive-placering.

När korrekt Drive-gren är relevant ska Workflow Cores regel för full Drive-parentverifiering tillämpas.

## 5. Reconciliation

Jämför varje pending-paket med basversionen.

Klassificera varje föreslagen ändring som exempelvis:

- redan registrerad
- ny information
- mer precis information
- korrigering
- historisk händelse
- ny dokumentrelation
- konflikt
- inte tillräckligt verifierad
- inte relevant för strukturerad data

Undvik dubbletter av befintliga assets, components, systems, documents och andra objekt.

## 6. Confidence

Bevara källans faktiska confidence.

En uppgift blir inte Confirmed enbart därför att den registreras i en ny snapshot.

Likely ska förbli Likely tills ytterligare stöd finns.

Unknown ska inte fyllas med antaganden.

## 7. Historik och aktuellt tillstånd

Skriv inte tyst över viktig historik.

När en förändring beskriver exempelvis:

- borttagen utrustning
- frånkopplad funktion
- ersatt komponent
- renovering
- tidigare installation
- förändrad användning

ska det bedömas om informationen hör hemma som historisk event-information snarare än enbart som nytt aktuellt värde.

Följ principen:

**Observation → Suggestion → Decision → Completed**

när den är relevant.

## 8. Tekniska relationer

Skapa endast relationer som faktiskt stöds av källorna.

Skapa inte relationer därför att de normalt förväntas i en installation.

Skilj mellan fysisk observation, dokumenterad design och teknisk inferens.

## 9. Reconciliation-rapport

Innan någon ny snapshot skapas ska användaren få en kompakt reconciliation-rapport.

Rapportera:

- basversion
- pending-paket som är commit-ready
- pending-paket som inte är commit-ready
- nya objekt
- ändrade eller preciserade objekt
- nya dokumentrelationer
- historiska events
- konflikter
- kvarvarande osäkerhet
- sådant som medvetet lämnas utanför commit

Skapa inte ny datasnapshot innan användaren uttryckligen godkänt reconciliation-resultatet.

## 10. Capability- och transportpreflight

Lokal filskrivning är en capability, inte ett krav.

Innan en versionsbärande kandidat skapas ska de capabilities som behövs för den planerade kandidatkedjan kontrolleras i den aktuella körningen.

Transportvägen ska fastställas innan kandidatbyggnaden börjar.

### A. Automatisk transport

Använd denna väg endast när den skapade kandidatfilen kan omvandlas eller överlämnas som en giltig filreferens till den aktuella Drive-skrivcapabilityn.

Planerad kedja är:

**Kandidatbyggnad → lokal readback → innehållsidentitet/hash → Drive-upload → Drive-readback → identitetsverifiering**

### B. Manuell filbrygga

Använd denna väg när automatisk transport från den lokalt skapade filen till Drive inte finns i den aktuella miljön.

Kandidaten ska då:

1. skapas och återläsas lokalt
2. verifieras tekniskt och semantiskt
3. få sin innehållsidentitet, när möjligt kryptografisk hash, fastställd
4. levereras som nedladdningsbar fil för oförändrad manuell uppladdning till den föreskrivna kandidatplatsen

Efter att användaren har laddat upp filen ska agenten:

1. inventera den föreskrivna kandidatplatsen
2. identifiera det faktiska Drive-objektet och dess Drive-ID
3. verifiera parent och relevant parentkedja enligt Workflow Core
4. återläsa objektet från Drive
5. verifiera att innehållet är identiskt med den tidigare verifierade kandidaten, när möjligt genom samma kryptografiska hash

Capability-preflight löser inte i sig en saknad lokal-fil-till-Drive-brygga. Den ska i stället säkerställa att rätt transportväg väljs innan kandidatbyggnad.

Om nödvändig kandidatbyggnad eller den valda transportvägen inte kan genomföras säkert:

- skapa inte en falsk kandidat
- ändra inte basversion
- öka inte versionsnummer för ett rent capability- eller transportförsök
- markera inte pending som committed
- behandla inte felet som saknad Home Agent-data

Pending ska förbli pending.

## 11. Skapa kandidat

Efter användarens uttryckliga godkännande av reconciliation:

1. läs den verifierade basversionen
2. applicera endast godkända pending-ändringar
3. skapa en komplett ny datasnapshot
4. öka dataversionen exakt ett steg
5. sätt timestamp vid faktisk skapandetid
6. reservera aldrig ett framtida timestamp eller filnamn i förväg

En patch eller diff ersätter inte den kompletta snapshotten.

Tidigare source-of-truth-snapshot får aldrig skrivas över.

Kandidatens versionsnummer, timestamp och filnamn fastställs vid faktisk skapandetid.

Ett lokalt exemplar och ett Drive-lagrat exemplar är samma kandidat endast om deras innehåll verifierats som identiskt. När capability finns ska kryptografisk hash användas som innehållsidentitet.

Upload-, flytt- eller readbackomtag av oförändrade bytes skapar inte en ny dataversion. Ett nytt Drive-ID innebär inte i sig en ny dataversion.

Om en kandidat redan har blivit en beständigt Drive-lagrad kandidat och dess semantiska innehåll därefter måste korrigeras ska kandidaten inte skrivas om i efterhand som om den vore oförändrad. Den korrigerade kandidaten ska följa Home Agent-specifikationens regel för nästa dataversion.

En tillfällig lokal artefakt som aldrig blev en Drive-kandidat och aldrig blev aktuell source of truth ska inte behandlas som en beständigt publicerad kandidat enbart därför att en lokal fil skapades. Ett misslyckat lokalt skapande-, verifierings- eller transportförsök får inte skriva om historiken eller i sig tvinga fram ytterligare en dataversion. Den faktiska kandidatstatusen ska avgöras av verifierad lagrings- och versionsstatus enligt specifikationen och detta workflow.

## 12. Teknisk verifiering

Efter att kandidatfilen skapats ska den återläsas och verifieras.

Kontrollera minst:

- att filen är läsbar
- att YAML är giltig
- samtliga obligatoriska rootfält enligt aktuell Home Agent-specifikation
- korrekt `source_of_truth` enligt etablerad snapshotmodell
- rätt schema/schema_version
- att kandidatens dataversion och timestamp överensstämmer med kandidatidentiteten och filnamnet
- fullständig förväntad struktur
- unika ID:n
- giltiga interna referenser
- ingen oväntad dataförlust
- att godkända ändringar finns med
- att icke godkända ändringar inte smugit sig in
- att endast den godkända semantiska ändringsomfattningen har applicerats
- inga oavsiktliga dubbletter

Verifiera den faktiska skapade filen, inte bara det innehåll agenten tror att den skrev.

## 13. Drive-kandidat

Spara den kompletta kandidatfilen i `Home Agent/System/Data Snapshots/`, men inte i `Current/` eller `History/` under kandidat- eller verifieringsfasen.

Kandidatplatsen och dess relevanta parentkedja ska verifieras enligt Workflow Core.

### Dubblettskydd före upload och uploadomtag

Före varje nytt uploadförsök, inklusive omtag efter ett oklart tidigare upload- eller readbackresultat, ska den kanoniska kandidatplatsen inventeras.

Om en fil med samma kandidatversion eller kandidatfilnamn redan finns ska agenten innan någon ny upload:

1. identifiera det befintliga objektets Drive-ID och parent
2. verifiera relevant parentkedja enligt Workflow Core
3. försöka återläsa objektet
4. verifiera innehållsidentiteten mot den lokalt verifierade kandidaten, när möjligt genom kryptografisk hash
5. återanvända det befintliga objektet om identiteten matchar
6. stoppa för beslut utan ytterligare upload om objektet inte kan verifieras eller om innehållet avviker

Agenten får inte skapa ytterligare en fil med samma kandidatidentitet enbart därför att ett föregående upload- eller readbackförsök gav ett oklart resultat.

Efter en faktisk skrivning till Drive:

1. verifiera att kandidatfilen faktiskt finns på kandidatplatsen
2. verifiera dess faktiska parent och relevanta parentkedja
3. återläs den från Drive
4. verifiera innehållet igen mot den lokalt verifierade kandidaten genom hash eller motsvarande innehållsidentitet

Kandidaten får inte ersätta eller flyttas in i `Current/` före uttryckligt slutgodkännande.

En lyckad lokal filskapning utan lyckad Drive-verifiering räcker inte för att göra snapshotten till source of truth.

Obligatorisk readback efter faktisk Drive-write ska alltid behållas.

## 14. Slutligt godkännande

En tekniskt och semantiskt verifierad kandidat är fortfarande endast kandidat.

Den blir aktuell source of truth först efter användarens uttryckliga slutliga godkännande och en därefter lyckad Drive-rotation med slutverifiering.

Före slutgodkännandet ska föregående snapshot ligga orörd i `Current/` och förbli source of truth.

Det införs inget ytterligare användargodkännande mellan lokal kandidatverifiering och Drive-baserad kandidatverifiering.

När arkivering av original ingår i det föregående källflödet gäller det separata arkiveringsgodkännande som definieras av det tillämpliga arkiveringsworkflowet. Det ersätter varken reconciliation-godkännandet i §9 eller slutgodkännandet i detta avsnitt.

## 15. Misslyckad kandidatverifiering

Om kandidaten eller Drive-kopian inte kan verifieras före slutgodkännande:

- lämna föregående snapshot orörd i `Current/`
- behåll föregående snapshot som source of truth
- markera inte kandidaten som aktuell
- markera inte pending som committed
- öka inte dataversionen igen enbart för att försöka verifiera samma logiska ändring

Verifieringskörningar i sig skapar ingen ny dataversion.

Skapa inte en extra version enbart därför att upload, flytt, readback eller verifiering behöver göras om.

Före ett nytt uploadförsök ska dubblettskyddet i §13 alltid genomföras.

Om kandidatens semantiska innehåll måste ändras gäller däremot kandidat- och versionsreglerna i §11 samt Home Agent-specifikationen.

## 16. Rotation efter slutgodkännande

Först efter användarens uttryckliga slutgodkännande:

1. flytta föregående snapshot från `Data Snapshots/Current/` till `Data Snapshots/History/`
2. verifiera den faktiska nya parentkedjan för den flyttade föregående snapshotten enligt Workflow Core
3. placera den godkända nya snapshotten i `Data Snapshots/Current/`
4. verifiera den faktiska nya parentkedjan för den nya snapshotten enligt Workflow Core
5. gör en faktisk Drive-inventering av `Current/`, `History/` och kandidatens tidigare plats
6. återläs den nya snapshotten från `Current/`
7. verifiera att:
   - `Current/` innehåller exakt den nya godkända YAML-snapshotten och ingen annan YAML-snapshot
   - föregående snapshot finns i `History/`
   - den nya snapshotten kan läsas komplett från `Current/`
   - relevanta parentkedjor motsvarar de föreskrivna Drive-grenarna
   - inga oavsiktliga dubbletter skapats

Rapportera versionsbytet som slutfört först när denna slutverifiering har lyckats.

Om rotationen eller slutverifieringen misslyckas efter slutgodkännandet:

- påstå inte att versionsbytet är slutfört
- rapportera exakt faktiskt Drive-tillstånd
- återställ inte filer på eget initiativ
- skapa inte någon ytterligare dataversion på eget initiativ

Efter lyckad rotation och slutverifiering:

- den nya snapshotten är aktuell source of truth
- godkända pending-paket markeras som committed
- ej inkluderade pending-paket förblir pending
- samma pending-ändring får inte appliceras igen i nästa reconciliation

Rapportera vilken version som nu är aktuell.

## 17. Aktuell backlog

Reconciliation kan exempelvis omfatta logiska paket såsom:

- `electrical_panel_A1`
- `bosch_main_dryer`
- `bosch_main_washer`
- `nibe_s1255`
- `nibe_flm30`
- analyserad NIBE-dokumentation
- analyserad Bosch-dokumentation
- verifierade arkiv- och källrelationer

Denna lista är endast exempel på möjliga pending-paket.

Förekomst i listan innebär inte i sig att paketet är verifierat eller commit-ready.

## Work-effektivitet

Målet är normalt:

**Körning 1:** läs basversion + samla/verifiera pending + reconciliation-rapport

**Användargodkännande**

**Körning 2:** capability- och transportpreflight enligt §10 + skapa komplett kandidat + lokal readback + teknisk och semantisk verifiering + genomför den i förväg valda transportvägen så långt den kan genomföras utan ny användarhandoff

Vid automatisk transport ska Drive-upload, Drive-readback och identitetsverifiering normalt ingå i samma körning.

Vid manuell filbrygga levereras den verifierade kandidatfilen till användaren. Efter användarens oförändrade uppladdning återupptas processen med kandidatplatsinventering, dubblettskydd, Drive-readback och identitetsverifiering.

Därefter krävs användarens slutliga godkännande.

Efter slutgodkännandet genomförs Drive-rotation, parentverifiering och slutverifiering i samma körning när möjligt.

Ett minimalt verifieringskvitto enligt Workflow Core får användas när det behövs för säker återupptagning. Kvittot ersätter aldrig ny verifiering av externa tillstånd som kan ha förändrats och ger aldrig i sig tillstånd till en write.

Gör inte ytterligare körningar utan konkret verifierings-, käll-, transport- eller åtkomstbehov.
