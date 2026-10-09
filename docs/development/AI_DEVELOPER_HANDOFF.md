# Home Agent — developer chat handoff

**Start here when a new chat takes over development.** Read `docs/README.md`, `docs/development/DEVELOPMENT_WORKFLOW.md` and the active specifications it lists before suggesting code changes.

## Mandatory operating rules
- Respond in Swedish to the owner.
- Discuss design and offer a recommendation first. Wait for the explicit **"kör"** before any repository changes, including documentation and CI.
- After approval, work without routine pauses until the PR is tested and merge-ready. Do not merge `main`; the owner does that.
- For installed add-on code changes, bump `home_agent/config.yaml` in the same PR and pass the version CI guard.
- Deliver a clickable GitHub PR URL, verified CI status and practical Home Assistant/Raspberry Pi test instructions.
- The owner performs installation and Pi verification; never imply this was done remotely.
- Preserve local-first behavior, original evidence, data identity and backward compatibility. Never pretend unimplemented AI features exist.

## Reconstruct current state; do not assume it
1. Inspect `main`, open PRs, latest CI, and `home_agent/config.yaml` before proposing a release number.
2. Read applicable active specs and recent design decisions.
3. Confirm the owner's requested scope and whether "kör" has been given **for this change**.
4. After work, report actual GitHub status and outstanding Pi checks. A new chat must not assume earlier CI runs cover newer commits.

This handoff documents standing collaboration rules, **not** permission to start work on a new request.
