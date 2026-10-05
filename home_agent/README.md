# Home Agent add-on

## 0.2.1

The web interface can import an existing Home Agent YAML snapshot.

The upload is validated before it replaces the local snapshot. A valid snapshot must use `schema: home_agent` and contain at least one home. The file is stored privately as `/data/home.yaml` in the add-on's persistent local storage.

The imported structure is displayed read-only: home, floors, rooms, and spaces.

Private house data is not stored in this public repository.

Still intentionally excluded: editing, database migration, Drive sync, AI, and Home Assistant device integration.
