# Äldre original till lokalt Home Agent-arkiv

Leverans: Home Agent 0.8.9. Ingen import sker vid installation eller uppstart.
Ägaren installerar, granskar planen och startar utvalt filurval i Home Agent.
Codex-läsverktygens scope och behörighet ändras inte.

## Vad som överförs

Den befintliga lokala dokumentpostens `source_file.google_drive_file_id` eller
exakta `source_file.drive_path` matchas mot en uttrycklig Drive-inventering.
Finns båda måste de överensstämma. Namn på dokument/utrustning används aldrig
för att välja ett befintligt objekt. `related_object_refs` löses mot redan
registrerade permanenta identiteter; okända eller tvetydiga mål stoppar dokumentet.
Dokumentet självt och dess explicit angivna mål får Source-kopplingar.

`additional_project_source_images` visas separat för granskning. Dessa explicita
bildreferenser får endast en kandidat om filnamnet är unikt i inventeringen;
användaren måste kontrollera och markera dem. En saknad huvudbild ersätts inte
automatiskt av kompletterande bilder. Filer utan säkra dokumentkopplingar,
exempelvis ny Inbox, visas som övriga och importeras inte i denna leverans.
Ingen ny faktaextraktion, ändring av utrustningsdata eller YAML-återimport görs.

## Två överföringsvägar

### Privat originalpaket — fungerar utan Pi:s Drive-inloggning

Använd befintlig auktoriserad Drive-anslutning för att hämta det granskade urvalet
oförändrat till en privat arbetsmapp utanför Git. Kontrollera faktisk åtkomst
och filstorlek; fillistning är inte bevis för att originalet har laddats ned.
Spara varje original under sitt Drive-ID. Skapa ett inventerings-JSON med
`files`, där varje post har `id`, `path` (äldre Drive-sökväg), `name`, `mime`,
`size` (byte) och valfritt tidigare verifierat `sha256`.

```sh
python3 scripts/build_source_bundle.py --inventory /private/selected.json --originals /private/originals --output /private/originals.zip
```

Exempelsökvägarna ska ersättas med privata arbetsmappar. Skriptet läser inga
credentials och gör inga nätanrop. Paketet innehåller `manifest.json` med SHA-256
och `originals/<Drive-ID>` med oförändrade byte. ZIP-sökvägar extraheras aldrig.
Högst 256 MB uppladdat/uppackat paket och 2 MB manifest stöds; dela större urval.
Fullständiga privata paket/inventeringar får aldrig läggas i kodrepo eller PR.

Öppna **Mer → Överför äldre original → Kopiera med originalpaket**, välj ZIP
och förhandsgranska. Paketet sparas i tilläggets beständiga privata lagring innan
import startas. Drive-referenser kommer här från det användargodkända paketet;
Pi har inte själv verifierat Google-konto eller Drive-föräldrar. Detta registreras
som kanalen `legacy_bundle_migration`, separat från direkt Drive-hämtning.

### Direkt Drive-hämtning — kräver faktisk separat importbehörighet på Pi

Ladda upp inventerings-JSON i samma vy. Tidigare inventeringsformat med
`drive.files` accepteras också. Den befintliga importkonfigurationen för begränsat
Drive-konto och godkänd delad rot måste redan fungera. En Codex-connector eller
sparad publiceringsinloggning bevisar inte detta. Funktionen skapar inget nytt
tokenflöde och ändrar ingen Google-konfiguration. Före varje fil verifieras
verklig Drive-föräldrastruktur under konfigurerad rot; endast GET används mot Drive.

## Granskning, lagring och återförsök

- Alla kryssrutor är omarkerade. Granska fil och dokument/rum/utrustning/system
  som ska kopplas; börja med en manual och bild.
- Förhandsgranskningen ändrar inga husdata. Den privata planen sparas separat.
- **Godkänn kopplingarna och överför markerade filer** startar en bakgrundskörning,
  en fil åt gången. Status uppdateras genom sidans Uppdatera status-länk.
- En SQLite-kontrollkopia skapas med SQLite backup-API och integrity_check före
  första körningen av planen. Det är inte en komplett backup av originalarkivet.
- Lokala objekt och identiteter binds till planens revision. Ändrat register
  stoppar återstående import tills en ny plan granskats. Drive-namn/media/storlek
  jämförs med planen; SHA-256 verifieras lokalt och paketets hash kontrolleras.
- Original med samma SHA-256 återanvänds endast efter kontroll av befintlig lokal
  fil och custody. Inga Source-ID:n ändras eller gamla original flyttas.
- Nya original läggs i `/data/sources/Photos/`, `Documents/Manuals/`,
  `Documents/Invoices/` eller `Documents/Other/`. Namnen börjar med fullt Source-ID
  följt av ett portabelt originalnamn. Originalnamnet bevaras också som metadata.
- Kopplingar, ingest-historik och audit skrivs i samma databastransaktion. Byte
  ändras inte. Äldre Drive-sökväg bevaras som provenance i importens audit,
  inte som lokal lagringssökväg eller domänidentitet.
- Paus sker efter aktuell fil. Efter omstart sker ingen automatisk fortsättning;
  öppna sparad plan och markera återstående filer. Ett avbrott efter databascommit
  men före statussparning kan köras om utan dubbla källor, kopplingar eller ingest.
- Öppna lokala original från **Dokument & objekt**, utrustningssidan eller
  rummets dokument-/systemlänkar. HTTP kontrollerar explicit Source-koppling,
  lokal custody och checksumma innan filer levereras. Inget nytt lässcope för
  Codex tillkommer.

Importerade paket, planer och kontrollkopior ligger i `/data/source-imports`.
Ingen automatisk retention/radering ingår. Säkerställ ledigt utrymme för paket,
kontrollkopia och slutliga original. Drive-filer och extern Inbox lämnas orörda.

## Ägarens Pi-prov efter merge och installation

1. Kontrollera att befintliga rum, anteckningar och utrustnings-ID:n finns kvar.
2. Förhandsgranska ett privat paket med en manual och bild. Kontrollera att
   källan kopplas till rätt befintligt dokument och de registrerade målen.
3. Överför urvalet. Öppna PDF och bild från utrustning, rum och dokument;
   kontrollera även systemvyn när explicit relation finns.
4. Läs via Codex: Source-ID, verklig PDF-sida och bildinnehåll. Bara uttryckligen
   NIBE-kopplade källor ingår fortfarande i Codex första lässcope.
5. Pausa/starta om och fortsätt resterande filer. Kontrollera oförändrade Source-ID:n
   och att antalet original inte dubblas. Prova felaktig paketchecksumma och
   en oåtkomlig Drive-fil med syntetiskt provmaterial.
6. Granska hela resterande urvalet före större överföring. Saknade original och
   oklara relationer ska kvarstå som olösta, inte få gissade ersättningar.

Lokala automatiska tester använder enbart syntetisk SQLite, PDF-byte och ZIP.
Verklig Google-behörighet, telefonuppladdning, ledigt Pi-utrymme och respons på
större paket måste verifieras av ägaren; godkänd CI bevisar inte dessa delar.
