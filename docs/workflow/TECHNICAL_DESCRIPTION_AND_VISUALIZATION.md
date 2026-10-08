# TECHNICAL_DESCRIPTION_AND_VISUALIZATION v1.0

## Syfte

Skapa källbundna tekniska beskrivningar och visualiseringar från aktuell verifierad Home Agent-data utan att ändra strukturerad data.

Workflowet är skrivskyddat och följer Home Agent-specifikationen och Workflow Core.

## Grundflöde

**Current-readback → Scope → Komponent-/relationsurval → Edge-lista → Beskrivning eller deterministisk grafkälla → Validering → Presentation**

Workflowet får inte användas för att skapa eller korrigera Home Agent-data.

## 1. Läs Current

Läs aktuell source of truth enligt Workflow Core.

När strukturerad Home Agent-data behövs ska den faktiska snapshotten i `Home Agent/System/Data Snapshots/Current/` inventeras och återläsas.

Historiska snapshots får inte användas som ersättning om Current inte kan läsas.

Om Current inte kan verifieras ska uppgiften stoppas som ett åtkomst-/synkroniseringsproblem.

## 2. Fastställ scope

Fastställ vilka system, komponenter, relationer, medier, kontrollrelationer eller andra strukturer som ska beskrivas eller visualiseras.

Ta endast med data som behövs för det begärda scopet.

Skilj vid behov mellan exempelvis:

- hydrauliskt huvudflöde
- hydrauliska sidoanslutningar
- parallella flödesvägar
- elektrisk matning
- styrrelationer
- fysisk placering

Utvidga inte scopet genom tekniska antaganden.

## 3. Bevara confidence och källstatus

Workflow Cores regler för källor, evidens och confidence gäller oförändrat.

Bevara:

- `Confirmed`
- `Likely`
- `Unknown`

En teknisk beskrivning eller visualisering får inte uppgradera confidence.

Unknown geometri, fysisk ledningsdragning, våningsmappning eller annan okänd detalj får inte fyllas i genom antagande för att göra en bild eller beskrivning mer komplett.

## 4. Komponent- och relationsurval

Identifiera de komponenter och relationsobjekt i Current som uttryckligen stöder den tekniska beskrivningen.

För exakt topologi ska varje teknisk kant först uttryckas som:

`from_ref → relation_id → to_ref`

Varje kant i en exakt teknisk graf måste motsvara ett relationsobjekt i Current.

Mellanliggande komponenter som förekommer i relationskedjan får inte elimineras i en exakt teknisk graf.

Skapa inte en direktrelation genom att slå ihop två eller flera relationer.

## 5. Edge-lista

Före exakt teknisk rendering ska en edge-lista skapas eller valideras från Current.

Edge-listan är renderingskontraktet för topologin.

För varje kant ska minst följande kunna identifieras:

- `from_ref`
- `relation_id`
- `to_ref`
- relationstyp eller medium när detta behövs för korrekt presentation
- confidence när den är relevant för presentationen

Edge-listan får inte innehålla tekniska kanter som saknar stöd i Current.

## 6. Teknisk beskrivning

En teknisk textbeskrivning ska följa samma komponent- och relationsurval som edge-listan när topologi beskrivs.

Beskrivningen får gruppera information för läsbarhet men får inte ändra relationsordningen eller göra en indirekt kedja till en bekräftad direktrelation.

När en förenkling görs ska det framgå att den är en presentationsförenkling och inte en ny relation i Current.

## 7. Deterministisk grafkälla

För en exakt teknisk topologibild ska topologin först uttryckas i en strukturerad och deterministiskt validerbar grafkälla, exempelvis Mermaid eller annan motsvarande grafrepresentation.

Den strukturerade grafkällan ska valideras mot edge-listan före rendering.

Valideringen ska kontrollera minst:

- att samtliga obligatoriska noder finns
- att samtliga obligatoriska kanter finns
- att varje exakt teknisk kant motsvarar rätt `relation_id`
- att inga extra tekniska kanter har lagts till
- att inga obligatoriska mellanliggande komponenter har eliminerats

Den strukturerade grafkällan, inte en AI-baserad pixelanalys, är primär verifieringsyta för topologin.

## 8. Rendering och generativ bildframställning

Rendering av en redan validerad deterministisk grafkälla får användas för exakt teknisk topologi.

AI-baserad pixelkontroll får användas som kompletterande visuell kvalitetskontroll men är inte obligatorisk och får inte ersätta validering av edge-lista och strukturerad grafkälla.

Generativ bildframställning får användas för att illustrera komponenters visuella utseende eller för icke-auktoritativ visuell presentation.

Generativ bildframställning får inte bestämma vilka komponenter som är sammankopplade eller användas som auktoritativ källa för exakt teknisk topologi.

Om generativ grafik kombineras med en exakt topologigraf ska den deterministiskt verifierade topologin förbli styrande.

## 9. Förenklad översikt

En förenklad översikt får utelämna mellanliggande komponenter eller detaljer endast när detta uttryckligen framgår av presentationen.

En förenklad översikt får inte:

- framställa ett utelämnat mellanled som om Current innehöll en bekräftad direktrelation
- tilldela en presentationskant ett relations-ID som inte motsvarar kanten
- beskrivas som exakt teknisk topologi

När det är relevant ska det anges vilka typer av detaljer som har utelämnats.

## 10. Fysisk placering och geometri

Fysisk placering får endast visas med den precision som stöds av Current och dess källor.

Unknown fysisk ledningsdragning, rörgeometri, kabeldragning, portposition, våningsmappning eller annan rumslig relation får inte konstrueras visuellt genom teknisk sannolikhet.

Schematisk layout får användas för läsbarhet när den tydligt är schematisk och inte påstås visa verifierad fysisk geometri.

## 11. Skrivskydd och ansvar

Detta workflow får inte:

- ändra Home Agent-data
- skapa eller ändra pending
- skapa nya tekniska relationer
- ändra confidence
- arkivera eller flytta original
- utföra reconciliation
- skapa datasnapshot
- rotera Current eller History

Om beskrivningen eller visualiseringen avslöjar en möjlig datakonflikt eller saknad relation ska detta rapporteras som observation. Datamodellen får inte korrigeras inom detta workflow.

Workflow Core äger fortsatt regler för:

- Current och source of truth
- Google Drive
- källor och evidens
- confidence
- originalfiler
- gemensam rapportering och regelprioritet

Detta workflow äger endast den skrivskyddade transformationen från verifierad strukturerad data till teknisk beskrivning eller visualisering.

## 12. Rapportering

Rapportera när relevant:

- vilken Current-snapshot som faktiskt lästes
- scope
- använda komponent-ID:n
- använda relations-ID:n
- edge-lista eller sammanfattning av den
- `Confirmed`, `Likely` och `Unknown`
- om presentationen är exakt eller förenklad
- eventuella valideringsfel eller datakonflikter

Påstå inte att en visualisering är exakt teknisk topologi om edge-lista och strukturerad grafkälla inte har validerats.

## 13. Regressionstest: Current v013 vattenkedja

Detta avsnitt är ett regressionstest för workflowets renderingsregler och är inte en generell hårdkodad systemregel.

### Testdata

Den verifierade kedjan i testfallet är:

`component_water_filter_bypass → relation_water_010 → component_water_distribution_cold_section`

`component_water_distribution_cold_section → relation_water_016 → component_heat_pump_nibe_s1255`

`component_heat_pump_nibe_s1255 → relation_water_017 → component_water_distribution_hot_section`

Motsvarande läsbara ordning är:

**filterbypass → kallvattenfördelare → NIBE S1255 → varmvattenfördelare**

### Förväntat

En exakt teknisk graf ska innehålla samtliga tre separata relationer och den mellanliggande kallvattenfördelaren.

### Underkänt

En direkt teknisk kant mellan filterbypass och NIBE ska underkännas i detta test eftersom den hoppar över `component_water_distribution_cold_section` och saknar motsvarande relationsobjekt i testets Current-data.

## Work-effektivitet

Läs Current en gång per sammanhängande uppgift när samma verifierade snapshot kan användas genom hela körningen.

Extrahera komponenter, relationer och edge-lista i samma körning.

Validera strukturerad grafkälla före rendering så att topologifel stoppas innan visuell presentation skapas.

Använd inte generativ bildframställning när en deterministisk graf är tillräcklig för användarens behov.
