# Utveckla Home Agent från Codex på Pi

Denna fil beskriver arbetsmiljön från Codex Remote Test 0.1.6. Börja med:

```sh
python3 /app/development.py --check
```

Kontrollen visar installerade verktyg och provar en tillfällig venv. Den läser
inga credentials och ändrar ingen konfiguration eller husdata.

## Förbered projektet

Arbetskatalog för kod: `/data/workspace/projects/home-agent`.
Källkod: `https://github.com/denniseriksson119-ctrl/home-agent.git`.

Om katalogen saknas får Codex hämta projektet där med Git. Klona inte ovanpå en
befintlig katalog. Om projektet finns: kontrollera arbetsgren, remote och lokala
ändringar först. Skriv inte över arbete, gör inga reset/clean och byt inte gren
över osparade ändringar. Redovisa aktuell revision innan ny utveckling.

Hämta aktuell main när det är säkert. Läs docs/README.md,
docs/development/AI_DEVELOPER_HANDOFF.md och docs/development/DEVELOPMENT_WORKFLOW.md.
Använd en arbetsgren för ägarens godkända uppgift. Auto-clone eller git pull körs
inte vid start av tillägget; nätåtkomst och verkligt kodarbete sker i konversationen.

## Verktyg och tester

Git, rg, Python 3, PyYAML 6, venv, Node 22/npm, Codex CLI 0.164.0 och
pdftotext/pdftoppm ingår i tillägget. Debian Bookworm använder Python 3.11;
release-CI kör även Python 3.12. Använd faktisk version från verktygskontrollen
och ange den när du redovisar tester. CI provar hela projektets tester i samma
ARM64-/amd64-image som Pi-tillägget.

Från projektets rot:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s home_agent/rootfs/opt/home-agent -p 'test_*.py' -v
python3 -m py_compile home_agent/rootfs/opt/home-agent/*.py codex_remote_test/app/*.py
```

Testerna använder syntetiska data, inte den körande husdatabasen. Vid extra
Python-beroenden kan en projektspecifik miljö skapas:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip --version
```

Använd `.venv/bin/python` för den miljön. Kontrollera .gitignore innan du skapar
en venv så att den inte kan hamna i Git. Systempaket uppdateras genom en PR och
ny tilläggsversion, inte genom root/apt-kommandon i den körande containern.

GitHub-/Drive-verktygen har verifierats av ägaren i Pi-sessionen. Använd dessa
anslutningar där de fungerar. Git CLI och anslutna GitHub-verktyg är separata
autentiseringsvägar; skapa inte ett nytt tokenflöde enbart för att git push nekas.
Använd ägarens faktiska författaridentitet vid lokala commits, inte en påhittad
produktionsidentitet. Publicera branch/PR via de anslutna verktygen om lämpligt.

Containerbyggen och tester på flera arkitekturer görs i GitHub Actions. Tillgång
till host-Docker eller HA/Supervisor behövs inte. Kontrollera CI på aktuell
PR-revision och lämna länk. Ägaren mergar och installerar tillägget.

## Husdata och nästa uppgift

Home Agent-läsverktygen ger aktuella uppgifter och kopplade original i sitt
begränsade scope. Filer under `/data/workspace/home-agent-sources` är privata
arbetskopior och ska aldrig flyttas in i kodrepot. GitHub innehåller ingen riktig
husdatabas, originalsamling eller fullständig backup.

Nästa planerade produktuppgift är inventering/migration av äldre material.
Läs backlog och fråga efter det aktuella uppdraget. Börja med inventering och
en förhandsgranskad plan: vad är redan registrerat, vad finns som original,
vilka kopplingar saknas och vilka ID:n ska bevaras? Inga databasskrivningar,
omlänkningar, Drive-ändringar eller massimporter ingår bara för att utveckling
nu är möjlig.
