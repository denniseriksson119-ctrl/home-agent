# EQUIPMENT\_IDENTIFICATION v1.0

## Syfte

Identifiera fysisk utrustning från fotografier, märkskyltar och annan direkt produktinformation och koppla den till rätt objekt i Home Agent.

Workflowet följer Home Agent-specifikationen och Workflow Core.

## Input

Normalt:

- en eller flera nya bilder i `Home Agent/Inbox`
- eventuell information från användaren om vad bilderna föreställer eller var utrustningen finns
- aktuell verifierad och godkänd Home Agent-datasnapshot

## 1. Inventera

Inventera den faktiska Google Drive-mappen `Home Agent/Inbox`.

Enbart filer som returneras av den aktuella Drive-inventeringen får beskrivas som filer i Inbox.

Identifiera vilka filer som hör till den aktuella uppgiften.

Lämna övriga Inbox-filer orörda.

## 2. Gruppera bilder

Avgör vilka bilder som visar samma fysiska produkt.

Använd:

- synlig produkt
- märkning
- modell
- serienummer
- användarens uttryckliga information

Gissa inte att två bilder hör till samma produkt enbart därför att produkterna liknar varandra.

## 3. Identifiera fysisk produkt

Läs i första hand direkt produktinformation från märkplåt/etikett.

Extrahera när tillgängligt:

- tillverkare
- produkttyp
- exakt modell-/produktbeteckning
- E-Nr/PNC/produktnummer/artikelnummer
- serienummer
- FD-/produktionskod
- elektriska märkdata
- andra relevanta identifierare och märkdata

Bevara exakt skrivsätt när detta har identifierande betydelse.

Gissa inte svårlästa tecken.

## 4. Confidence

Klassificera varje relevant uppgift:

**Confirmed**
Direkt styrkt av läsbar källa eller uttryckligen bekräftad av användaren.

**Likely**
Starkt indicerad men inte tillräckligt styrkt för Confirmed.

**Unknown**
Kan inte fastställas från tillgängligt underlag.

Ange vid behov varför en uppgift inte är Confirmed.

## 5. Matcha mot Home Agent

Jämför den identifierade produkten med befintliga assets och components i aktuell verifierad source of truth.

Prioritera matchning mot befintligt objekt framför skapande av nytt objekt.

Använd bland annat:

- produkttyp
- tillverkare
- modell
- serienummer
- placering
- befintliga relationer
- användarbekräftelse

Skapa inte dubbletter på grund av förbättrad eller korrigerad modellbeteckning.

Exempel:

`FLM30` i befintlig data och `FLM 30` på märkplåt kan vara samma fysiska produkt med mer exakt skrivsätt, inte två modeller eller två assets.

## 6. Källprioritet

För den installerade fysiska apparaten är en läsbar märkplåt primär källa för dess egna identifierare och märkdata.

Användarens uttryckliga bekräftelse är giltig källa för sådant användaren faktiskt bekräftar, exempelvis:

- vilken fysisk produkt bilden visar
- vilken av två kända maskiner som fotograferats
- placering

En produktmanual får inte användas för att ersätta en mer exakt variantspecifik märkplåtsuppgift.

Manualer behandlas enligt dokumentets egen modellomfattning.

## 7. Skillnader mot source of truth

Rapportera separat:

- uppgifter som redan överensstämmer
- nya uppgifter
- mer precisa uppgifter
- möjliga korrigeringar
- konflikter
- fortsatt Unknown

En precisering av befintlig information innebär inte automatiskt att ett nytt objekt ska skapas.

Ändra inte source of truth under identifieringssteget.

## 8. Föreslå arkivering

När produkten är tillräckligt identifierad, föreslå permanent plats för originalbilderna.

Normal struktur:

`Home Agent/Homes/<Home>/07 Photos/Appliances/<Product>/`

Använd en stabil och begriplig produktbeteckning för mappen.

Flytta ingenting innan arkiveringen har godkänts, om användaren inte uttryckligen har instruerat att workflowet får genomföra hela processen utan mellanliggande godkännande.

## 9. Väntande registrering

Sammanställ nya eller korrigerade fakta som:

**Väntande registrering i strukturerad data**

Ange vilka befintliga asset/component-ID\:n informationen gäller.

Skapa inte ny YAML-snapshot inom detta workflow.

## 10. Rapport

Rapportera kompakt:

- behandlade källfiler
- identifierad produkt
- matchat asset/component
- Confirmed
- Likely
- Unknown
- skillnader mot source of truth
- föreslagen arkivplats
- väntande strukturerade ändringar

Undvik att återge hela workflowet i resultatet.

## 11. Arkivering efter godkännande

När användaren godkänner arkiveringen får nästa körning:

1. flytta samtliga godkända original i samma logiska batch
2. bevara originalfilnamn, format och innehåll
3. verifiera destinationen
4. återläsa filerna från destinationen
5. verifiera att de är läsbara
6. verifiera att de flyttade originalen inte längre finns i Inbox
7. lämna andra Inbox-filer orörda

Rapportera endast resultat och eventuella avvikelser.

## Work-effektivitet

Utför inventering, bildläsning, identifiering, source-of-truth-jämförelse och arkivförslag i samma Work-körning när möjligt.

Efter användarens godkännande ska flytt och efterföljande verifiering normalt göras tillsammans i en andra körning.

Målet är normalt:

**Körning 1: analysera och föreslå**

**Körning 2: arkivera och verifiera**

Ytterligare körningar ska bara göras när nya källor, fel eller verklig osäkerhet kräver det.

