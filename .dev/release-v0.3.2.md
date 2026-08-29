# Release Checklist: v0.3.2

**Started:** 2026-08-29 | **Project:** sitewalker

## Current Step: 11. Merge & Verify

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
| 11. Merge & Verify | [ ] | |
| --- GATE: CI | [ ] | |
| 12. Tag & GitHub Release | [ ] | |
| 13. Post-Release | [ ] | PyPI publish |
| 14. Branch Cleanup | [ ] | |
| 15. Retrospective | [ ] | |
