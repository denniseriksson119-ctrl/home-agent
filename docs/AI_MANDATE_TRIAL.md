# Mandate trial – Home Agent (proposal)

**Active phase:** Experimental software development in a separate Git branch.
**Protected boundaries:** Do not change Drive Data Snapshots/Current, Workflows/Current, accepted YAML, approved workflow versions or user data. The existing reconciliation and approval processes take precedence for any promotion.

## Trial assignment
Inspect current Git repository, select one bounded, testable software improvement that does not require changing protected Drive state; implement it on an isolated branch; run available tests/checks and report artifacts and actual results. Prefer a small import or validation robustness improvement only if supported by code inspection. If blocked by access or missing fixtures, implement safe tests/document the concrete blocker rather than inventing success.

## Pass/fail evidence
Record changed files and commit, test commands/results, whether protected Drive was untouched, and exact next executable step. No promotion to Current or merge without approval. A documentation-only plan does not pass as an implementation.
