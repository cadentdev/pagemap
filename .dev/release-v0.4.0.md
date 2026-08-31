# Release Checklist: v0.4.0

**Started:** 2026-08-31 | **Project:** sitewalker

## Current Step: COMPLETE

| Step | Status | Notes |
|------|--------|-------|
| Pre-flight | [x] | 5 issues (#9, #14, #15, #16, #17) + #27 docs, target v0.4.0 |
| 1. Security Audit | [x] | Full red-team review of v0.3.2..main: 0 findings; 3 pre-existing hardening items filed (#32, #33, #34) |
| 2. Triage Findings | [x] | #32/#33 target v0.4.1; #34 hygiene |
| 3. Fix Blockers | [x] | None — nothing in the release delta |
| --- GATE: Security | [x] | PASS |
| 4. Test Coverage | [x] | 120 tests, 97% coverage |
| --- GATE: Quality | [x] | PASS |
| 5. Dependency Audit | [x] | bandit clean; no new runtime deps (config uses stdlib tomllib) |
| 6. Documentation Final Pass | [x] | Docs audit PR #35; options table + --help regrouped (#27) |
| 7. Version Bump | [x] | 0.3.2 → 0.4.0 |
| 8. Release Notes | [x] | Unreleased → v0.4.0 |
| 9. PR Creation/Update | [x] | PR #36 |
| 10. Issue Triage | [x] | #9, #14–#17, #27 closed by PRs; #32–#34 open for v0.4.1 |
| 11. Merge & Verify | [x] | CI green on 3.11 + 3.13 |
| --- GATE: CI | [x] | PASS |
| 12. Tag & GitHub Release | [x] | v0.4.0 tagged and released |
| 13. Post-Release | [x] | PyPI 0.4.0 verified — release-trigger run blocked by pypi environment protection (tag refs not allowed); published via workflow_dispatch from main |
| 14. Branch Cleanup | [x] | Locals pruned; remotes auto-deleted on merge |
| 15. Retrospective | [x] | See below |

## Retrospective

### What went well
- Nine PRs (#26, #28–#31, #35, #36 + two v0.3.2-era) took the tracker from 9 open issues to 0 feature issues across two releases; every PR carried its own tests, docs, and Unreleased entry, so both release PRs were a heading rename and a version bump.
- Pre-release security red-team review (two identification passes + adversarial verification) found zero vulnerabilities in the delta and produced three well-scoped hardening issues (#32–#34) for v0.4.1.
- Stacking #31 on #30 kept config-file work moving while assets was in review; GitHub retargeted cleanly on merge.
- First release through automated PyPI Trusted Publishing — attestations generated, no tokens anywhere.

### What could improve
- The `release: published` trigger deploys from the tag ref, and the pypi environment's protection rules only allow `main` — the automatic publish failed and needed a manual `workflow_dispatch` from main. **Fix before v0.4.1: add a `v*` tag rule to the pypi environment's deployment policy.**
- The security review's first pass ran against a stale local main (PRs merged on GitHub but not pulled); the agent caught the discrepancy. Pull before any review of "current" state.
- Stacked PRs get no CI until retargeted to main — fine, but worth remembering that green must be re-verified after retarget.

### Process note
- A --assets crawl counts assets toward --max-pages; release notes call this out, but watch for user reports of "truncated" inventories on image-heavy sites with default limits.
