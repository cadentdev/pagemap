# Release Notes

## v0.3.0 (2026-04-09)

Three features and two security fixes addressing all four open issues.

### Features

- **BFS crawl algorithm** — Replaced depth-first search with breadth-first search. `--max-depth` now reflects the true shortest link distance from the start URL, ensuring all reachable pages are found regardless of site structure. Previously, cross-links between pages caused DFS to burn through the depth budget on a single chain, missing pages that were logically close to the start. (#1)

- **External link status checking** — New `--check-external` flag (used with `-e`) sends HEAD requests to each external link and includes HTTP status codes in the external links CSV. Falls back to GET on 405 responses. Rate-limited to 1 request per second with a 10-second timeout. (#2)

- **CSV output fixes** — The `-e` flag now saves both the internal pages CSV and the external links CSV. Previously, using `-e` skipped the internal pages file entirely. CSV output also uses Unix line endings (`\n`) instead of Windows-style `\r\n`, fixing silent data corruption when piping to CLI tools. (#3, #4)

### Security

- Fixed crash on pages with empty `<title></title>` tags (`AttributeError` on `None.strip()`)
- User-Agent version string now reads from package metadata instead of a hardcoded value

### Quality

- 51 tests, 96% coverage
- bandit clean (0 findings)
- BFS regression test proves the DFS bug and prevents re-introduction

## v0.2.1 (2026-04-05)

- Warn when `--max-depth` causes skipped pages during crawl

## v0.2.0 (2026-04-05)

- Renamed package from pagemap to sitewalker for PyPI availability

## v0.1.1 (2026-04-03)

- Accept full URLs or bare domains as input
- Add robots.txt compliance
- Rewrite README for accuracy

## v0.1.0 (2026-04-03)

- Initial release: recursive website crawling with CSV output
- SSRF protection, CSV injection sanitization, crawl limits
