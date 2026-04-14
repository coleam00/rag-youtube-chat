<!--
This PR will be validated by the Dark Factory's independent validator.
Fill in every section. The validator reads this body + the diff + the test
results only — it does not see the coder's scratch notes or implementation
plan (the "holdout principle"). If you don't explain the change here, it
won't be considered.
-->

## Linked issue

<!-- Required. Use one of: Fixes #N, Closes #N, Resolves #N. A PR without a linked issue cannot be validated. -->

Fixes #

## Summary

<!-- One or two sentences: what changed and why. -->

## How this solves the issue

<!-- Explain the causal link between the diff and the reported problem.
     The validator will independently check that `solves_issue: "yes"`. -->

## Test plan

<!-- Every PR must include tests. Bug fixes need a regression test that
     fails on main and passes on this branch. Features need tests for the
     new behavior. List them here. -->

- [ ]
- [ ]

## Agent-browser regression

<!-- Every PR must pass the full end-to-end happy path via agent-browser.
     Confirm you ran it locally (or note that the validator will run it). -->

- [ ] Full happy-path regression passes (sign-in → new conversation → ask question → streaming response → citations → citation modal with embedded player)

## Dependencies

<!-- Fill in ONLY if this PR adds, removes, or upgrades a package. Leave
     blank otherwise. New dependencies require strong justification per
     FACTORY_RULES.md §2. -->

- **Package**:
- **What it does**:
- **Why existing deps don't work**:
- **Maintenance evidence** (recent commits, stars, no known CVEs):

## Governance / protected files

<!-- Confirm the PR does NOT modify any of: MISSION.md, FACTORY_RULES.md,
     CLAUDE.md, .github/**, Dockerfile*, docker-compose*, deploy/**,
     .env*, .archon/config.yaml, rate-limit code, or auth middleware.
     Any PR touching these is auto-rejected. -->

- [ ] No protected files modified
- [ ] PR size is within 500 lines (additions + deletions)
- [ ] No weakening of authentication, authorization, or the 25 msg/day rate limit
