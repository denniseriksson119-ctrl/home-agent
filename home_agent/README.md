# Home Agent add-on

## Google Drive from a phone (0.8.6)

Configure the Google client in Home Assistant, then open Home Agent → Mer → Anslut Google Drive. Pi displays a code and Google link, and the user approves on the phone. Google Cloud requires a **TVs and Limited Input devices** OAuth client; no desktop script or token-file transfer is needed for this setup path. [Mobile setup and acceptance](https://github.com/denniseriksson119-ctrl/home-agent/blob/main/docs/architecture/GOOGLE_DRIVE_MOBILE_CONNECT.md).

## 0.5.0

Home Agent now has a persistent local SQLite store at `/data/home_agent.db`.

On first start after upgrading, the existing private `/data/home.yaml` snapshot is automatically imported into SQLite. The YAML file is kept unchanged as the bootstrap/source snapshot.

New YAML imports are validated, atomically preserved as `/data/home.yaml`, and imported into SQLite in one local operation.

SQLite contains:
- the complete snapshot text
- an object index for homes, floors, rooms, spaces, systems, components, assets, documents, events, service history, maintenance, projects, costs, suppliers, reminders and open items

The web UI reads its working snapshot from SQLite. Version 0.5 remains read-only: no editing, Drive sync, AI or Home Assistant device integration is added yet.

Private house data stays in the add-on's persistent local storage and is never committed to this repository.

