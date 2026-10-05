# Home Agent add-on

## 0.2.0

The add-on now has persistent local storage and can read an existing Home Agent YAML snapshot from:

`/data/home.yaml`

It displays the imported home's floors, rooms, and spaces read-only.

The repository contains no private house data. The YAML snapshot stays in the add-on's local Home Assistant data storage.

Still intentionally excluded: editing, database migration, Drive sync, AI, and Home Assistant device integration.
