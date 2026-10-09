# Drive-import: konfiguration och test

**Status:** experimentell; använd inte med privata kontots åtkomsttoken.

## Säkerhetsmodell
- Home Agent importerar endast från det särskilda Google-kontot som fått läsrättighet till en delad mapp.
- Ägarens privata Google-konto ska aldrig användas för import.
- Drive-backup till privata kontot är ett separat framtida system.
- Import gör inga skrivningar i Google Drive.

## Nuvarande manuell konfiguration
Servern förväntar sig följande filer på Pi:ns permanenta add-on-datavolym:
- `/data/drive_import_root_id`: ID för roten till den delade mappen.
- `/data/drive_import_access_token`: en **kortlivad** Google OAuth-access-token för det separata importkontot.

Filerna får **aldrig** checkas in i Git, skickas till loggar eller läggas i en okrypterad backup. Token-filen ska vara åtkomlig endast för tjänsten (filrättigheter 0600).

**Begränsning:** OAuth-inloggning och tokenförnyelse är ännu inte implementerade. Denna manuella tokenlösning är en utvecklingskoppling, inte en säker produktionslösning. Lägg inte in en token förrän inloggning, kontoverifiering och testflöde är färdiga.

## UI
Öppna en utrustning och välj **Importera från Google Drive**. Formuläret tar ett Drive-fil-ID, inte en webbadress. Servern kontrollerar mappens föräldrar mot godkänd rot innan nedladdning. Den nedladdade filen SHA256-verifieras och registreras som Source med Google Drive som importkälla; sedan länkas den till utrustningen.

## Återstående innan release
- OAuth-inloggning och tokenförnyelse utan att dela inloggningsuppgifter med ChatGPT.
- Bind kontot till förväntad identitet och säkra tokenlagring.
- Testa faktisk Drive API-åtkomst och hela importflödet på Pi.
- Automatiserade tester för deduplicering, avbrutna hämtningar, felaktig rot och nekad behörighet.
- Granska atomisk lagring och felåterhämtning vid ström-/diskfel.
