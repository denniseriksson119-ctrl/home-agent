# Home Agent add-on

## 0.4.0

Room pages now resolve relationships already present in the imported snapshot.

The pilot is Kök + matplats, but the resolver is generic. It follows only explicit references from the room and related_object_refs in the snapshot.

The room page can show features, systems, assets, components, documents, history, service, maintenance and costs when those relationships are explicitly stored.

No relationships are inferred from names or from expected house topology. Raw room YAML remains available for verification.

The imported snapshot remains read-only and private in the add-on's persistent local storage.
