# INBOX\_ANALYSIS v1.1

## Syfte

Analysera originalfiler i `Home Agent/Inbox`, extrahera källstödda fakta, koppla materialet till rätt Home Agent-objekt och förbereda permanent arkivering samt väntande strukturerad registrering.

Workflowet följer Home Agent-specifikationen och Workflow Core.

## Input

Normalt:

- en eller flera originalfiler i `Home Agent/Inbox`
- aktuell verifierad och godkänd Home Agent-datasnapshot
- eventuell redan verifierad produktidentifiering eller användarinformation

## 1. Inventera Inbox

Inventera den faktiska Google Drive-mappen `Home Agent/Inbox`.

Endast filer som returneras av den aktuella Drive-inventeringen får beskrivas som filer i Inbox.

Project Sources, scratch, projektkontext eller tidigare kända filnamn är inte bevis för aktuell Inbox-placering.

Identifiera vilka filer som hör till aktuell uppgift.

Lämna övriga Inbox-filer orörda.

## 2. Läs originalen

Läs originalfilerna direkt från Google Drive.

Analysera det faktiska dokumentet, inte en rekonstruerad version från tidigare chattminne eller sammanfattning.

Om en känd fil inte kan läsas ska detta behandlas som ett åtkomstproblem.

Gissa inte innehållet och ersätt inte originalet med tidigare AI-tolkning.

## 3. Identifiera dokumentet

Fastställ när möjligt:

- dokumenttyp
- titel
- utgivare/tillverkare
- dokumentnummer
- modellomfattning
- språk
- revision/utgåva
- publiceringsdatum
- sidantal

Tolka inte interna koder som datum, revision eller annan metadata utan stöd.

## 4. Fastställ scope

Klassificera vad dokumentet faktiskt gäller, exempelvis:

- exakt fysisk individ
- exakt produktvariant
- grundmodell
- produktfamilj
- system
- byggnad
- projekt
- generell dokumentation

Skilj dokumentets eget scope från extern evidens om relevans.

Exempel:

En officiell supportsida för en exakt variant kan visa att tillverkaren kopplar ett grundmodelldokument till varianten.

Det gör inte dokumentets egna formuleringar variantspecifika.

## 5. Extrahera relevanta fakta

Följ Workflow Cores princip:

**Extrahera brett men registrera selektivt utifrån långsiktigt förvaltningsvärde.**

Analysera dokumentet tillräckligt brett för att förstå innehåll och sammanhang. Ta endast vidare information med bestående förvaltningsvärde som väntande strukturerad registrering.

Det kan exempelvis vara:

- identifierare
- tekniska data
- installationskrav
- dimensioner
- anslutningar
- kapacitet
- säkerhetsinformation
- driftinformation
- underhåll
- felsökning
- serviceinformation
- garanti
- kostnader för historik över hem, service, underhåll och projekt
- projektinformation
- byggnadsinformation

Registrera inte betalnings- eller fakturaadministration såsom betalningsstatus, förfallodatum, betalningsvillkor, bankuppgifter eller kundnummer enbart därför att informationen finns i dokumentet.

Undvik att registrera hela manualen som strukturerad data.

## 6. Källkontext och confidence

Koppla extraherade fakta till dokumentets scope och källa.

Använd:

- Confirmed
- Likely
- Unknown

En uppgift som är Confirmed som dokumentinnehåll är inte automatiskt Confirmed som installerad fysisk konfiguration.

Generell eller modellgemensam information får inte omtolkas som observerad fysisk installation.

## 7. Möjliga funktioner och konfigurationer

Dokument kan beskriva:

- möjliga funktioner
- tillbehör
- alternativa installationer
- kapaciteter
- rekommenderade anslutningar
- möjliga inställningar

Detta bevisar inte att dessa används eller finns installerade i huset.

Skapa inga tekniska relationer enbart därför att manualen beskriver dem.

## 8. Jämför med source of truth

Jämför relevanta fakta med aktuell verifierad Home Agent-data.

Klassificera resultatet som:

- redan överensstämmande
- ny information
- mer precis information
- möjlig korrigering
- dokumentavvikelse
- konflikt
- fortsatt Unknown

Ändra inte source of truth under analysen.

## 9. Dokumentavvikelser

Om två tillförlitliga dokument anger olika värden ska båda bevaras med respektive dokumentkontext.

Normalisera inte automatiskt bort skillnaden.

Dra inte slutsatsen att ett dokument är fel utan ytterligare stöd.

## 10. Underhåll

När dokument innehåller underhållsinstruktioner, skilj mellan exempelvis:

- efter varje användning
- regelbundet intervall
- vid behov
- kontroll/inspektion
- professionell service

Skapa inte automatiskt återkommande Home Agent-underhållsuppgifter om dokumentet inte ger tillräckligt stöd för ett faktiskt intervall eller om uppgiften kräver användarbeslut.

## 11. Matcha Home Agent-objekt

Koppla dokumentet och nya fakta till befintliga objekt när stöd finns.

Använd befintliga ID\:n för exempelvis:

- home
- asset
- component
- system
- room
- project

Skapa inte dubbletter därför att ett dokument använder en något annan produktbeteckning.

## 12. Föreslå arkivering

Föreslå permanent Drive-plats utifrån dokumenttyp och objekt.

Exempel:

- `02 Manuals`
- `03 Receipts & Invoices`
- `04 Warranties`
- `05 Service & Maintenance`
- `06 Projects`
- `08 Other Documents`

Använd relevant undermapp för produkt, system eller projekt.

Flytta inte original innan arkiveringen godkänts, om inte användaren uttryckligen har godkänt ett automatiserat flöde.

## 13. Väntande registrering

Sammanställ registreringsunderlag som:

**Väntande registrering i strukturerad data**

Ange när relevant:

- berörda objekt-ID\:n
- nya eller preciserade fakta
- confidence
- källfil
- dokumentrelationer
- konflikter
- kvarvarande Unknown

Skapa inte en ny Home Agent-datasnapshot inom detta workflow.

## 14. Arkivering efter godkännande

Efter användarens godkännande:

1. flytta godkända original till permanent Drive-plats
2. bevara originalfilnamn, format och innehåll
3. verifiera destinationen
4. återläs filerna från destinationen
5. verifiera läsbarhet
6. verifiera att de flyttade originalen inte längre finns i Inbox
7. lämna andra Inbox-filer orörda

Arkivering innebär inte automatiskt att informationen är registrerad i source of truth.

## 15. Lokal filskrivning

Om lokal filskrivning finns tillgänglig får den användas för tillfälliga analysartefakter eller strukturerade pending-underlag.

Workflowet får inte vara beroende av att lokal filskrivning fungerar.

Misslyckad lokal filskrivning ändrar inte source of truth och ska inte orsaka en ny dataversion.

## 16. Rapport

Rapportera kompakt:

- analyserade original
- dokumentidentitet och scope
- relevant ny information
- matchade Home Agent-objekt
- konflikter/dokumentavvikelser
- Unknown
- föreslagen arkivplats
- väntande registrering

Undvik att återge hela dokumentet eller workflowet.

## Work-effektivitet

Inventera, läs, analysera, jämför med source of truth och föreslå arkivering i samma körning när möjligt.

Batcha dokument som hör till samma produkt eller logiska ärende.

Efter godkännande ska flytt och verifiering normalt göras tillsammans i en andra körning.

Målet är normalt:

**Körning 1: analysera och föreslå**

**Körning 2: arkivera och verifiera**

Ytterligare körningar ska bara göras när källfel, nya dokument eller verkliga konflikter kräver det.

