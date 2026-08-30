# Release Checklist: v0.3.2

**Started:** 2026-08-29 | **Project:** sitewalker

## Current Step: COMPLETE

| Step | Status | Notes |
|------|--------|-------|
| Pre-flight | [x] | 3 issues (#6, #7, #8) + Python floor (#18), target v0.3.2 |
| 1. Security Audit | [x] | No new network surface; limits only reduce exposure |
| 2. Triage Findings | [x] | Nothing to triage |
| 3. Fix Blockers | [x] | None needed |
| --- GATE: Security | [x] | PASS |
| 4. Test Coverage | [x] | 56 tests, 97% coverage |
| --- GATE: Quality | [x] | PASS |
| 5. Dependency Audit | [x] | bandit clean, no new runtime deps; lock regenerated for ^3.11 |
| 6. Documentation Final Pass | [x] | README: Requirements section, 2 new flags in options table |
| 7. Version Bump | [x] | 0.3.1 → 0.3.2 |
| 8. Release Notes | [x] | Unreleased → v0.3.2 |
| 9. PR Creation/Update | [x] | PR #22 |
| 10. Issue Triage | [x] | #6, #7, #8, #18 closed by PRs; #9, #14–#17 stay open (v0.4.0 plan) |
| 11. Merge & Verify | [x] | CI green on 3.11 + 3.13 |
| --- GATE: CI | [x] | PASS |
| 12. Tag & GitHub Release | [x] | v0.3.2 tagged and released |
| 13. Post-Release | [x] | PyPI 0.3.2 verified — published via publish.yml (Trusted Publishing, PR #24) |
| 14. Branch Cleanup | [x] | 4 branches pruned (remotes auto-deleted on merge) |
| 15. Retrospective | [x] | See below |

## Retrospective

### What went well
- Four PRs (#19, #20, #21, #22) from issue review to release in two days; every PR carried its own tests, README row, and release-notes entry, so the release PR was a heading rename and a version bump.
- Introduced a `## Unreleased` section in RELEASE-NOTES.md — notes are written with the change, not reconstructed at release time. Adopted as the ongoing convention.
- Batching #6/#7/#8 into one PR worked: they touch ~40 adjacent lines and share one test setup.

### What could improve
- The Breaking entry (#18) ended up below Features after #21 merged; the release PR had to reorder it. Convention going forward: Breaking is always the first subsection under Unreleased.
- Shipping a Python-floor bump as a patch release is a judgement call; noted first in the release notes to compensate.

### Process note
- Order matters for the next batch: the results-model refactor (#14 Found-On column) must land before #15 asset discovery, and #8's queue cap (shipped here) was a prerequisite for #15.
