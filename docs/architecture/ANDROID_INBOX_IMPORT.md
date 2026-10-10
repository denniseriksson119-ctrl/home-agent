# Android → Inbox: första NIBE-importen

Home Agent tar emot original via **Lägg till → Foto eller dokument → Spara i Inbox**. På Android kan systemets filväljare visa Google Drive som källa (beroende på installerad Drive-app och Androids filväljare). Ingen Google Cloud OAuth-konfiguration behövs för detta.

## Inventering av befintligt material i Drive

- NIBE S1255-12 CU EM: foto `20260914_213851.jpg` (2 215 662 byte).
- NIBE S1255: `MDIyNTA4LzAvbWFzdGVy.pdf` (487 721 byte).
- NIBE S1255: `MTIxMTA4LzAvbWFzdGVy.pdf` (11 791 641 byte).
- NIBE S1255: `MTIxMTU0LzAvbWFzdGVy.pdf` (2 262 298 byte).

Filnamnen på PDF:erna bekräftar **inte** dokumenttyp; kontrollera innehållet innan de kopplas. Blanda inte in NIBE FLM 30 som om den vore S1255.

## Test efter uppdatering

1. Öppna Home Agent på Android och välj **Lägg till**.
2. Välj en av PDF-filerna i Drive via Androids filväljare.
3. Kontrollera att originalet syns i Inbox och går att öppna.
4. Upprepa med PDF:en på cirka 11,8 MB; tidigare 5 MB-gräns ska inte stoppa den.
5. Ladda upp samma fil igen; det ska skapas en ny importhändelse men inte en andra kopia av originalet.
6. Kontrollera att metadata och filkoppling till `eq_heat_pump_nibe_s1255` ännu **inte** godkänns automatiskt.

## Avgränsning

Denna ändring möjliggör större originalfiler med strömmande SHA-256-inläsning (25 MiB filgräns, 26 MiB begärandegräns). Inbox analys/identifiering, importförslag och manuellt godkännande återstår. YAML-snapshot-importen och befintlig utrustningsuppladdning har fortfarande sin separata 5 MB-gräns. Ingen automatisk import eller registrering av utrustningsmetadata sker här.
