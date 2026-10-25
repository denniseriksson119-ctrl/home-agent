# Changelog

## 0.1.1

- Lås Debian/Node-basen i Dockerfile så att Supervisors BUILD_FROM-argument inte kan välja Alpine.
- Ta bort den äldre build.yaml och kontrollera Debian, apt och Node före paketinstallationen.
- CI bygger på ARM64 och amd64 med avsiktligt motstridigt Alpine-argument och verifierar rätt bas samt tidigare container-/omstartsprov.

## 0.1.0

- Isolerat ARM64/amd64-anslutningsprov med Codex CLI 0.164.0.
- Home Assistant Ingress-sida för ChatGPT-enhetsinloggning, fjärrprocess och manuell parkod.
- Privata, beständiga testfiler/sessioner; ingen montering av Home Agent-data.
- Syntetiska tester och containerprov i CI. Verklig Android-parkoppling återstår.
