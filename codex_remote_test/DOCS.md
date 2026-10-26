# Installera och prova Codex från mobilen

## Förutsättningar

- Home Assistant OS, ARM64 eller amd64, med samma tilläggsrepo som Home Agent.
- Uppdaterad ChatGPT-app på telefonen och Codex-åtkomst på ditt ChatGPT-konto.
- Internet från Pi:n för OpenAI-inloggning, fjärranslutning och modellåtkomst.
- Tillgängligt diskutrymme och RAM för Node, Codex och de kommandon du vill köra. Ingen språkmodell körs lokalt. Faktisk Pi-belastning ska mätas vid provet.

Du behöver inte installera via SSH eller ändra Home Assistant OS. Ingen Google
Cloud-/Drive-inställning hör till detta anslutningsprov.

## Installera från telefonen

1. Merga PR:n som lägger till **Codex Remote Test** i GitHub.
2. I Home Assistant: **Inställningar → Appar/Tillägg → Installera app/Tilläggsbutik**.
3. Välj menyn **⋮ → Sök efter uppdateringar/Check for updates** om det behövs.
4. Leta efter det separata tillägget **Codex Remote Test**, version **0.1.3**, och installera eller uppdatera.
   Detta är en ny app, inte en uppdatering av Home Agent 0.8.6.
5. Starta tillägget och tryck **Öppna webbgränssnitt**. Ingen port ska konfigureras eller öppnas i routern.
6. Vänta tills sidan visar **Codex 0.164.0**. Inga optionsfält behöver fyllas i.

Första installationen bygger en container och kan ta tid på Pi. Vid byggfel behövs
byggloggen från detta tillägg, inte Home Assistant Core-loggen. Dela inte inloggningskoder, parkoder eller privata backupfiler i felrapporter.

### Om installationen av 0.1.0 misslyckades

Version 0.1.1 använder en uttrycklig Debian/Node-bas som inte kan bytas genom
Supervisors `BUILD_FROM`-argument. 0.1.0 kunde byggas mot en Alpine-bas i ägarens
installation; då kördes `apt-get` med `/bin/ash` och bygget stoppade med exitkod 127.
CI provar nu ett avsiktligt motstridigt Alpine-argument på både ARM64 och amd64
och kontrollerar att den färdiga imagen ändå innehåller Debian, apt och Node.

Efter merge: uppdatera tilläggsbutiken, kontrollera att **0.1.1** visas och försök
installera igen. Om tillägget redan är installerat väljer du uppdatering till
0.1.1. Ingen ominstallation av Home Assistant eller ändring av Home Agent behövs.

## 1. Logga in

1. Vänta på kontrollen av sparad inloggning. Om **ChatGPT inloggat** visas: gå direkt till steg 2, Anslut mobilen. Starta inte en ny inloggning.
2. Om **Inloggningsstatus okänd** visas: tryck **Kontrollera sparad inloggning**. Ett kontrollfel betyder inte att credentials saknas. Under **Diagnostik utan hemligheter** visas om inloggningsfilen finns, senaste kontroll och när tillägget startade; inga filinnehåll eller tokens visas.
3. Endast när **Inte inloggad** visas: tryck **Hämta inloggningskod**.
4. Anteckna/kopiera koden som visas och tryck **Öppna OpenAI-inloggning**.
5. Logga in med **samma ChatGPT-konto och workspace som i mobilappen**, ange koden och godkänn.
   Detta är inte ditt Google-/Drive-konto.
6. Återvänd till Home Assistant-sidan. Den ska visa **ChatGPT inloggat**.

Från 0.1.2 kontrolleras sparad auth även när sidan öppnas på nytt. UI och backend
spärrar ny enhetsinloggning när en sparad ChatGPT-inloggning hittas, också om
webbsidans tidigare status var gammal. Codex 0.164.0 rensar/revokerar befintlig
auth innan en ny device-login startas; därför får knappen inte användas som en
statuskontroll. Funktionen **Kontrollera sparad inloggning** startar ingen sådan
inloggning och visar aldrig råa CLI-utdata. Kontrollen visar vad CLI:n hittar i
sin credential-cache, inte att OpenAI precis har godkänt ett modell-/fjärranrop.

Vid uppdatering från 0.1.1: installera 0.1.2, öppna sidan och kontrollera sparad
inloggning först. Uppdateringen skriver inte över auth.json eller testfiler.
Om credentials redan hunnit rensas av ett tidigare nytt inloggningsförsök kan
de inte återskapas av uppdateringen; då behövs en ny inloggning efter kontrollen.

Om OpenAI begär att enhetsinloggning ska aktiveras: följ kontots säkerhetsinställningar
och försök igen. Om en kod hinner gå ut: avbryt försöket och hämta en ny.
Avbrytning stoppar försöket men återkallar inte credentials som OpenAI redan hunnit spara.

## 2. Prova parkoppling

1. Tryck **Starta fjärranslutning** om den inte redan startats automatiskt. Vänta tills status säger **Ansluten till OpenAI**. En startad process räcker inte; knappen för parkod aktiveras när anslutningen är klar.
2. Tryck **Skapa parkod**. En tidsbegränsad manuell kod visas om CLI/konto stöder detta.
3. Öppna ChatGPT-appens **Remote / Codex**, välj att lägga till en anslutning och
   använd koden **om appen erbjuder manuell kodinmatning**.
4. Kontrollera att enheten går att välja och att du kan öppna eller skapa en Codex-konversation på den.
5. Välj **/data/workspace** som projektmapp om appen frågar efter projekt.

Version 0.1.3 använder samma privata Codex app-server för anslutningsstatus och
parkod, via en Unix-socket inne i containern. Ingen TCP-port öppnas för servern.
Tidigare versioner blandade förgrundsprocessen med ett parkodskommando som sökte
en separat bakgrundsserver. Felmeddelandet om kontots fjärrstöd kunde därför vara
missvisande. Uppdatera till 0.1.3 och återanvänd den sparade inloggningen.

Vänteläge och eventuella säkra felkoder visas direkt vid parkodsknappen. Om
anslutningen visar fel: stoppa och starta fjärranslutningen igen. En parkod som
inte kan skapas är inte i sig bevis för att kontot saknar stöd; starta ingen ny
enhetsinloggning enbart på grund av ett sådant fel.

**Viktig provgräns:** Den offentliga mobilguiden beskriver fortfarande parkoppling via
en Mac-/Windows-app. Codex fjärrprotokoll och manuella parkoder är experimentella.
Om mobilen bara erbjuder QR-skanning, kräver en datorapp eller inte visar enheten:
stanna där och rapportera exakt vad som visas. En igångvarande process och skapad
parkod bevisar inte en lyckad eller stödd direkt mobilanslutning. Exponera inte en
egen app-server-port som genväg.

## 3. Verifiera åtkomst och session

Skicka i den anslutna Codex-konversationen:

> Läs README.md i /data/workspace och återge testmarkören. Skapa sedan session-test.txt med en kort anteckning om att anslutningen fungerar.

Godkänt resultat:
- Svaret innehåller **CODEX_PI_TEST_OK** från filen, inte bara från denna guide.
- Codex kan skapa och sedan läsa **session-test.txt** i testmappen med normala godkännanden.
- Telefonen kan skicka ett uppföljande meddelande till samma konversation.

## 4. Prova omstart

1. Vänta tills Codex är klar med pågående arbete.
2. Starta om **Codex Remote Test** från Home Assistant.
3. Öppna installationssidan och verifiera sparad ChatGPT-inloggning samt återstartad fjärrprocess.
4. Öppna samma anslutning/konversation i mobilen och be Codex läsa **session-test.txt**.
5. Kontrollera både sparad fil och att konversationshistoriken går att återuppta. Persistenta filer är inte i sig bevis på återansluten konversation.

En ny parkod kan behövas om OpenAI återkallat anslutningen. UI-koder sparas inte
över omstart; de är kortlivade. Inloggning, CLI-historik och testfiler finns i
tilläggets egen **/data** tills tilläggets data tas bort.

## Stoppa provet

**Stoppa fjärranslutning** stoppar Codex fjärrprocess och stänger av dess automatiska
återstart inom tillägget. Testfiler, historik och sparad inloggning raderas inte.
Detta är inte ett löfte om återkallade enhetsparningar i OpenAI-kontot; hantera
kontots anslutningar/säkerhet separat när du vill återkalla åtkomst.

Tilläggets **Starta vid systemstart** är från början avstängt. Håll det avstängt
under provet. Home Agent fortsätter vara ett separat tillägg.

## Säkerhet och avgränsning

- Endast Home Assistant Ingress, ingen publicerad host-port eller godtycklig terminalendpoint.
- Lokal styrning sker över samma privata Unix/WebSocket-anslutning till app-servern för start, status och parkod. Endast tre fasta fjärrmetoder används, utan användarstyrd metod eller adress.
- Processerna körs som UID 10001 efter förberedelse av tilläggets privata kataloger.
- Inga host-/Docker-/Supervisor-/Home Assistant-API-behörigheter eller delade datamappningar begärs.
- Codex får normal workspace-sandbox och on-request-godkännanden, inga bypass-flaggor.
- Kontohemligheter ligger hos CLI i privat /data/home/.codex. Inga tokens eller råa providersvar visas i UI/loggar. Kortlivade användar-/parkoder visas bara i den autentiserade setup-sidan.
- Sessions- och workspace-data innehåller det du ger Codex. Home Assistant-backuper som omfattar tillägget måste därför hanteras som privata, inklusive credentials.
- Containern har nätåtkomst för OpenAI. Separat container innebär inte att nätåtkomst till alla andra LAN-tjänster är tekniskt spärrad. Inga Home Agent-integrationer är konfigurerade eller godkända genom detta prov.
- CI kan verifiera container/CLI och syntetiska flöden. Pi-resurser, sandbox under HA:s AppArmor, verklig OpenAI-inloggning, Android-UI, parkoppling och konversationsåterupptagning kräver detta verkliga prov.
- CI provar även initialize, statusläsning och nekad parkod mot samma riktiga CLI-server över Unix/WebSocket, utan nätverk eller aktiverad OpenAI-reläanslutning. Det verifierar det lokala protokollet, inte kontots fjärrbehörighet.

## Underlag

- [Codex fjärrkommandon](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
- [Codex autentisering](https://learn.chatgpt.com/docs/auth)
- [Dokumenterat mobil-/SSH-flöde](https://learn.chatgpt.com/docs/remote-connections)
- [Home Assistant-appar](https://contributors.home-assistant.io/apps/first-app/)
