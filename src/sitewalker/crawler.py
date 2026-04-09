#!/usr/bin/env python3

import csv
import ipaddress
import socket
from collections import deque
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from typing import Set, List, Tuple
import time
import logging

logger = logging.getLogger(__name__)

# List of file extensions that are considered web pages
PAGE_EXTENSIONS = {
    '', # for URLs ending in '/'
    'html',
    'htm',
    'php',
    'asp',
    'aspx',
    'jsp',
    'shtml',
    'phtml',
    'xhtml',
    'jspx',
    'do',
    'cfm',
    'cgi'
}

class URLProcessingError(Exception):
    """Custom exception for URL processing errors"""
    pass

class CrawlingError(Exception):
    """Custom exception for crawling errors"""
    pass

class SSRFProtectionError(Exception):
    """Raised when a domain resolves to a private/reserved IP address."""
    pass


def validate_domain_ssrf(domain: str) -> None:
    """Check that a domain does not resolve to a private or reserved IP.

    Raises SSRFProtectionError if the domain resolves to loopback,
    private, link-local, or reserved address ranges.
    """
    try:
        results = socket.getaddrinfo(domain, None)
        for family, _, _, _, sockaddr in results:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise SSRFProtectionError(
                    f"Domain '{domain}' resolves to private/reserved IP {ip}. "
                    f"Use --allow-private to override."
                )
    except socket.gaierror as e:
        raise CrawlingError(f"Cannot resolve domain '{domain}': {e}")

class WebsiteCrawler:
    from sitewalker import __version__ as _pkg_version
    USER_AGENT = f'Mozilla/5.0 (compatible; sitewalker/{_pkg_version}; +https://github.com/cadentdev/sitewalker)'

    def __init__(self, target: str, timeout: int = 30, delay: float = 1.0,
                 allow_private: bool = False, ignore_robots: bool = False):
        # Parse target: accept full URL (http://example.com) or bare domain (example.com)
        parsed = urlparse(target)
        if parsed.scheme in ('http', 'https'):
            self.domain = parsed.netloc
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            # Bare domain — assume HTTPS
            self.domain = target
            self.base_url = f"https://{target}"

        if not allow_private:
            validate_domain_ssrf(self.domain)

        # Normalize the base URL
        self.base_url, _ = self.process_url(self.base_url)
        self.visited_urls: Set[str] = set()
        self.results: List[Tuple[str, str, int]] = []
        self.external_links: Set[str] = set()
        self.external_links_checked: List[Tuple[str, int]] = []
        self.depth_limited_urls: Set[str] = set()
        self.pages_only: bool = False
        self.timeout = timeout
        self.delay = delay
        self.ignore_robots = ignore_robots
        self.robot_parser: RobotFileParser | None = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.USER_AGENT})

    def process_url(self, url: str) -> Tuple[str, bool]:
        """
        Process and validate a URL.
        Returns: (cleaned_url, is_internal)
        Raises: URLProcessingError if URL is invalid
        """
        if not url:
            raise URLProcessingError("Empty URL")

        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise URLProcessingError("Invalid URL format")

            # Clean URL by removing fragments, query parameters, and trailing slashes
            path = parsed_url.path
            if not path or path == '/':
                path = ''
            else:
                path = path.rstrip('/')

            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{path}"
            is_internal = self.domain in parsed_url.netloc

            if parsed_url.scheme not in ('http', 'https'):
                raise URLProcessingError("Unsupported protocol")

            return clean_url, is_internal

        except Exception as e:
            raise URLProcessingError(f"URL processing error: {str(e)}")

    def is_page(self, url: str) -> bool:
        """
        Check if a URL points to a web page based on its extension or path.
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False

            path = parsed.path.rstrip('/')

            # URLs ending with '/' are considered pages (directory index)
            if not path or path.endswith('/'):
                return True

            # Check if the file extension (if any) is in our list of page extensions
            if '.' in path:
                ext = path.split('.')[-1].lower()
                return ext in PAGE_EXTENSIONS

            # URLs without extensions are considered pages
            return True

        except Exception as e:
            logger.debug(f"Error checking if URL is page: {str(e)}")
            return False

    def _load_robots_txt(self) -> None:
        """Fetch and parse robots.txt for the target domain."""
        if self.ignore_robots:
            return
        robots_url = f"{self.base_url}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=self.timeout)
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                rp.parse(resp.text.splitlines())
                self.robot_parser = rp
                logger.info(f"Loaded robots.txt from {robots_url}")
            else:
                logger.info(f"No robots.txt found at {robots_url} (HTTP {resp.status_code})")
        except Exception as e:
            logger.warning(f"Could not load robots.txt from {robots_url}: {e}")
            self.robot_parser = None

    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt rules."""
        if self.ignore_robots or self.robot_parser is None:
            return True
        return self.robot_parser.can_fetch(self.USER_AGENT, url)

    def crawl(self, collect_external: bool = False, check_external: bool = False,
              recursive: bool = False, pages_only: bool = False,
              max_pages: int = 1000, max_depth: int = 10) -> None:
        """
        Crawl the website starting from the base URL using BFS.

        BFS ensures that depth = shortest link distance from the start URL,
        so max_depth behaves predictably regardless of site structure.

        In non-recursive mode:
        - Crawls the base URL and follows internal links found on that page
        - Does not follow links found on subsequent pages

        In recursive mode:
        - Crawls the base URL and follows all internal links using BFS
        - Continues until all reachable internal pages are visited
        """
        self.pages_only = pages_only
        self.max_pages = max_pages
        self.max_depth = max_depth
        self._load_robots_txt()
        logger.info(f"Starting crawl of {self.base_url}")
        logger.info(f"Mode: {'Recursive' if recursive else 'Single-level'} crawl, "
                   f"{'collecting' if collect_external else 'ignoring'} external links, "
                   f"{'pages only' if pages_only else 'all files'}, "
                   f"max_pages={max_pages}, max_depth={max_depth}")

        # BFS queue: (url, depth)
        queue: deque[Tuple[str, int]] = deque()
        queue.append((self.base_url, 0))
        # Track URLs already queued to avoid duplicates in the queue
        queued: Set[str] = {self.base_url}

        while queue:
            url, depth = queue.popleft()
            if len(self.visited_urls) >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages})")
                break

            discovered = self._process_page(url, collect_external, depth)

            if recursive:
                for next_url in discovered:
                    if next_url in queued:
                        continue
                    next_depth = depth + 1
                    if next_depth > self.max_depth:
                        self.depth_limited_urls.add(next_url)
                        continue
                    queued.add(next_url)
                    queue.append((next_url, next_depth))

        logger.info(f"Crawl complete. Visited {len(self.visited_urls)} pages")
        if self.depth_limited_urls:
            skipped = self.depth_limited_urls - self.visited_urls
            if skipped:
                logger.warning(
                    f"WARNING: {len(skipped)} URLs were skipped due to max_depth={self.max_depth}. "
                    f"These pages were discovered but never crawled. "
                    f"Increase --max-depth to include them."
                )
                for url in sorted(skipped)[:10]:
                    logger.warning(f"  Skipped: {url}")
                if len(skipped) > 10:
                    logger.warning(f"  ... and {len(skipped) - 10} more")
        if collect_external:
            logger.info(f"Found {len(self.external_links)} unique external links")
            if check_external:
                self._check_external_links()

    def _process_page(self, url: str, collect_external: bool, depth: int) -> List[str]:
        """Fetch a single page and return discovered internal URLs."""
        discovered: List[str] = []
        try:
            clean_url, is_internal = self.process_url(url)
            if not is_internal or clean_url in self.visited_urls:
                return discovered

            # Check robots.txt rules
            if not self._is_allowed_by_robots(clean_url):
                logger.debug(f"Blocked by robots.txt: {clean_url}")
                return discovered

            # Skip non-page URLs if pages_only is True
            if self.pages_only and not self.is_page(clean_url):
                logger.debug(f"Skipping non-page URL: {clean_url}")
                return discovered

            self.visited_urls.add(clean_url)
            logger.debug(f"Crawling {clean_url}")

            response = self.session.get(clean_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Process page title
            title = soup.title.string.strip() if soup.title and soup.title.string else "No title"
            self.results.append((clean_url, title, response.status_code))

            # Process links
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                try:
                    next_clean_url, next_is_internal = self.process_url(next_url)

                    if next_is_internal:
                        if next_clean_url not in self.visited_urls:
                            discovered.append(next_clean_url)
                    elif collect_external:
                        self.external_links.add(next_clean_url)

                except URLProcessingError:
                    continue

        except requests.HTTPError as e:
            logger.error(f"HTTP Error crawling {url}: {str(e)}")
            self.results.append((url, "Error", e.response.status_code))
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            self.results.append((url, "Error", 0))

        if self.delay > 0:
            time.sleep(self.delay)
        return discovered

    def _check_external_links(self) -> None:
        """Check HTTP status of each external link via HEAD request."""
        logger.info(f"Checking {len(self.external_links)} external links...")
        for url in sorted(self.external_links):
            try:
                resp = self.session.head(url, timeout=10, allow_redirects=True)
                status = resp.status_code
                # Some servers reject HEAD — retry with GET
                if status == 405:
                    resp = self.session.get(url, timeout=10, allow_redirects=True)
                    status = resp.status_code
                logger.debug(f"External {url}: {status}")
            except Exception as e:
                logger.debug(f"External {url}: failed ({e})")
                status = 0
            self.external_links_checked.append((url, status))
            if self.delay > 0:
                time.sleep(self.delay)
        logger.info(f"External link check complete. "
                   f"{sum(1 for _, s in self.external_links_checked if s == 200)} OK, "
                   f"{sum(1 for _, s in self.external_links_checked if s != 200)} issues")

    @staticmethod
    def _sanitize_csv_value(value: str) -> str:
        """Sanitize a value for safe CSV output.

        Prevents CSV injection by prefixing dangerous characters that
        spreadsheet applications interpret as formulas.
        """
        if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
            return "'" + value
        return value

    def save_results(self, output_file: str) -> None:
        """Save results to a CSV file."""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(['URL', 'Title', 'Status Code'])
            for url, title, status in self.results:
                writer.writerow([
                    self._sanitize_csv_value(url),
                    self._sanitize_csv_value(title),
                    status
                ])
        logger.info(f"Results saved to {output_file}")

    def save_external_links_results(self, filename: str) -> None:
        """Save external links to a CSV file.

        If external links were checked (check_external=True), includes status codes.
        """
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, lineterminator='\n')
            if self.external_links_checked:
                writer.writerow(['External URL', 'Status Code'])
                for url, status in sorted(self.external_links_checked):
                    writer.writerow([self._sanitize_csv_value(url), status])
            else:
                writer.writerow(['External URL'])
                for url in sorted(self.external_links):
                    writer.writerow([self._sanitize_csv_value(url)])
        logger.info(f"External links saved to {filename}")
