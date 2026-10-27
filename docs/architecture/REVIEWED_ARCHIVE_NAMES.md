# Granskade arkivnamn och lokal placering

Leverans: Home Agent **0.8.12**. Befintlig Codex Remote Test **0.1.7** används
för rapporten; ingen ny nyckel eller utökad läs-/skrivbehörighet krävs.
Detta genomför arkitekturens läsbara namn för granskade lokala original.
Ingen namnändring sker vid installation, uppstart eller en vanlig läsning.

## Namn och kataloger

Godkänt datum + kort beskrivning + kort Source-ID-hint + mediatypsändelse:

```text
Photos/2026/09/2026-09-14_synthetic-rating-plate__src-aabbccddee.jpg
Documents/Manuals/2026-01-02_synthetic-user-manual__src-1122334455.pdf
```

Hinten är de sista tio bokstäverna/siffrorna i Source-ID:t, utan bindestreck;
för korta syntetiska ID:n används en deterministisk SHA-256-hint. Hinten är
en mänsklig ledtråd, aldrig intern identitet eller en garanti mot kollision.
En befintlig annan målfil skrivs aldrig över, även om dess byte är identiska.
Beskrivningen normaliseras till portabla gemena ASCII-ord med bindestreck,
högst 80 tecken. Originalnamnet lagras oförändrat i Source-metadata.

Bilder placeras i `Photos/YYYY/MM`. Dokument använder `Documents/Manuals`,
`Documents/Invoices`, `Documents/Receipts`, `Documents/Warranties` eller
`Documents/Other` utifrån registrerad dokumenttyp. Ingen rums-/utrustningsbaserad
mappstruktur skapas. Olika kategorier från samma källas dokument stoppar planen
så att relationerna kan utredas; en AI väljer inte en kategori genom gissning.

## Okända och osäkra uppgifter

Ett registrerat `captured_at` föreslås som källdatum. Ett datum i ett filnamn som
`YYYYMMDD_HHMMSS.jpg` märks separat som **förslag från filnamn**, inte verifierat
fotograferingsdatum. Användaren bekräftar/ändrar datumet före namnbyte.
`imported_at`, en utrustnings installationsdatum, dagens datum och ett UUID:s
tidsstämpel används aldrig som påhittat källdatum.

Om datum är okänt måste datumfältet tömmas och **Datum är okänt** uttryckligen
markeras. Då används `undated_description__src-hint.ext`; bilder placeras i
`Photos/Undated`. Det uttryckliga undantaget bevaras i audit och visas i
arkivrapporten som `architectural_undated`, inte som ett känt kalenderdatum.

En ensam registrerad dokumenttitel kan föreslås som beskrivning. Saknad eller
tvetydig titel ger inget automatiskt beskrivningsförslag. Användaren granskar
betydelsen och måste skriva en användbar beskrivning. Ingen ny faktaextraktion,
ändring av dokumentinnehåll eller gissad rum-/utrustningskoppling ingår.

## Två steg i Home Agent

1. Öppna **Mer → Granska arkivnamn**. Markera högst tio källor på sidan och
   granska datum, osäkerhetsmärkning och beskrivningar.
2. **Förhandsgranska valda namn** sparar en privat plan och visar exakta gamla
   och nya relativa sökvägar. Inga original eller domänuppgifter ändras.
3. **Godkänn och genomför dessa namnbyten** startar en bakgrundskörning, en fil
   åt gången. Planen kan öppnas igen för status och återupptagning efter avbrott.
4. Kontrollera resultatet i **Mer → Arkivkontroll** och öppna originalet genom
   dess befintliga dokument-/utrustningslänk. Fortsätt därefter med **Granska nästa omgång**.

Från 0.8.12 visar standardlistan bara kvarvarande namn att granska, med antal
kvar, färdiga och totalt. Ett redan arkitekturenligt namn på rätt plats med
entydig kategori, lokal custody och registrerad SHA-256 räknas som färdigt;
även `undated` räknas. Befintliga namn från 0.8.11 känns igen utan ny körning.
Urvalet filtreras **före** sidindelning (högst tio synliga källor), så nästa
omgång inte återanvänder färdiga filer. Högst 2000 källor stöds i denna vy.
En förhandsgranskad eller misslyckad ändring lämnar källan kvar i arbetslistan.

**Visa färdiga arkivnamn** öppnar en separat vy för frivillig omgranskning.
En klar plan länkar till **Granska nästa omgång**. Den skrivskyddade
arkivkontrollen behåller alla registrerade källor. Arbetslistans räknare gäller
namnsättning enligt metadata, inte filernas existens eller checksummeverifiering;
dessa kontroller hör fortsatt till arkivkontrollen. Enbart öppning av listan
ändrar inga data, filer eller sparade planer.

CSRF och origin-kontroll krävs vid båda POST-stegen. Inga godkännandekryssrutor
är förvalda. Pågående paketimport blockerar start av namnplan; pågående namnbyte
blockerar ny paketimport. Ingen ny mobil filuppladdning behövs för namnbytet.

## Identitet, original och återhämtning

Source-ID, SHA-256, originalnamn, registrerade datum och alla `source_link`-rader
bevaras. Endast `source.storage_ref` uppdateras och en `archive_name`-händelse
registreras med gammal/ny relativ sökväg, granskat datum/datumgrund, beskrivning,
plan-ID och checksumma. De vanliga objektvyerna kan fortsatt visa originalnamnet;
arkivkontrollen visar det faktiska nya lagringsnamnet.

Planer och journal ligger privat i `/data/archive-name-plans`. Före första
körningen skapas en konsekvent SQLite-kontrollkopia med backup-API och
integrity_check. Det är inte en komplett återställningsbackup med gamla fysiska
sökvägar: ursprungliga byte finns efter godkänt namnbyte på den nya platsen och
gammal/ny referens finns i plan/audit. Full backup/restore är fortsatt separat.

Varje källa binds till förhandsgranskningens metadata och kopplingar. Ändrad
källa eller ändrade mål stoppar ej utförda namnbyten tills en ny plan granskats.
Originalet öppnas med `O_NOFOLLOW` för varje sökvägskomponent och SHA-256-verifieras.
Det nya namnet skapas som en hård länk till samma verifierade inode, utan att
ersätta befintliga filer. Målet verifieras innan databasreferens och audit
committas atomiskt. Därefter tas det gamla aliaset bort endast om det fortfarande
är exakt samma inode och ingen Source-rad refererar till den gamla platsen.

Ett avbrott före databascommit kan återuppta den egna hårda länken. Ett avbrott
efter commit kan återuppta städningen utan en ny audit eller nya Source-ID:n.
Misslyckad commit lämnar den gamla referensen och originalet fungerande; egen
ny länk tas bort endast när databasen säkert inte refererar till den.
Osäker städning lämnar `cleanup_pending` och tar inte bort en annan fil.
En identisk redan genomförd namnplan blir `unchanged` utan dubbla domänändringar.

En fil får vara högst 256 MiB, med åtta sekunders budget per verifieringsläsning.
Codex-läsning, lokal filöppning/arkivkontroll och namnbyten använder samma
exklusiva läs-/filoperationsplats. En begäran under namnbyte får ett tydligt
upptaget-svar i stället för att öppna en sökväg mellan kontroll och borttagning.
Flera filer utgör inte en enda atomisk batch: framsteg är beständigt per källa.
Det finns ingen automatisk återställning av en redan godkänd och committad batch.

## Arkivkontrollen efter uppdatering

`rules_version: archive-0.8.11` skiljer nu följande format åt:

- `architectural`: granskat datum, beskrivning och kort ID samt rätt katalog;
- `architectural_undated`: arkivnamn med uttryckligen okänt datum;
- `technical_preserved`: tidigare fullt Source-ID + originalnamn, ännu inte
  arkitekturens läsbara namn;
- `legacy_preserved`: äldre fil direkt under källagret med Source-ID som namn;
- `deviation` och `not_checked`: avvikelse respektive ej verifierad kontroll.

Det gamla tekniska importformatet kan fortfarande användas för säkert intag,
innan datum/beskrivning granskats. Rapporten kallar det inte längre färdig
arkitekturnamnsättning. Ingen fil behöver importeras igen för att få ett arkivnamn.

## Ägarens Pi-prov

1. Uppdatera Home Agent till 0.8.12. Bekräfta att enbart installationen inte
   ändrar namn, källantal, ID:n, kopplingar eller innehåll.
2. Välj en bild med granskat datum och en manual med uttryckligen okänt datum.
   Kontrollera gammal/ny sökväg och beskrivning före det andra godkännandet.
3. Genomför planen. Öppna båda originalen från tidigare objektlänkar och läs
   kontrollrapporten via Codex. Kontrollera oförändrade Source-ID:n och SHA-256.
4. Öppna den avslutade planen igen; återförsök får inte dubblera källor/audit.
   Prova avbrott/omstart endast med godkänt syntetiskt provmaterial först.
5. Fortsätt med högst tio källor per granskning. Lämna osäkra beskrivningar och
   kopplingar för separat utredning. Två okopplade bilder får inte automatiskt
   rums-/utrustningskoppling bara för att de ges ett nytt arkivnamn.

Automatiska tester använder syntetiska data. CI provar riktiga tvåstegsformulär,
namnbyte, befintlig PDF-/bildhämtning och arkivrapport i ARM64-/amd64-containrar.
Verkliga datum, beskrivningar, Pi-prestanda och hushållets filer granskas av ägaren.
