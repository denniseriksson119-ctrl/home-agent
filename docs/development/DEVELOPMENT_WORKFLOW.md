# Home Agent development workflow

This document governs collaboration and delivery. Product behavior remains governed by the active specifications in `docs/README.md`.

## Decision gate
1. Discuss the request first. The assistant proposes scope, behavior, alternatives, risks, version and acceptance tests.
2. Do not create branches, change code/docs, or open PRs before the owner explicitly says **"kör"**. Questions, suggestions and exploration are not authorization to implement.
3. After "kör", proceed autonomously through implementation, review, fixes, automated tests, CI and a merge-ready pull request. Do not stop for routine checkpoints.
4. The owner performs the actual GitHub merge and installs/tests on Raspberry Pi / Home Assistant. Never merge to `main` without explicit authorization.
5. Deliver a clickable PR link, change summary, verified CI status, limitations and a concrete Pi verification checklist. Do not claim Pi verification from CI alone.

## Engineering quality
- Follow the normative architecture, identity/provenance, security, processing, AI and UI contracts. Preserve backwards compatibility and existing user data.
- Keep changes scoped, review edge cases, add regression tests and resolve failures before marking a PR ready.
- Update relevant specs and decision records when behavior or policy changes.
- If a blocker cannot be resolved, state it explicitly rather than claiming merge readiness.

## Versioning and release gate
- Any PR changing installed add-on functionality MUST increment the add-on version in `home_agent/config.yaml` relative to its target branch.
- Use semantic versions (`MAJOR.MINOR.PATCH`); ordinarily increment PATCH for backwards-compatible fixes/features within the current minor series. Choose MINOR/MAJOR deliberately for broader or breaking releases.
- Version changes must be included in the same PR as the add-on change, never deferred to a follow-up PR.
- CI checks this rule on PRs and checks that the version is a valid semantic version. Passing CI is necessary, not proof of deployment stability.
- Documentation-only and CI-only PRs do not need a version increment.
- Check the target branch and version again before delivery; concurrent merges may change the required next version.

## Ownership and feedback
- Assistant: solution proposal, implementation after approval, testing, CI, review, versioning, documentation, PR and merge link.
- Owner: scope approval ("kör"), merge, Pi installation, real-device verification and observed feedback.
- Report defects with reproduction steps; fix through a reviewed PR, respecting the decision gate for new scope.
