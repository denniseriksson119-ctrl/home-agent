# Google Drive från telefonen — Home Agent 0.8.6

> **2026-10-26:** Drive-publicering är pausad som AI-huvudspår. Använd [Codex-läskopplingen](CODEX_HOME_AGENT_READ.md). Detta dokument beskriver den tidigare vägen; Drive-backup/arkiv planeras separat.

**Godkänt av ägaren:** 2026-10-18, "gör uppdateringen".
**Status:** Implementerat för granskning; verkligt Google-godkännande och Pi-publicering återstår som installationsprov.

Pi använder Googles enhetsflöde för en installation utan egen webbläsare. Användaren godkänner på telefonen. Ingen dator, terminal, lokal Python-körning eller manuell överföring av en tokenfil behövs för denna väg. Google Cloud kräver fortfarande en engångsinställning i webbläsaren.

Den automatiska läspubliceringen från 0.8.5, lokala original, databas, permanenta ID:n och Inbox fungerar som tidigare. Detta är en anslutningsfunktion, inte modell-API-integration eller import av AI-förslag. Anslutning i ChatGPTs Drive-plugin ger inte Pi denna behörighet.


## Förtydligande 2026-10-19 — befintlig delad mapp

Ägaren använder ett huvudkonto med befintligt lagringsabonnemang och en befintlig Home Agent-mapp som delas med det separata Home Agent-/ChatGPT-kontot. Endast mappen är delad, inte Google One-lagringen. Se [kontoprincipen](GOOGLE_DRIVE_ACCOUNTS_AND_STORAGE.md) och [backlog](../development/BACKLOG.md).

**Nuvarande implementation skapar en separat appmapp på det autentiserade kontot. Den är ännu inte anpassad till den befintliga delade roten.** Stegen nedan beskriver den levererade implementationen, inte en färdig lösning för denna installation. Nästa leverans ska först verifiera appauktorisering och publicering till rätt rot (BL-DRIVE-001); därefter återupptas Google-/Pi-/ChatGPT-provet. Enbart mapp-ID eller kontots delningsrätt löser inte appåtkomst med `drive.file`. Ägaröverföring och återställningsbar backup ingår inte i 0.8.6.


## Engångsinställning hos Google

Gör detta med kontot vars Drive ChatGPT ska läsa. På en telefon kan Cloud Console behöva webbläsarens datorvy för att visa alla fält.

1. Öppna [Google Cloud Console](https://console.cloud.google.com/) och välj eller skapa ett separat projekt, exempelvis **Home Agent**. Aktivera **Google Drive API** under API:er och tjänster → Bibliotek. Ändra inte ett projekt för den tidigare read-only-importen.
2. Öppna **Google Auth platform → Branding → Get started**, om ingen OAuth-app finns. Ange appnamn **Home Agent** och din e-post som support-/kontaktadress. För ett vanligt privat Google-konto, välj **External** som målgrupp.
3. Om appen är i testläge: öppna **Audience → Test users** och lägg till ditt eget Google-konto. Endast avsedda testanvändare kan då godkänna. Googles regler för testläge kan göra att refresh-token behöver förnyas efter sju dagar när Drive-behörighet ingår. Ett stabilt samtyckes-/publiceringsläge i Google är ett separat driftssteg; ändra inte målgrupp blint för att dölja varningar.
4. Under **Data Access** lägger du till `openid`, e-post (`email` / `https://www.googleapis.com/auth/userinfo.email`) och `https://www.googleapis.com/auth/drive.file`. Den senare avser filer appen skapar eller uttryckligen får åtkomst till, inte generell Drive-åtkomst. Pi begär exakt dessa tre behörigheter.
5. Öppna **Clients → Create client**. Välj **TVs and Limited Input devices** och ett namn, exempelvis **Home Agent Pi**. **Desktop app** hör till det äldre skriptflödet och fungerar inte med den här enhetsinloggningen.
6. Behåll klient-ID och klienthemlighet privat. Mata in dem direkt i Home Assistant i nästa steg. De ska inte skickas i chatt, Git eller skärmbilder.

## Inställning i Home Assistant

1. Öppna **Inställningar → Appar/Tillägg → Home Agent → Konfiguration**.
2. Under **Google Drive** (`google_drive`) fyller du i:
   - `client_id`: klient-ID från Google.
   - `client_secret`: klienthemligheten, ett lösenordsfält i Home Assistant.
   - `expected_email`: hela e-postadressen för det Google-konto som ska godkänna. Använd samma konto som Drive-anslutningen i ChatGPT, eller dela senare den skapade mappen uttryckligen till det kontot.
3. Spara och starta om Home Agent. Backend läser värdena från add-onens `/data/options.json`; inga värden skrivs in i vanlig Home Agent-UI.
4. Öppna Home Agent via dess lokala adress, exempelvis `http://192.168.1.246:8099`, och välj **Mer → ChatGPT via Drive → Anslut Google Drive**.
5. Tryck **Anslut Google Drive**. Pi hämtar en användarkod och Googles länk. Sidan uppdateras automatiskt medan arbetet sker i bakgrunden.
6. Öppna Google-länken, ange koden exakt och godkänn för det förväntade kontot. Läs att behörigheterna gäller din egen Home Agent-app. Återvänd till Home Agent-sidan; Pi kontrollerar svaret automatiskt och sparar behörigheten lokalt efter kontokontroll.
7. Öppna **Mer** och kontrollera första lyckade publiceringen samt indexlänken. Publiceringen väcks direkt vid lyckad anslutning och fortsätter därefter enligt 0.8.5-schemat.

Den skapade Drive-mappen delas inte automatiskt. Om ChatGPT använder ett annat Google-konto behöver ägaren dela just denna mapp. Google kan kräva ny anslutning/synk i ChatGPT för att filerna ska hittas. Slutprovet är att läsa verkligt innehåll via det aktuella indexet och öppna rätt PDF, inte bara att kontonamnet visas.

## Fel och återförsök

- **Fel klient / invalid_client:** kontrollera ID, hemlighet och att klienttypen är **TVs and Limited Input devices**.
- **Åtkomst nekad:** kontrollera appens målgrupp, testanvändare och eventuella Workspace-policyer. Ingen ny token sparas vid nekande.
- **Utgången kod:** tryck på anslutningsknappen igen för en ny kod. Samma aktiva försök återanvänds vid dubbeltryck.
- **Fel Google-konto / otillräcklig behörighet:** inga nya credentials sparas. Välj rätt konto och godkänn de tre behörigheterna.
- **Tillfälligt nätfel:** Pi väntar innan nästa försök, inom kodens livslängd. Google `slow_down` ökar pollningsintervallet med fem sekunder.
- **Omstart:** ett väntande försök återupptas från privat sparat tillstånd om koden inte gått ut. Om avbrottet sker efter att credentials sparats men före slutstatus återhämtas detta via försökets ID. Ett avbrott efter att Google förbrukat koden men innan credentials kunnat sparas kräver en ny kod; gamla fungerande credentials lämnas kvar.
- **Avbryt inloggningen:** stoppar det lokala försöket och rensar dess koder. Det återkallar inte en redan sparad Google-behörighet, stoppar inte befintlig publicering och tar inte bort filer från Drive.
- **Anslut på nytt:** tillåter ny inloggning med samma klient och förväntade konto, exempelvis efter återkallad/utgången Google-token. Den gamla konfigurationen ersätts först efter ett nytt verifierat godkännande. Byte av klient/projekt/konto är spärrat för befintlig konfiguration eftersom Drive-mappningarna annars kan bli fel; det kräver en separat migrering.

## Säkerhetsgräns

Klientuppgifterna matas in via Home Assistants skyddade konfiguration. De returneras aldrig i Home Agents anslutningssida, läsunderlag eller loggar. Home Assistant-inställningar och säkerhetskopior som innehåller dem är privata.

En anslutning startar eller avbryts endast med POST, matchande Origin/Host och en slumpmässig CSRF-token från anslutningssidan. Sidans GET ändrar inte tillstånd. Tillåtna Host är privata/loopback-IP-adresser, `localhost`, `homeassistant` och `.local`-namn. Detta avvisar externa Host-namn/DNS-rebinding och cross-origin-formulär. Använd lokal adress vid ett 403-fel. Anpassad publik proxy/Ingress ingår inte i denna leverans.

Detta är inte full användarautentisering för Home Agent: tjänsten är fortfarande avsedd för betrott lokalt nät, och hela befintliga UI:n ska inte exponeras publikt. Klienthemlighet, refresh-/access-token och Google device code exponeras inte i UI. Google user code och verifieringslänk visas under det aktiva försöket; sidorna är `no-store` med `no-referrer`. Provider-URL måste vara HTTPS på Googles uttryckligen tillåtna värdar och används exakt som mottagen. Google-anrop har fasta endpoint-URL:er, 15 sekunders timeout, 64 KiB svarsgräns och följer inga redirectar.

`/data/google_drive_pairing.json` är privat (0600), begränsad och atomärt sparad. Den innehåller koder endast under det aktiva försöket. Klienthemlighet och tokens sparas inte där. Konfigurationsfingeravtryck och försök-ID förhindrar att sent nätverkssvar, avbrytning eller ändrade inställningar appliceras på fel försök. Den färdiga tokenfilen `/data/chatgpt_drive_oauth.json` är 0600 och kompatibel med befintlig refresh-/publiceringskod. Ingen domändatabas, Source-status eller permanent identitet ändras av autentiseringsflödet.

## Verifiering före och efter leverans

Automatiska syntetiska tester täcker hela Handler-knappflödet till sparad behörighet och befintlig token-refresh, dubbeltryck, omstart, pollningsintervall/backoff, nekande, utgång, fel konto, scope, avbruten nätverksoperation, ändrade inställningar, felaktiga Google-svar, tillståndsfiler, HTML-escaping, CSRF/Origin/Host och omedelbar väckning av publiceringen. Befintliga export-/importtester körs också.

Ägarens riktiga prov:

1. Installera 0.8.6, öppna befintliga rum/Inbox/NIBE-original och kontrollera att äldre funktioner fungerar med tomma Google-inställningar.
2. Utför engångsinställningen och godkänn från telefonen. Kontrollera status under **Mer**, senaste publicering och indexlänken. Verifiera att en originalfil på 11,8 MB öppnas från Drive.
3. Prova att avbryta ett försök före godkännande, att välja fel konto och att starta om under väntan. Inga nya credentials ska registreras efter avbrytning eller för fel konto.
4. Be ChatGPT läsa indexets tid/revision, följa aktuellt NIBE-underlag och ange innehåll från relevant original. Denna verkliga OAuth-/Pi-/Drive-/ChatGPT-kedja är inte verifierad av lokala tester eller CI.

API-underlag: [Google device authorization, inklusive tillåtna scopes](https://developers.google.com/identity/protocols/oauth2/limited-input-device), [konfigurera OAuth-samtycke](https://developers.google.com/workspace/guides/configure-oauth-consent), [Drive-scope](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
