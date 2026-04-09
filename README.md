# sitewalker

Crawl a website and create a structured map of its pages.

## Installation

```bash
pipx install sitewalker
```

## Usage

```bash
# Map all pages on a site (single-level crawl)
sitewalker example.com

# Recursive crawl of all internal pages
sitewalker example.com -r

# Collect external links
sitewalker example.com -e

# Collect external links and check their HTTP status
sitewalker example.com -e --check-external

# Recursive crawl with external link collection
sitewalker example.com -r -e

# Only crawl web pages (skip images, PDFs, etc.)
sitewalker example.com -r -p

# Crawl an HTTP-only site (e.g., LAN staging server)
sitewalker http://staging.lan --allow-private

# Verbose output for debugging
sitewalker example.com -r -v
```

The target accepts a bare domain (`example.com`) or a full URL (`http://example.com`). Bare domains default to HTTPS — if the connection fails, sitewalker exits with a message to provide the full URL.

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-r`, `--recursive` | Recursively crawl internal links | Off |
| `-e`, `--external-links` | Collect external links | Off |
| `--check-external` | Check HTTP status of external links (requires `-e`) | Off |
| `-p`, `--pages` | Only crawl web pages (HTML, PHP, etc.) | Off |
| `-v`, `--verbose` | Enable verbose/debug output | Off |
| `-t`, `--timeout` | Request timeout in seconds | 30 |
| `--max-pages` | Maximum number of pages to crawl | 1000 |
| `--max-depth` | Maximum link distance from start URL (BFS) | 10 |
| `--allow-private` | Allow crawling domains that resolve to private IPs | Off |
| `--ignore-robots` | Ignore robots.txt rules | Off |

## Output

Results are saved to a CSV file named `{domain}_{timestamp}.csv` with columns:

- **URL** — the page URL
- **Title** — the page's `<title>` tag content
- **Status Code** — HTTP response status

When using `-e`, external links are additionally saved to `{domain}_{timestamp}_external_links.csv`. The internal pages CSV is always generated. With `--check-external`, the external links CSV includes a Status Code column.

## Security

- **SSRF protection**: Domains that resolve to private/reserved IP addresses are blocked by default. Use `--allow-private` to override for legitimate internal use.
- **robots.txt**: Respected by default. Use `--ignore-robots` to override.
- **CSV injection**: Output values are sanitized to prevent spreadsheet formula injection.
- **Crawl limits**: Recursive crawls are bounded by `--max-pages` and `--max-depth` to prevent resource exhaustion.

## Roadmap

- `--format json` — JSON output format
- `--images --check-alt` — image inventory with alt text auditing

## License

MIT
