#!/usr/bin/env python3

import sys
import argparse
import logging
from datetime import datetime
from pagemap.crawler import WebsiteCrawler


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
        "domain",
        help="Domain to crawl (e.g., example.com)"
    )
    parser.add_argument(
        "-e", "--external-links",
        action="store_true",
        help="Check for external links on the domain"
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
        safe_domain = args.domain.replace('/', '_').replace('\\', '_').replace('..', '_')
        crawler = WebsiteCrawler(args.domain, timeout=args.timeout,
                                  allow_private=args.allow_private,
                                  ignore_robots=args.ignore_robots)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H%M")

        if args.external_links:
            crawler.crawl(
                collect_external=True,
                recursive=args.recursive,
                pages_only=args.pages,
                max_pages=args.max_pages,
                max_depth=args.max_depth
            )
            ext_links_root = "_external_links.csv"
            external_links_file = f"{safe_domain}_{timestamp}{ext_links_root}"
            crawler.save_external_links_results(external_links_file)
            logging.info(f"External links saved to {external_links_file}")
        else:
            crawler.crawl(recursive=args.recursive, pages_only=args.pages,
                         max_pages=args.max_pages, max_depth=args.max_depth)
            output_file = f"{safe_domain}_{timestamp}.csv"
            crawler.save_results(output_file)
            logging.info(f"Crawling complete! Results saved to {output_file}")

        logging.info(f"Total pages crawled: {len(crawler.visited_urls)}")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        sys.exit(1)


# pragma: no cover
if __name__ == "__main__":
    main()
