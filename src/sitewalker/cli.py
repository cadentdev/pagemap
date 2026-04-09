#!/usr/bin/env python3

import sys
import argparse
import logging
from datetime import datetime
from urllib.parse import urlparse
import requests
from sitewalker.crawler import WebsiteCrawler


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
        "-e", "--external-links",
        action="store_true",
        help="Collect external links found on the domain"
    )
    parser.add_argument(
        "--check-external",
        action="store_true",
        help="Check HTTP status of each external link (requires -e)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively crawl internal links"
    )
    parser.add_argument(
        "-p", "--pages",
        action="store_true",
        help="Only crawl web pages (HTML, PHP, etc.) and skip other file types"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1000,
        help="Maximum number of pages to crawl (default: 1000)"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum crawl depth for recursive mode (default: 10)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0, use 0 for local servers)"
    )
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Allow crawling domains that resolve to private/reserved IPs"
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt rules when crawling"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
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

        # Extract domain for safe filename
        parsed = urlparse(target)
        safe_domain = parsed.netloc.replace('/', '_').replace('\\', '_').replace('..', '_')

        crawler = WebsiteCrawler(target, timeout=args.timeout, delay=args.delay,
                                  allow_private=args.allow_private,
                                  ignore_robots=args.ignore_robots)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H%M")

        crawler.crawl(
            collect_external=args.external_links,
            check_external=args.check_external,
            recursive=args.recursive,
            pages_only=args.pages,
            max_pages=args.max_pages,
            max_depth=args.max_depth
        )

        # Always save internal pages CSV
        output_file = f"{safe_domain}_{timestamp}.csv"
        crawler.save_results(output_file)
        logging.info(f"Crawling complete! Results saved to {output_file}")

        # Additionally save external links CSV when -e is set
        if args.external_links:
            external_links_file = f"{safe_domain}_{timestamp}_external_links.csv"
            crawler.save_external_links_results(external_links_file)
            logging.info(f"External links saved to {external_links_file}")

        logging.info(f"Total pages crawled: {len(crawler.visited_urls)}")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        sys.exit(1)


# pragma: no cover
if __name__ == "__main__":
    main()
