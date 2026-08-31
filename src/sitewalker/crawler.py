#!/usr/bin/env python3

import csv
import ipaddress
import socket
from collections import deque
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from typing import Set, List, Tuple
import time
import logging

logger = logging.getLogger(__name__)

# Page titles longer than this are truncated in results (#9)
MAX_TITLE_LENGTH = 256


@dataclass
class PageResult:
    """One row of the crawl output."""
    url: str
    title: str
    status: int | None  # None for rows never fetched (e.g. skipped: max_depth)
    found_on: str = ""  # URL of the page this one was first discovered on; "" for the start URL
    kind: str = "page"  # "page" (parsed for links) or "asset" (recorded only)

    CSV_HEADER = ('URL', 'Title', 'Status Code', 'Found On', 'Kind')

    def as_row(self) -> tuple:
        return (self.url, self.title, self.status, self.found_on, self.kind)

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
    # Cap on discovered URLs (queued set) as a multiple of max_pages (#8)
    QUEUE_MULTIPLIER = 5
    USER_AGENT = f'Mozilla/5.0 (compatible; sitewalker/{_pkg_version}; +https://github.com/cadentdev/sitewalker)'

    def __init__(self, target: str, timeout: int = 30, delay: float = 1.0,
                 allow_private: bool = False, ignore_robots: bool = False,
                 domain_delay: float = 5.0,
                 page_extensions: Set[str] | None = None):
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
        self.results: List[PageResult] = []
        self.external_links: Set[str] = set()
        self.external_links_checked: List[Tuple[str, int]] = []
        # URLs discovered beyond max_depth, mapped to (found_on, kind)
        self.depth_limited_urls: dict[str, tuple[str, str]] = {}
        self.pages_only: bool = False
        self.include_assets: bool = False
        # Extensions treated as pages by -p; None means the built-in set
        self.page_extensions: Set[str] = (
            PAGE_EXTENSIONS if page_extensions is None else set(page_extensions))
        self.timeout = timeout
        self.delay = delay
        # Minimum seconds between requests to the same external domain
        self.domain_delay = domain_delay
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
                return ext in self.page_extensions

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
              max_pages: int = 1000, max_depth: int = 10,
              max_external_links: int = 500, include_assets: bool = False) -> None:
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

        The set of discovered-but-unvisited URLs is capped at
        QUEUE_MULTIPLIER * max_pages so dense link graphs cannot grow the
        queue without bound.

        include_assets extends discovery to img/script/link/source
        references (src, href, srcset). Assets are fetched for their HTTP
        status and recorded, but never parsed for further links. They are
        recorded even in non-recursive mode and count toward max_pages.
        """
        self.pages_only = pages_only
        self.include_assets = include_assets
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.max_external_links = max_external_links
        max_queued = self.QUEUE_MULTIPLIER * max_pages
        queue_capped = False
        self._load_robots_txt()
        logger.info(f"Starting crawl of {self.base_url}")
        logger.info(f"Mode: {'Recursive' if recursive else 'Single-level'} crawl, "
                   f"{'collecting' if collect_external else 'ignoring'} external links, "
                   f"discovery: anchors{'+assets' if include_assets else ''}, "
                   f"filter: {'pages only' if pages_only else 'none'}, "
                   f"max_pages={max_pages}, max_depth={max_depth}")

        # BFS queue: (url, depth, found_on, kind)
        queue: deque[Tuple[str, int, str, str]] = deque()
        queue.append((self.base_url, 0, "", "page"))
        # Track URLs already queued to avoid duplicates in the queue
        queued: Set[str] = {self.base_url}

        while queue:
            url, depth, found_on, kind = queue.popleft()
            if len(self.visited_urls) >= self.max_pages:
                logger.info(f"Reached max_pages limit ({self.max_pages})")
                break

            if kind == "asset":
                self._record_asset(url, found_on)
                continue
            discovered = self._process_page(url, collect_external, depth, found_on)

            for next_url, next_kind in discovered:
                # Page links are only followed in recursive mode;
                # assets are recorded whenever discovered.
                if next_kind == "page" and not recursive:
                    continue
                if next_url in queued:
                    continue
                next_depth = depth + 1
                if next_depth > self.max_depth:
                    self.depth_limited_urls.setdefault(next_url, (url, next_kind))
                    continue
                if len(queued) >= max_queued:
                    if not queue_capped:
                        queue_capped = True
                        logger.warning(
                            f"WARNING: Queue limit reached ({max_queued} URLs, "
                            f"{self.QUEUE_MULTIPLIER}x max_pages). "
                            f"Newly discovered URLs will be ignored."
                        )
                    break
                queued.add(next_url)
                queue.append((next_url, next_depth, url, next_kind))

        logger.info(f"Crawl complete. Visited {len(self.visited_urls)} pages")
        skipped = self.depth_limited_urls.keys() - self.visited_urls
        if skipped:
            logger.warning(
                f"WARNING: {len(skipped)} URLs were skipped due to max_depth={self.max_depth}. "
                f"They are included in the results CSV with title 'skipped: max_depth'. "
                f"Increase --max-depth to crawl them."
            )
            for url in sorted(skipped):
                ref, skipped_kind = self.depth_limited_urls[url]
                self.results.append(PageResult(
                    url, "skipped: max_depth", None, ref, skipped_kind))
        if collect_external:
            logger.info(f"Found {len(self.external_links)} unique external links")
            if check_external:
                self._check_external_links()

    ASSET_SELECTORS = (('img', 'src'), ('script', 'src'),
                       ('link', 'href'), ('source', 'src'))

    @staticmethod
    def _extract_asset_urls(soup, base_url: str) -> List[str]:
        """Collect asset references (src/href/srcset) from a parsed page."""
        urls: List[str] = []
        for tag, attr in WebsiteCrawler.ASSET_SELECTORS:
            for el in soup.find_all(tag, **{attr: True}):
                urls.append(urljoin(base_url, el[attr]))
        # srcset: comma-separated "url [descriptor]" candidates
        for el in soup.find_all(('img', 'source'), srcset=True):
            for candidate in el['srcset'].split(','):
                parts = candidate.strip().split()
                if parts:
                    urls.append(urljoin(base_url, parts[0]))
        return urls

    def _record_asset(self, url: str, found_on: str) -> None:
        """Fetch an asset for its HTTP status and record it — never parse it.

        Uses HEAD (with a GET fallback on 405, body not downloaded) so a
        4 MB image costs a header exchange, not a transfer.
        """
        try:
            clean_url, is_internal = self.process_url(url)
            if not is_internal or clean_url in self.visited_urls:
                return
            if not self._is_allowed_by_robots(clean_url):
                logger.debug(f"Blocked by robots.txt: {clean_url}")
                return
            self.visited_urls.add(clean_url)
            logger.debug(f"Recording asset {clean_url}")
            resp = self.session.head(clean_url, timeout=self.timeout,
                                     allow_redirects=True)
            status = resp.status_code
            if status == 405:
                resp = self.session.get(clean_url, timeout=self.timeout, stream=True)
                status = resp.status_code
                resp.close()
            self.results.append(PageResult(clean_url, "", status, found_on, "asset"))
        except Exception as e:
            logger.error(f"Error fetching asset {url}: {str(e)}")
            self.results.append(PageResult(url, "Error", 0, found_on, "asset"))
        if self.delay > 0:
            time.sleep(self.delay)

    def _process_page(self, url: str, collect_external: bool, depth: int,
                      found_on: str = "") -> List[Tuple[str, str]]:
        """Fetch a single page and return discovered internal (url, kind) pairs.

        found_on is the URL of the page this one was first discovered on.
        """
        discovered: List[Tuple[str, str]] = []
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
            if len(title) > MAX_TITLE_LENGTH:
                title = title[:MAX_TITLE_LENGTH]
            self.results.append(PageResult(clean_url, title, response.status_code, found_on))

            # Process links
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                try:
                    next_clean_url, next_is_internal = self.process_url(next_url)

                    if next_is_internal:
                        if next_clean_url not in self.visited_urls:
                            discovered.append((next_clean_url, "page"))
                    elif collect_external:
                        self.external_links.add(next_clean_url)

                except URLProcessingError:
                    continue

            if self.include_assets:
                for asset_url in self._extract_asset_urls(soup, url):
                    try:
                        clean, is_int = self.process_url(asset_url)
                        if is_int:
                            if clean not in self.visited_urls:
                                discovered.append((clean, "asset"))
                        elif collect_external:
                            self.external_links.add(clean)
                    except URLProcessingError:
                        continue

        except requests.HTTPError as e:
            logger.error(f"HTTP Error crawling {url}: {str(e)}")
            self.results.append(PageResult(url, "Error", e.response.status_code, found_on))
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            self.results.append(PageResult(url, "Error", 0, found_on))

        if self.delay > 0:
            time.sleep(self.delay)
        return discovered

    def _order_external_links(self) -> List[str]:
        """Return external links round-robin interleaved by domain.

        Spreading same-domain URLs apart means the per-domain delay rarely
        has to block; the global delay usually covers it.
        """
        by_domain: dict[str, deque] = {}
        for url in sorted(self.external_links):
            by_domain.setdefault(urlparse(url).netloc, deque()).append(url)
        ordered: List[str] = []
        while by_domain:
            for domain in list(by_domain):
                ordered.append(by_domain[domain].popleft())
                if not by_domain[domain]:
                    del by_domain[domain]
        return ordered

    def _check_external_links(self) -> None:
        """Check HTTP status of each external link via HEAD request.

        Checks at most max_external_links URLs, and waits at least
        domain_delay seconds between requests to the same domain.
        """
        links = self._order_external_links()
        if len(links) > self.max_external_links:
            logger.warning(
                f"WARNING: {len(links)} external links found, checking only the first "
                f"{self.max_external_links}. Increase --max-external-links to check more."
            )
            links = links[:self.max_external_links]
        logger.info(f"Checking {len(links)} external links...")
        last_request: dict[str, float] = {}
        for url in links:
            domain = urlparse(url).netloc
            if domain in last_request:
                wait = self.domain_delay - (time.monotonic() - last_request[domain])
                if wait > 0:
                    logger.debug(f"Rate limiting {domain}: waiting {wait:.1f}s")
                    time.sleep(wait)
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
            last_request[domain] = time.monotonic()
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
            writer.writerow(PageResult.CSV_HEADER)
            for r in self.results:
                writer.writerow([self._sanitize_csv_value(v) for v in r.as_row()])
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
