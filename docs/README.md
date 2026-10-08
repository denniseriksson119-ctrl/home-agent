# Home Agent documentation

This directory contains design and engineering documentation for Home Agent.

## Document hierarchy

1. **Architecture / system specification** — what Home Agent is, its data model and system-level rules.
2. **Workflows** — operational processing rules.
3. **UI specification** — how users interact with the product.
4. **Design decisions** — why important product/design choices were made.
5. **Implementation** — code should conform to the applicable specifications above.

## Versioning policy

Git is the change history for documentation stored in this repository. The imported system specification preserves its original approved snapshot metadata. Current workflow files are imported from the verified Drive Current workflow folder without rewriting their content.

The UI specification starts as a living draft. Stable milestones can later be tagged/released when the design contract is sufficiently mature.

## Development flow

**Idea → discussion/prototype → decision → spec/decision update → implementation → test against spec → PR → merge**

When implementation and specification differ, explicitly decide which should change. Experimental behavior does not automatically become product policy.
