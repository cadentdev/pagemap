# Release Checklist: v0.4.0

**Started:** 2026-08-31 | **Project:** sitewalker

## Current Step: 11. Merge & Verify

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
| 11. Merge & Verify | [ ] | |
| --- GATE: CI | [ ] | |
| 12. Tag & GitHub Release | [ ] | |
| 13. Post-Release | [ ] | Verify PyPI shows 0.4.0 (auto via publish.yml) |
| 14. Branch Cleanup | [ ] | |
| 15. Retrospective | [ ] | |
