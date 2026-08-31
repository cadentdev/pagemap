#!/usr/bin/env python3

import sys
import os
import re
import argparse
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
from sitewalker.crawler import WebsiteCrawler
from sitewalker.config import load_config, default_config_path


# Filename components: keep letters, digits, dot, dash; everything else -> "_"
_UNSAFE_CHARS = re.compile(r'[^A-Za-z0-9.-]+')
MAX_FILENAME_COMPONENT = 100


def sanitize_filename_component(value: str) -> str:
    """Reduce an arbitrary string (e.g. a hostname) to a safe filename fragment.

    Whitelists characters, strips leading dots/dashes (no hidden files, no
    option-like names), and caps length so long hostnames can't produce
    filesystem errors.
    """
    value = os.path.basename(value)
    value = _UNSAFE_CHARS.sub('_', value).strip('._-')
    return value[:MAX_FILENAME_COMPONENT] or 'site'


def resolve_output_paths(output_dir: str | None, output_filename: str | None,
                         domain: str, timestamp: str) -> tuple[Path, Path]:
    """Return (results_csv, external_links_csv) paths.

    Precedence: --output-filename > --output-dir > current directory.
    --output-filename must be a bare filename; the directory always comes
    from --output-dir (or the CWD), so there is no path-traversal surface.
    Creates --output-dir if missing; raises ValueError on a bad directory
    or filename.
    """
    base_dir = Path(output_dir) if output_dir else Path.cwd()
    if base_dir.exists() and not base_dir.is_dir():
        raise ValueError(f"Output path exists but is not a directory: {base_dir}")
    base_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(base_dir, os.W_OK):
        raise ValueError(f"Output directory is not writable: {base_dir}")

    if output_filename:
        if (os.path.isabs(output_filename) or '/' in output_filename
                or '\\' in output_filename or '..' in output_filename):
            raise ValueError(
                f"--output-filename must be a bare filename, not a path: {output_filename!r} "
                f"(use --output-dir to choose the directory)"
            )
        stem = output_filename[:-4] if output_filename.lower().endswith('.csv') else output_filename
        if not stem:
            raise ValueError("--output-filename must not be empty")
    else:
        stem = f"{sanitize_filename_component(domain)}_{timestamp}"

    return base_dir / f"{stem}.csv", base_dir / f"{stem}_external_links.csv"


def print_broken_summary(crawler) -> None:
    """Print non-200 results to stdout for quick triage (--broken-only)."""
    broken = [r for r in crawler.results if r.status is not None and r.status != 200]
    broken_external = [(url, status) for url, status in crawler.external_links_checked
                       if status != 200]
    if not broken and not broken_external:
        print("No broken links found.")
        return
    if broken:
        print(f"Broken internal links ({len(broken)}):")
        for r in sorted(broken, key=lambda r: r.url):
            print(f"  {r.status}  {r.url}  (found on: {r.found_on or '-'})")
    if broken_external:
        print(f"Broken external links ({len(broken_external)}):")
        for url, status in sorted(broken_external):
            print(f"  {status}  {url}")


def setup_logging(verbose: bool):
    """Configure logging based on verbosity level."""
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if verbose:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)


def main():
    """Main function to run the crawler."""
    parser = argparse.ArgumentParser(
        description="Crawl a website and create a structured map of its pages"
    )
    parser.add_argument(
        "target",
        help="Domain or URL to crawl (e.g., example.com or http://example.com)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    scope = parser.add_argument_group("crawl scope")
    scope.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively crawl internal links"
    )
    scope.add_argument(
        "-a", "--assets",
        action="store_true",
        help="Also discover and record img/script/link/source assets "
             "(fetched for status via HEAD, never parsed; counts toward --max-pages)"
    )
    scope.add_argument(
        "-p", "--pages",
        action="store_true",
        help="Only crawl web pages (HTML, PHP, etc.) and skip other file types"
    )
    scope.add_argument(
        "--max-pages",
        type=int,
        default=1000,
        help="Maximum number of pages to crawl (default: 1000)"
    )
    scope.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum crawl depth for recursive mode (default: 10)"
    )

    external = parser.add_argument_group("external links")
    external.add_argument(
        "-e", "--external-links",
        action="store_true",
        help="Collect external links found on the domain"
    )
    external.add_argument(
        "--check-external",
        action="store_true",
        help="Check HTTP status of each external link (requires -e)"
    )
    external.add_argument(
        "--max-external-links",
        type=int,
        default=500,
        help="Maximum number of external links to check with --check-external (default: 500)"
    )
    external.add_argument(
        "--domain-delay",
        type=float,
        default=5.0,
        help="Minimum seconds between requests to the same external domain (default: 5.0)"
    )

    output = parser.add_argument_group("output")
    output.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Directory to write CSV files to (created if missing; default: current directory)"
    )
    output.add_argument(
        "--output-filename",
        metavar="NAME",
        help="Base name for output files instead of {domain}_{timestamp}; "
             "external links go to NAME_external_links.csv"
    )
    output.add_argument(
        "--broken-only",
        action="store_true",
        help="Print a summary of non-200 URLs to stdout after the crawl"
    )

    requests_group = parser.add_argument_group("requests")
    requests_group.add_argument(
        "-t", "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    requests_group.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0, use 0 for local servers)"
    )

    config_group = parser.add_argument_group("configuration")
    config_group.add_argument(
        "--config",
        metavar="PATH",
        help=f"Config file to load (default: {default_config_path()})"
    )
    config_group.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore any config file"
    )

    safety = parser.add_argument_group("safety overrides")
    safety.add_argument(
        "--allow-private",
        action="store_true",
        help="Allow crawling domains that resolve to private/reserved IPs"
    )
    safety.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt rules when crawling"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        # Precedence: CLI flags > config file > built-in defaults
        config = {} if args.no_config else load_config(args.config)
        output_dir = args.output_dir if args.output_dir is not None else config.get('output_dir')

        target = args.target
        parsed = urlparse(target)

        # If bare domain (no scheme), probe HTTPS first
        if parsed.scheme not in ('http', 'https'):
            probe_url = f"https://{target}"
            try:
                requests.head(probe_url, timeout=5, allow_redirects=True)
                target = probe_url
            except requests.ConnectionError:
                logging.error(
                    f"Could not connect to {probe_url}\n"
                    f"If this site uses HTTP, provide the full URL:\n"
                    f"  sitewalker http://{target}"
                )
                sys.exit(1)

        parsed = urlparse(target)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H%M")
        # Resolve (and validate) output paths before crawling, so a bad
        # --output-dir fails fast instead of after a long crawl.
        output_file, external_links_file = resolve_output_paths(
            output_dir, args.output_filename, parsed.netloc, timestamp)

        crawler = WebsiteCrawler(target, timeout=args.timeout, delay=args.delay,
                                  allow_private=args.allow_private,
                                  ignore_robots=args.ignore_robots,
                                  domain_delay=args.domain_delay,
                                  page_extensions=config.get('page_extensions'))

        crawler.crawl(
            collect_external=args.external_links,
            check_external=args.check_external,
            recursive=args.recursive,
            pages_only=args.pages,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            max_external_links=args.max_external_links,
            include_assets=args.assets
        )

        # Always save internal pages CSV
        crawler.save_results(str(output_file))
        logging.info(f"Crawling complete! Results saved to {output_file}")

        # Additionally save external links CSV when -e is set
        if args.external_links:
            crawler.save_external_links_results(str(external_links_file))
            logging.info(f"External links saved to {external_links_file}")

        logging.info(f"Total pages crawled: {len(crawler.visited_urls)}")

        if args.broken_only:
            print_broken_summary(crawler)

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        sys.exit(1)


# pragma: no cover
if __name__ == "__main__":
    main()
