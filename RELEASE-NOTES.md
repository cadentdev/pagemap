# Release Notes

## v0.4.0 (2026-08-31)

### Features

- **`Found On` column** — The results CSV now records the page each URL was first discovered on (empty for the start URL). When a link returns 404, this is the page that needs fixing. (#14, part 1)
- **`--output-dir` and `--output-filename` flags** — Choose where CSVs are written and what they're called. `--output-dir` is created on demand and validated before the crawl starts, so a bad path fails fast. `--output-filename NAME` replaces the generated `{domain}_{timestamp}` base; external links go to `NAME_external_links.csv`. The default remains the current directory. (#16)


- **Depth-skipped URLs appear in the output** — URLs discovered beyond `--max-depth` are now rows in the results CSV (title `skipped: max_depth`, empty status, Found On preserved) instead of only a log warning. A malformed link at the depth boundary is no longer invisible. (#14, part 2)
- **`--broken-only` flag** — Prints a summary of all non-200 internal URLs (with the page each was found on) and broken external links to stdout after the crawl, so there's nothing to grep out of the logs. (#14)

- **`-a`/`--assets` flag** — Discovery now optionally extends beyond anchors to `img[src]`, `script[src]`, `link[href]`, `source[src]`, and `srcset`. Assets are fetched for their HTTP status with HEAD (GET fallback on 405, body never downloaded), recorded with `Kind=asset` and an empty title, and never parsed for further links. They are recorded even in non-recursive mode and count toward `--max-pages`. Without `-a` an anchors-only crawl of an image-heavy site can miss most of its URL inventory — the motivating case under-reported a 417-URL site as 95. (#15)

- **Config file** — Persistent settings in `~/.config/sitewalker/config.toml` (TOML, stdlib `tomllib`; honors `$XDG_CONFIG_HOME`, `--config PATH` to point elsewhere, `--no-config` to skip). Two keys: `output_dir` (default output directory) and `page_extensions` (replaces the built-in extension set used by `-p`). Precedence is CLI flags > config file > built-in defaults; unknown keys or wrong types fail loudly before the crawl starts. (#17)

### Fixes

- **Crawl-mode log line no longer overstates scope** — The startup log now states discovery scope (`discovery: anchors` or `anchors+assets`) and filter separately, instead of the misleading "all files", which described the filter while discovery was anchors-only. (#15)
- **Title truncation** — Page titles are capped at 256 characters in the CSV, so a page with a maliciously long `<title>` can't bloat the output. (#9, title half)

- **Stricter output filename sanitization** — Domain-derived filenames now use a character whitelist, strip leading dots/dashes, and are capped at 100 characters, covering NUL bytes, `~`, and very long hostnames. `--output-filename` rejects any path separators or `..`, so user-supplied names cannot escape the output directory. (#9, filename half)

### Infrastructure

- **Automated PyPI publishing** — A `publish.yml` workflow builds and uploads the package to PyPI via Trusted Publishing whenever a GitHub release is published (or on manual dispatch). No API token is stored in the repo.

### Quality

- 120 tests, 97% coverage, bandit clean
- Pre-release security red-team review: no vulnerabilities in the release delta; three pre-existing hardening items filed as #32, #33, #34
- README options table and `--help` regrouped by purpose (#27)

## v0.3.2 (2026-08-29)

### Breaking

- **Minimum Python is now 3.11** (was 3.9). Python 3.9 reached end of life in October 2025 and 3.10 follows in October 2026. `pipx install sitewalker` will refuse to install on older interpreters. CI matrix is now 3.11 and 3.13. (#18)

### Features

- **`--max-external-links` flag** — Caps how many external links `--check-external` will probe (default 500). Previously a site with thousands of external links could take many hours to check. A warning reports how many were skipped. (#6)
- **Per-domain rate limiting for external checks** — External links are checked round-robin across domains, and requests to the same domain are spaced by at least `--domain-delay` seconds (default 5.0), reducing the chance of triggering rate limits or IP blocks. (#7)

### Fixes

- **Bounded BFS queue** — The set of discovered-but-unvisited URLs is now capped at 5× `--max-pages`, preventing unbounded memory growth on sites with dense link graphs. A warning is logged when the cap is hit. (#8)

### Quality

- 56 tests, 97% coverage, bandit clean
- CI verified on Python 3.11 and 3.13

## v0.3.1 (2026-04-09)

### Features

- **`--delay` flag** — Configurable delay between requests (default 1.0s). Use `--delay 0` for local servers where rate limiting isn't needed. Crawling localhost went from ~83 minutes to ~10 minutes for 3305 pages.

### Infrastructure

- **GitHub Actions CI** — Automated pytest + bandit on every push and PR. Python 3.9 and 3.12 matrix. Enforces 95% coverage threshold.

### Quality

- 51 tests, 96% coverage, bandit clean
- CI verified on both Python 3.9 and 3.12

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
