# FIND\_AND\_COLLECT v1.0

## Syfte

Hitta tillförlitlig extern dokumentation för ett känt Home Agent-objekt och samla relevanta originaldokument för senare analys.

Workflowet används för dokumentinsamling, inte för registrering av nya fakta i Home Agent-data.

Workflowet följer Home Agent-specifikationen och Workflow Core.

## Input

Normalt:

- ett känt asset, component, system eller annan produkt
- tillverkare
- modell eller annan identifierare
- aktuell verifierad Home Agent-data när den behövs för identifikation

Ju mer exakt fysisk produktidentifiering som redan finns, desto mer exakt ska sökningen vara.

## 1. Fastställ sökidentitet

Använd i första hand den mest exakta verifierade identifieringen som finns.

Prioritetsordning:

1. exakt variant, E-Nr, PNC eller motsvarande
2. exakt modell
3. grundmodell
4. produktfamilj

Hitta inte på saknade suffix eller variantnummer.

Om exakt variant är känd ska sökningen börja där.

## 2. Sök källor

Prioritera:

1. officiell supportsida för exakt variant
2. officiell supportsida för grundmodell
3. tillverkarens officiella dokumentserver
4. annan auktoritativ källa
5. tredje part endast när bättre källa saknas eller när den behövs för historiskt material

Föredra tillverkarens originaldokument framför kopior hos dokumentaggregatorer.

## 3. Dokumentets modellomfattning

Klassificera dokumentets scope som exempelvis:

- exakt variant
- grundmodell
- produktfamilj
- generell

Gör inte ett grundmodelldokument variantspecifikt enbart därför att det hittades under sökning på en exakt variant.

Om tillverkarens officiella supportsida för en exakt variant länkar till ett dokument för grundmodellen får detta registreras som stöd för att tillverkaren kopplar dokumentet till varianten.

Dokumentets eget modell-scope ska ändå bevaras.

## 4. Identifiera dokument

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
- officiell källa

Tolka inte interna dokumentkoder som datum, revision eller produktionsinformation utan stöd.

Om informationen inte kan fastställas ska den vara Unknown.

## 5. Prioritera relevanta dokument

Prioritera sådant som kan ha bestående värde för Home Agent, exempelvis:

- användarmanual
- installationsmanual
- servicemanual
- tekniskt datablad
- produktblad
- reservdelsdokumentation
- elschema
- installationsritning
- officiell underhållsinformation

Undvik onödiga dubbletter, irrelevanta språkversioner och föråldrade dokument om de inte har historiskt värde för den installerade produkten.

## 6. Webbsidor och dokument

En officiell supportsida kan vara viktig som evidens för modellkoppling och dokumentrelation.

Själva supportsidan behöver normalt inte sparas som permanent originalfil.

Prioritera nedladdningsbara originaldokument, exempelvis PDF, för Inbox och permanent arkiv.

Bevara källreferensen till supportsidan när den behövs för att styrka dokumentets relevans.

## 7. Dubblettkontroll

Kontrollera om dokumentet redan finns eller redan har identifierats.

Jämför när möjligt:

- dokumentnummer
- filnamn
- modell
- språk
- revision
- innehåll

Spara inte samma original flera gånger utan anledning.

## 8. Insamling

Rekommendera eller spara relevanta originaldokument till:

`Home Agent/Inbox`

Inbox är endast mellanlandning.

Dokumenten ska senare behandlas med `INBOX_ANALYSIS`.

Ändra inte originaldokumentets innehåll.

## 9. Ingen strukturerad registrering

Detta workflow ska inte:

- skapa ny Home Agent-datasnapshot
- ändra befintliga assets/components
- registrera tekniska fakta från dokumenten som source of truth
- skapa tekniska relationer från sökresultat

Dokumentens innehåll analyseras i `INBOX_ANALYSIS`.

## 10. Rapport

Rapportera kompakt:

- vilken produkt/objekt sökningen gällde
- vilken identifiering sökningen baserades på
- hittade officiella källor
- rekommenderade dokument
- dokumentens modellomfattning
- eventuella osäkerheter
- vilka original som sparades/rekommenderades till Inbox
- eventuella dubbletter som undveks

## Work-effektivitet

Sök, verifiera källor, bedöm modellomfattning och samla rekommenderade dokument i samma körning när möjligt.

Batcha dokument som gäller samma produkt eller logiska dokumentgrupp.

Undvik separata Work-körningar för varje PDF när de kan hanteras tillsammans.

Målet är normalt en sök-/insamlingskörning per produkt eller logisk dokumentgrupp.

