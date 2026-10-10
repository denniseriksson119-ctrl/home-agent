# Drive-import: konfiguration och test

**Status:** experimentell; använd inte med privata kontots åtkomsttoken.

## Säkerhetsmodell
- Home Agent importerar endast från det särskilda Google-kontot som fått läsrättighet till en delad mapp.
- Ägarens privata Google-konto ska aldrig användas för import.
- Drive-backup till privata kontot är ett separat framtida system.
- Import gör inga skrivningar i Google Drive.

## OAuth-konfiguration (ännu ej färdigt användarflöde)
På Pi behövs:
- `/data/drive_import_root_id`: ID för delad rotmapp.
- `/data/drive_import_oauth.json`: JSON med `client_id`, `client_secret`, `refresh_token`, `expected_email` för **det separata Home Agent-kontot**.

OAuth-konfigurationsfilen måste ha filrättigheter `0600`. Servern förnyar access-token vid varje import och verifierar den autentiserade e-postadressen mot `expected_email` innan Drive API används. OAuth-refresh kräver att en giltig refresh-token redan utfärdats med nödvändiga scopes; koden skapar **inte** denna token ännu. Kontots e-post verifieras med Google UserInfo och kräver `openid email` vid ursprungligt samtycke, utöver läsbehörighet till Drive.

**Viktigt:** Lägg inte in tokens i Git eller i chatten. Manuell provisionering och lagring av refresh-token på disk är inte en färdig säker installationslösning. Säker autentiseringsstart och skydd av token i backup återstår.

## UI
Öppna en utrustning och välj **Importera från Google Drive**. Formuläret tar ett Drive-fil-ID, inte en webbadress. Servern kontrollerar mappens föräldrar mot godkänd rot innan nedladdning. Den nedladdade filen SHA256-verifieras och registreras som Source med Google Drive som importkälla; sedan länkas den till utrustningen.

## Återstående innan release
- OAuth-inloggning och tokenförnyelse utan att dela inloggningsuppgifter med ChatGPT.
- Bind kontot till förväntad identitet och säkra tokenlagring.
- Testa faktisk Drive API-åtkomst och hela importflödet på Pi.
- Automatiserade tester för deduplicering, avbrutna hämtningar, felaktig rot och nekad behörighet.
- Granska atomisk lagring och felåterhämtning vid ström-/diskfel.

## Första inloggningen på egen dator

1. Skapa en OAuth-klient av typen **Desktop app** i ett Google Cloud-projekt som du kontrollerar. Aktivera Google Drive API, konfigurera OAuth consent och nödvändiga scopes (`openid`, `email`, `drive.readonly`). Lägg det särskilda Home Agent-kontot bland testanvändare om appen är i testläge.
2. Kör `python3 tools/drive_oauth_setup.py CLIENT_ID CLIENT_SECRET HOME_AGENT_EMAIL` **på din egen dator** med webbläsare. Välj endast det begränsade Home Agent-kontot vid Google-inloggningen.
3. Skriptet skapar `drive_import_oauth.json` med behörighet 0600 i aktuell katalog. Kopiera filen säkert till `/data/drive_import_oauth.json` på Pi, och skapa `/data/drive_import_root_id` med ID för den delade rotmappen. Dessa filer ska inte ligga i Git eller delas i chatten.
4. Starta om add-on och prova import från utrustningssidan med ett Drive-fil-ID. Kontrollera att originalet visas på utrustningen och att Drive-originalet är oförändrat.

**Obs:** OAuth-appar i Google Cloud med status Testing kan ge refresh-token med kort livslängd. För långsiktig drift krävs korrekt OAuth-konfiguration och eventuellt ny inloggning. Läsbegränsningen är på API-scope-nivå; ett vanligt `drive.readonly`-scope kan tekniskt läsa andra filer som importkontot har tillgång till. Använd därför ett separat konto med åtkomst endast till avsedd delning.
