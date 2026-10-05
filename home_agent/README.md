# Home Agent add-on

## 0.3.0

The imported Home Agent snapshot is still read-only, but rooms in the house overview are now clickable.

A room detail page shows:
- room name and floor
- stable room ID
- room-level system references when present
- the complete raw YAML for that room, so we can verify what v013 actually contains before designing richer views

This deliberately avoids inventing relationships between rooms and central systems/assets/documents. Those richer links will be added only after we inspect the real snapshot structure.

Private house data remains in the add-on's local persistent storage and is not committed to GitHub.
