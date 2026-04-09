# Release Checklist: v0.3.0

**Started:** 2026-04-09 | **Project:** sitewalker

## Current Step: 1 — Security Audit

| Step | Status | Notes |
|------|--------|-------|
| Pre-flight | [x] | 3 features inventoried, target v0.3.0 |
| 1. Security Audit | [ ] | |
| 2. Triage Findings | [ ] | |
| 3. Fix Blockers | [ ] | |
| --- GATE: Security | [ ] | |
| 4. Test Coverage | [ ] | |
| --- GATE: Quality | [ ] | |
| 5. Dependency Audit | [ ] | |
| 6. Documentation Final Pass | [ ] | |
| 7. Version Bump | [ ] | |
| 8. Release Notes | [ ] | |
| 9. PR Creation/Update | [ ] | |
| 10. Issue Triage | [ ] | |
| 11. Merge & Verify | [ ] | |
| --- GATE: CI | [ ] | |
| 12. Tag & GitHub Release | [ ] | |
| 13. Post-Release | [ ] | |
| 14. Branch Cleanup | [ ] | |
| 15. Retrospective | [ ] | |

## Features Included

- CSV output fixes (issues #3, #4) — save both files with -e, Unix line endings
- BFS crawl algorithm (issue #1) — replaces DFS, correct depth tracking
- External link status checking (issue #2) — new --check-external flag

## Findings

<!-- Security audit findings logged here -->

## Detours

<!-- Log unplanned work that happened between steps -->
