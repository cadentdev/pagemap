# pagemap — Security Audit Remediation Tasks

From the Feature Release security audit conducted 2026-04-03.

---

## P0 — Release Blockers

### [x] Fix broken import path in cli.py

**File:** `src/pagemap/cli.py:7`
**Current:** `from src.pagemap.crawler import WebsiteCrawler`
**Fix:** `from pagemap.crawler import WebsiteCrawler`

The `src.` prefix works when running from the repo root during development, but fails when installed as a package via pip/pipx. The `packages = [{include = "pagemap", from = "src"}]` directive in pyproject.toml means the installed package is `pagemap`, not `src.pagemap`. Any user who installs this tool will get an ImportError on launch.

**Effort:** 1 line change.

---

## P1 — High Priority

### [x] Add request timeout to HTTP calls

**File:** `src/pagemap/crawler.py:151`
**Current:** `response = self.session.get(clean_url)` — no timeout parameter.

A hanging or slow-drip target server will block the crawler indefinitely. The `requests` library has no default timeout — it will wait forever.

**Fix:** Add `timeout=30` (or a configurable value) to `session.get()`. Consider adding a `--timeout` CLI flag with a 30-second default.

**Effort:** 1 line in crawler + optional CLI flag.

---

### [x] Add crawl limits for recursive mode

**File:** `src/pagemap/crawler.py` — `_crawl_page()` method, `crawl()` method.

Recursive crawl has no `max_depth` or `max_pages` limit. A site with 100K+ pages will exhaust memory from the growing `visited_urls` set and `results` list. The 1-second `time.sleep()` delay slows things down but doesn't prevent memory growth. This is especially dangerous on flicky (3.7GB RAM) where large crawls will trigger OOM kills.

**Fix:** Add `--max-pages` (default: 1000) and `--max-depth` (default: 10) CLI flags. Check counters in `_crawl_page()` before recursing.

**Effort:** ~20 lines across cli.py and crawler.py.

---

### [x] Add SSRF protection for domain argument

**File:** `src/pagemap/crawler.py:42` — `__init__()` constructs `https://{domain}` with no validation.

An attacker or careless user could target internal services: `127.0.0.1`, `localhost`, `169.254.169.254` (cloud metadata endpoints), `10.x.x.x`, `192.168.x.x`, or internal hostnames. There is no IP blocklist, no DNS resolution check, and no private network guard.

**Fix:** After resolving the domain to an IP, check against RFC 1918 ranges, loopback, link-local, and cloud metadata IPs. Reject or warn before crawling. Consider a `--allow-private` flag for legitimate internal use.

**Effort:** ~15 lines — a validation function + integration in `__init__()`.

---

## P2 — Medium Priority

### [x] Sanitize CSV output against formula injection

**File:** `src/pagemap/crawler.py:188` — `writer.writerows(self.results)`

Page titles are written directly to CSV with no sanitization. A malicious page title like `=cmd|'/C calc'!A0` or `+cmd|'/C calc'!A0` will execute as a formula when the CSV is opened in Excel or LibreOffice Calc. Since pagemap crawls untrusted websites, this is a realistic attack vector — the malicious payload is set by the target site, not the user.

**Fix:** Prefix any cell value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` with a single quote (`'`). Apply to both `save_results()` and `save_external_links_results()`.

**Effort:** ~5 lines — a sanitize function applied to values before writing.

---

### [x] Sanitize output filename against path traversal

**File:** `src/pagemap/cli.py:71-72`
**Current:** `output_file = f"{args.domain}_{timestamp}.csv"`

The domain argument is used directly in the output filename. If domain is `../../etc/evil`, the file writes outside the intended directory. The URL processing in `__init__()` validates scheme/netloc, but the raw `args.domain` (not the processed URL) is used for filenames in cli.py.

**Fix:** Strip or replace path separators (`/`, `\`, `..`) from the domain before constructing the filename. Consider `args.domain.replace('/', '_').replace('\\', '_')` or use `os.path.basename()`.

**Effort:** ~3 lines.

---

### [x] Add UTF-8 encoding to external links CSV writer

**File:** `src/pagemap/crawler.py:193`
**Current:** `with open(filename, 'w', newline='') as csvfile:` — no encoding specified.

The `save_results()` method (line 185) correctly uses `encoding='utf-8'`, but `save_external_links_results()` does not. On systems where the default encoding is not UTF-8 (e.g., older Windows), this causes data corruption for URLs containing non-ASCII characters.

**Fix:** Add `encoding='utf-8'` to the `open()` call.

**Effort:** 1 line.

---

## P3 — Low Priority

### [x] Add robots.txt compliance (or document omission)

**File:** `src/pagemap/crawler.py` — `crawl()` and `_crawl_page()` methods.

There is no robots.txt fetching or checking. The crawler will visit paths explicitly forbidden by the site owner's robots.txt directives. This is a legal/ethical concern and could result in the crawler being banned by target sites.

**Fix (option A):** Fetch and parse robots.txt before crawling, skip disallowed paths. Python's `urllib.robotparser` handles this natively.
**Fix (option B):** Document in README that robots.txt is not yet respected, and add a `--respect-robots` flag for future implementation.

**Effort:** ~30 lines for option A, or a README edit for option B.

---

### [x] Fix README to match actual implemented features

**File:** `README.md`

The README documents several features that are not yet implemented:
- `--format json` — only CSV output exists
- `--check-links` — not implemented
- `--images --check-alt` — not implemented
- Usage shows `pagemap https://www.example.com` — but CLI takes a bare domain (`example.com`), not a URL

This creates user confusion and sets false expectations. The README appears to have been written for planned features rather than current state.

**Fix:** Rewrite README to document only implemented features. Move planned features to a "Roadmap" section or this TASKS.md file.

**Effort:** Content edit.

---

## Audit Notes

**Clean areas (no issues found):**
- No secrets or credentials in git history (3 commits checked)
- No command injection surface (zero subprocess/exec/eval usage)
- No hardcoded credentials or API keys
- All dependencies current with no known CVEs (beautifulsoup4 4.14.3, requests 2.32.5, urllib3 2.6.3)
- requests.Session redirect limit defaults to 30 — reasonable implicit cap

**Test coverage:** 37 tests, 98% coverage after remediation. Missing lines: cli.py:117 (`if __name__` guard), crawler.py:62 (DNS resolution error path), crawler.py:179 (unreachable branch). All acceptable.
