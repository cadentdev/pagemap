import pytest
from sitewalker.crawler import (
    PageResult,
    MAX_TITLE_LENGTH,
    WebsiteCrawler, URLProcessingError, SSRFProtectionError,
    validate_domain_ssrf
)
import responses
import tempfile
import os
import csv
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException
import requests
import logging


@pytest.fixture
def crawler_instance():
    """Fixture to create a WebsiteCrawler instance for testing."""
    crawler = WebsiteCrawler("example.com", allow_private=True)
    return crawler


def test_init():
    """Test WebsiteCrawler initialization"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)
    assert crawler.domain == domain
    assert crawler.base_url == f"https://{domain}"
    assert len(crawler.visited_urls) == 0
    assert len(crawler.results) == 0
    assert len(crawler.external_links) == 0


def test_process_url():
    """Test URL processing with various inputs"""
    crawler = WebsiteCrawler("example.com")

    # Test valid internal URL
    url, is_internal = crawler.process_url("https://example.com/page")
    assert url == "https://example.com/page"
    assert is_internal is True

    # Test valid external URL
    url, is_internal = crawler.process_url("https://external.com/page")
    assert url == "https://external.com/page"
    assert is_internal is False

    # Test URL cleaning (remove query params and fragments)
    url, _ = crawler.process_url("https://example.com/page?param=1#section")
    assert url == "https://example.com/page"


def test_process_url_errors():
    """Test URL processing error cases"""
    crawler = WebsiteCrawler("example.com")

    # Test empty URL
    with pytest.raises(URLProcessingError, match="Empty URL"):
        crawler.process_url("")

    # Test invalid protocol
    with pytest.raises(URLProcessingError, match="Unsupported protocol"):
        crawler.process_url("ftp://example.com")

    # Test invalid URL format
    with pytest.raises(URLProcessingError, match="Invalid URL format"):
        crawler.process_url("example.com/page")


@responses.activate
def test_crawl_page():
    """Test crawling a single page"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with some links
    html_content = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <a href="https://example.com/page1">Page 1</a>
            <a href="https://example.com/page2">Page 2</a>
            <a href="https://external.com">External</a>
        </body>
    </html>
    """

    responses.add(
        responses.GET,
        'https://example.com',
        body=html_content,
        status=200,
        content_type='text/html'
    )

    # Crawl the page
    crawler.crawl()

    # Check results
    assert len(crawler.visited_urls) == 1
    assert len(crawler.results) == 1
    assert crawler.results[0].url == 'https://example.com'
    assert crawler.results[0].title == 'Test Page'
    assert crawler.results[0].status == 200


@responses.activate
def test_recursive_crawl():
    """Test recursive crawling of pages"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock responses for multiple pages
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Home</title></head>
            <body>
                <a href="https://example.com/page1">Page 1</a>
                <a href="https://external.com">External</a>
            </body>
        </html>
        """,
        status=200
    )

    responses.add(
        responses.GET,
        'https://example.com/page1',
        body="""
        <html>
            <head><title>Page 1</title></head>
            <body>
                <a href="https://example.com/page2">Page 2</a>
            </body>
        </html>
        """,
        status=200
    )

    responses.add(
        responses.GET,
        'https://example.com/page2',
        body="""
        <html>
            <head><title>Page 2</title></head>
            <body>
                <a href="https://example.com">Home</a>
            </body>
        </html>
        """,
        status=200
    )

    # Test recursive crawl
    crawler.crawl(recursive=True)

    # Check that all pages were visited
    assert len(crawler.visited_urls) == 3
    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/page1' in crawler.visited_urls
    assert 'https://example.com/page2' in crawler.visited_urls

    # Check that titles were collected
    titles = [r.title for r in crawler.results]
    assert 'Home' in titles
    assert 'Page 1' in titles
    assert 'Page 2' in titles


@responses.activate
def test_external_links_collection():
    """Test collection of external links"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with external links
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="https://external1.com">External 1</a>
                <a href="https://external2.com">External 2</a>
                <a href="https://example.com/internal">Internal</a>
            </body>
        </html>
        """,
        status=200
    )

    # Crawl with external link collection
    crawler.crawl(collect_external=True)

    # Check external links were collected
    assert len(crawler.external_links) == 2
    assert 'https://external1.com' in crawler.external_links
    assert 'https://external2.com' in crawler.external_links


@responses.activate
def test_crawl_page_with_error(caplog):
    """Test crawling a page that returns an error"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with error
    responses.add(
        responses.GET,
        'https://example.com',
        status=404
    )

    # Crawl the page and check error was logged
    crawler.crawl()
    assert "HTTP Error crawling https://example.com: 404" in caplog.text


@responses.activate
def test_crawl_page_with_network_error(caplog):
    """Test crawling a page that has network errors"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock a network error
    responses.add(
        responses.GET,
        'https://example.com',
        body=RequestException("Network error")
    )

    # Crawl the page and check error was logged
    crawler.crawl()
    assert "Error crawling https://example.com" in caplog.text


@responses.activate
def test_crawl_page_with_invalid_html():
    """Test crawling a page with invalid HTML"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with invalid HTML
    responses.add(
        responses.GET,
        'https://example.com',
        body="<html><head>No title</head><body>Invalid HTML",
        status=200
    )

    # Crawl the page
    crawler.crawl()

    # Check that page was processed despite invalid HTML
    assert len(crawler.results) == 1
    assert crawler.results[0].title == "No title"


@responses.activate
def test_crawl_page_with_empty_title():
    """Test crawling a page with an empty <title></title> tag doesn't crash."""
    crawler = WebsiteCrawler("example.com")

    responses.add(
        responses.GET,
        'https://example.com',
        body="<html><head><title></title></head><body>Content</body></html>",
        status=200
    )

    crawler.crawl()

    assert len(crawler.results) == 1
    assert crawler.results[0].title == "No title"


def test_save_results():
    """Test saving results to a CSV file"""
    crawler = WebsiteCrawler("example.com")
    crawler.results = [
        PageResult("https://example.com", "Home Page", 200),
        PageResult("https://example.com/about", "About Us", 200),
        PageResult("https://example.com/contact", "Contact", 404)
    ]

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
        output_file = tmp_file.name

    try:
        # Save results
        crawler.save_results(output_file)

        # Read and verify the CSV content
        with open(output_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check header and content
            assert rows[0] == ["URL", "Title", "Status Code", "Found On"]
            assert len(rows) == 4  # Header + 3 results
            assert rows[1] == ["https://example.com", "Home Page", "200", ""]

    finally:
        os.unlink(output_file)


@responses.activate
def test_crawl_page_with_missing_title():
    """Test crawling a page without a title tag"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with HTML missing title tag
    responses.add(
        responses.GET,
        'https://example.com',
        body="<html><body>No title tag here</body></html>",
        status=200
    )

    # Crawl the page
    crawler.crawl()

    # Check that page was processed with default title
    assert len(crawler.results) == 1
    assert crawler.results[0].title == "No title"


@responses.activate
def test_crawl_page_with_relative_links():
    """Test handling of relative links"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with relative links
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="/page1">Relative Link 1</a>
                <a href="page2">Relative Link 2</a>
                <a href="../page3">Relative Link 3</a>
            </body>
        </html>
        """,
        status=200
    )

    # Mock responses for relative links
    responses.add(
        responses.GET,
        'https://example.com/page1',
        body="<html><head><title>Page 1</title></head></html>",
        status=200
    )

    responses.add(
        responses.GET,
        'https://example.com/page2',
        body="<html><head><title>Page 2</title></head></html>",
        status=200
    )

    responses.add(
        responses.GET,
        'https://example.com/page3',
        body="<html><head><title>Page 3</title></head></html>",
        status=200
    )

    # Test recursive crawl with relative links
    crawler.crawl(recursive=True)

    # Check that relative links were properly resolved and crawled
    assert len(crawler.visited_urls) == 4
    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/page1' in crawler.visited_urls
    assert 'https://example.com/page2' in crawler.visited_urls
    assert 'https://example.com/page3' in crawler.visited_urls


@responses.activate
def test_crawl_page_with_malformed_links():
    """Test handling of malformed links"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with malformed links
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="javascript:void(0)">JavaScript Link</a>
                <a href="mailto:test@example.com">Email Link</a>
                <a href="#">Hash Link</a>
                <a href="">Empty Link</a>
                <a>No Href</a>
            </body>
        </html>
        """,
        status=200
    )

    # Crawl the page
    crawler.crawl()

    # Check that the page was processed without errors
    assert len(crawler.visited_urls) == 1
    assert len(crawler.results) == 1
    assert crawler.results[0].url == 'https://example.com'


@responses.activate
def test_skip_already_visited():
    """Test that pages aren't crawled multiple times"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with a link to self
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="https://example.com">Self Link</a>
                <a href="https://example.com/">Root with slash</a>
            </body>
        </html>
        """,
        status=200
    )

    # Crawl the page
    crawler.crawl(recursive=True)

    # Check that the page was only crawled once
    assert len(crawler.visited_urls) == 1
    assert len(crawler.results) == 1


def test_save_external_links():
    """Test saving external links to a CSV file"""
    crawler = WebsiteCrawler("example.com")
    crawler.external_links = {
        "https://external1.com",
        "https://external2.com"
    }

    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
        output_file = tmp_file.name

    try:
        # Save external links
        crawler.save_external_links_results(output_file)

        # Read and verify the CSV content
        with open(output_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check content
            assert rows[0] == ["External URL"]
            assert len(rows) == 3  # Header + 2 external links
            urls = {rows[1][0], rows[2][0]}
            assert urls == crawler.external_links

    finally:
        os.unlink(output_file)


@responses.activate
def test_recursive_external_links_collection():
    """Test recursive crawling with external link collection"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with external links
    responses.add(
        responses.GET,
        'https://example.com',
        body="""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <a href="https://external1.com">External 1</a>
                <a href="https://example.com/page1">Internal 1</a>
            </body>
        </html>
        """,
        status=200
    )

    responses.add(
        responses.GET,
        'https://example.com/page1',
        body="""
        <html>
            <head><title>Page 1</title></head>
            <body>
                <a href="https://external2.com">External 2</a>
            </body>
        </html>
        """,
        status=200
    )

    # Test recursive crawl with external links
    crawler.crawl(collect_external=True, recursive=True)

    assert len(crawler.external_links) == 2
    assert len(crawler.visited_urls) == 2


def test_is_page():
    """Test URL page type detection"""
    crawler = WebsiteCrawler("example.com")

    # Test URLs ending with '/'
    assert crawler.is_page("https://example.com/") is True
    assert crawler.is_page("https://example.com/path/") is True

    # Test URLs with page extensions
    assert crawler.is_page("https://example.com/page.html") is True
    assert crawler.is_page("https://example.com/page.php") is True
    assert crawler.is_page("https://example.com/page.asp") is True

    # Test URLs without extensions
    assert crawler.is_page("https://example.com/about") is True

    # Test non-page URLs
    assert crawler.is_page("https://example.com/image.jpg") is False
    assert crawler.is_page("https://example.com/doc.pdf") is False

    # Test invalid URLs
    assert crawler.is_page("not-a-url") is False


@responses.activate
def test_crawl_pages_only():
    """Test crawling with pages_only flag"""
    domain = "example.com"
    crawler = WebsiteCrawler(domain)

    # Mock response with various link types
    html_content = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <a href="https://example.com/page1.html">Page 1</a>
            <a href="https://example.com/image.jpg">Image</a>
            <a href="https://example.com/doc.pdf">Document</a>
        </body>
    </html>
    """

    responses.add(
        responses.GET,
        'https://example.com',
        body=html_content,
        status=200,
        content_type='text/html'
    )

    # Add mock response for page1.html
    responses.add(
        responses.GET,
        'https://example.com/page1.html',
        body='<html><head><title>Pg. 1</title></head><body>Test</body></html>',
        status=200,
        content_type='text/html')

    # Crawl with pages_only=True
    crawler.crawl(recursive=True, pages_only=True)

    # Should only visit the base URL and page1.html
    assert len(crawler.visited_urls) == 2
    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/page1.html' in crawler.visited_urls
    assert 'https://example.com/image.jpg' not in crawler.visited_urls
    assert 'https://example.com/doc.pdf' not in crawler.visited_urls


def test_crawl_with_non_page_skipped(crawler_instance):
    """Test that non-page URLs are skipped when pages_only is True."""
    base_url = "http://example.com/page"
    non_page_url = "http://example.com/image.jpg"
    crawler_instance.base_url = base_url
    crawler_instance.domain = "example.com"
    crawler_instance.visited_urls = set()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.text = (
        f'<html><body><a href="{non_page_url}">Non-page</a></body></html>'
    )
    mock_response.url = base_url

    with patch('requests.get', return_value=mock_response):
        crawler_instance.crawl(pages_only=True, recursive=False)

    assert base_url in crawler_instance.visited_urls
    assert non_page_url not in crawler_instance.visited_urls
    assert not any(r.url == non_page_url for r in crawler_instance.results)


def test_is_page_exception(crawler_instance, caplog):
    """Test that is_page handles exceptions gracefully."""
    malformed_url = "http://[::1]:80"
    caplog.set_level(logging.DEBUG)

    with patch('sitewalker.crawler.urlparse',
               side_effect=ValueError("Mock parsing error")):
        assert not crawler_instance.is_page(malformed_url)

    assert "Error checking if URL is page: Mock parsing error" in caplog.text


def test_save_results_empty(crawler_instance, tmp_path):
    """Test saving results when no pages were crawled."""
    output_file = tmp_path / "results.csv"
    crawler_instance.results = []
    crawler_instance.save_results(output_file)

    assert output_file.exists()
    with open(output_file, 'r') as f:
        content = f.read()
        assert content.strip() == "URL,Title,Status Code,Found On"


def test_ssrf_blocks_localhost():
    """Test that SSRF protection blocks localhost."""
    with pytest.raises(SSRFProtectionError, match="private/reserved IP"):
        WebsiteCrawler("localhost")


def test_ssrf_blocks_private_ip():
    """Test that SSRF protection blocks private IPs."""
    with patch('sitewalker.crawler.socket.getaddrinfo',
               return_value=[(2, 1, 6, '', ('192.168.1.1', 0))]):
        with pytest.raises(SSRFProtectionError, match="private/reserved IP"):
            WebsiteCrawler("evil.example.com")


def test_ssrf_allow_private_override():
    """Test that --allow-private bypasses SSRF protection."""
    crawler = WebsiteCrawler("localhost", allow_private=True)
    assert crawler.domain == "localhost"


def test_timeout_passed_to_requests():
    """Test that timeout is passed to session.get."""
    crawler = WebsiteCrawler("example.com", timeout=5)
    assert crawler.timeout == 5


@responses.activate
def test_bfs_finds_children_at_correct_depth():
    """Test that BFS explores children at the shortest path depth.

    This is the core bug from issue #1: DFS visits /services via a deep path
    (Home→About→Contact→Services at depth 3), so /services/pricing is explored
    at depth 4 and blocked by max_depth=3. BFS visits /services at depth 1
    (directly from Home), so /services/pricing is explored at depth 2.

    Site structure:
      Home → About, Services
      About → Contact
      Contact → Services (cross-link)
      Services → Services/Pricing
    """
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com/robots.txt', status=404)
    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://example.com/about">About</a>'
             '<a href="https://example.com/services">Services</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/about',
        body='<html><head><title>About</title></head><body>'
             '<a href="https://example.com/contact">Contact</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/contact',
        body='<html><head><title>Contact</title></head><body>'
             '<a href="https://example.com/services">Services</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/services',
        body='<html><head><title>Services</title></head><body>'
             '<a href="https://example.com/services/pricing">Pricing</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/services/pricing',
        body='<html><head><title>Pricing</title></head><body></body></html>',
        status=200)

    crawler.crawl(recursive=True, max_depth=3)

    # BFS: Home(0) → About(1), Services(1) → Contact(2), Pricing(2) → all within depth 3
    # DFS: Home(0) → About(1) → Contact(2) → Services(3) → Pricing(4, BLOCKED!)
    assert 'https://example.com/services/pricing' in crawler.visited_urls, \
        "Pricing should be at BFS depth 2 (Home→Services→Pricing), not DFS depth 4"


@responses.activate
def test_max_pages_limit():
    """Test that crawling stops at max_pages limit."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://example.com/p1">1</a>'
             '<a href="https://example.com/p2">2</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/p1',
        body='<html><head><title>P1</title></head></html>', status=200)
    responses.add(responses.GET, 'https://example.com/p2',
        body='<html><head><title>P2</title></head></html>', status=200)

    crawler.crawl(recursive=True, max_pages=2)
    assert len(crawler.visited_urls) <= 2


@responses.activate
def test_max_depth_limit():
    """Test that crawling stops at max_depth limit."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>D0</title></head><body>'
             '<a href="https://example.com/d1">D1</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/d1',
        body='<html><head><title>D1</title></head><body>'
             '<a href="https://example.com/d2">D2</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/d2',
        body='<html><head><title>D2</title></head><body></body></html>', status=200)

    crawler.crawl(recursive=True, max_depth=1)
    # depth 0 = base, depth 1 = d1, depth 2 = d2 (blocked)
    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/d1' in crawler.visited_urls
    assert 'https://example.com/d2' not in crawler.visited_urls


@responses.activate
def test_max_depth_warning(caplog):
    """Test that a warning is logged when URLs are skipped due to max_depth."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>D0</title></head><body>'
             '<a href="https://example.com/d1">D1</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/d1',
        body='<html><head><title>D1</title></head><body>'
             '<a href="https://example.com/d2">D2</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/d2',
        body='<html><head><title>D2</title></head><body></body></html>', status=200)

    import logging
    with caplog.at_level(logging.WARNING):
        crawler.crawl(recursive=True, max_depth=1)

    assert 'https://example.com/d2' not in crawler.visited_urls
    assert 'https://example.com/d2' in crawler.depth_limited_urls
    assert any("1 URLs were skipped due to max_depth=1" in msg for msg in caplog.messages)
    skipped_row = next(r for r in crawler.results if r.url == 'https://example.com/d2')
    assert skipped_row.title == "skipped: max_depth"
    assert skipped_row.status is None
    assert skipped_row.found_on == 'https://example.com/d1' 


def test_csv_sanitization():
    """Test that CSV injection characters are sanitized."""
    crawler = WebsiteCrawler("example.com")
    assert crawler._sanitize_csv_value("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert crawler._sanitize_csv_value("+cmd") == "'+cmd"
    assert crawler._sanitize_csv_value("-cmd") == "'-cmd"
    assert crawler._sanitize_csv_value("@sum") == "'@sum"
    assert crawler._sanitize_csv_value("Normal title") == "Normal title"
    assert crawler._sanitize_csv_value("") == ""


def test_csv_sanitization_in_output(tmp_path):
    """Test that saved CSV files have sanitized values."""
    crawler = WebsiteCrawler("example.com")
    crawler.results = [
        PageResult("https://example.com", "=HYPERLINK('evil')", 200),
    ]
    output_file = tmp_path / "results.csv"
    crawler.save_results(str(output_file))

    with open(output_file, 'r') as f:
        content = f.read()
        assert "'=HYPERLINK('evil')" in content


@responses.activate
def test_robots_txt_blocks_disallowed_paths():
    """Test that robots.txt disallowed paths are skipped."""
    crawler = WebsiteCrawler("example.com")

    # Mock robots.txt
    responses.add(responses.GET, 'https://example.com/robots.txt',
        body="User-agent: *\nDisallow: /secret/\n", status=200)

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://example.com/public">Public</a>'
             '<a href="https://example.com/secret/page">Secret</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/public',
        body='<html><head><title>Public</title></head></html>', status=200)
    responses.add(responses.GET, 'https://example.com/secret/page',
        body='<html><head><title>Secret</title></head></html>', status=200)

    crawler.crawl(recursive=True)

    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/public' in crawler.visited_urls
    assert 'https://example.com/secret/page' not in crawler.visited_urls


@responses.activate
def test_ignore_robots_flag():
    """Test that --ignore-robots bypasses robots.txt checking."""
    crawler = WebsiteCrawler("example.com", ignore_robots=True)

    # No robots.txt mock needed — it should not be fetched
    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://example.com/secret/page">Secret</a>'
             '</body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/secret/page',
        body='<html><head><title>Secret</title></head></html>', status=200)

    crawler.crawl(recursive=True)

    assert 'https://example.com' in crawler.visited_urls
    assert 'https://example.com/secret/page' in crawler.visited_urls


def test_save_results_unix_line_endings(tmp_path):
    """Test that saved CSV uses Unix line endings (no \\r)."""
    crawler = WebsiteCrawler("example.com")
    crawler.results = [
        PageResult("https://example.com", "Home Page", 200),
        PageResult("https://example.com/about", "About Us", 200),
    ]
    output_file = tmp_path / "results.csv"
    crawler.save_results(str(output_file))

    raw = output_file.read_bytes()
    assert b'\r' not in raw, f"Found \\r in CSV output: {raw[:200]}"


def test_save_external_links_unix_line_endings(tmp_path):
    """Test that saved external links CSV uses Unix line endings (no \\r)."""
    crawler = WebsiteCrawler("example.com")
    crawler.external_links = {"https://external1.com", "https://external2.com"}
    output_file = tmp_path / "external.csv"
    crawler.save_external_links_results(str(output_file))

    raw = output_file.read_bytes()
    assert b'\r' not in raw, f"Found \\r in CSV output: {raw[:200]}"


@responses.activate
def test_robots_txt_missing_gracefully():
    """Test that a missing robots.txt doesn't block crawling."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com/robots.txt', status=404)
    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head></html>', status=200)

    crawler.crawl()

    assert 'https://example.com' in crawler.visited_urls


@responses.activate
def test_check_external_links_status():
    """Test that check_external checks HTTP status of external links."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://good.com">Good</a>'
             '<a href="https://broken.com">Broken</a>'
             '</body></html>', status=200)
    responses.add(responses.HEAD, 'https://good.com', status=200)
    responses.add(responses.HEAD, 'https://broken.com', status=404)

    crawler.crawl(collect_external=True, check_external=True)

    # external_links_checked should have status codes
    checked = {url: status for url, status in crawler.external_links_checked}
    assert checked['https://good.com'] == 200
    assert checked['https://broken.com'] == 404


@responses.activate
def test_check_external_timeout():
    """Test that external link check handles timeouts gracefully."""
    crawler = WebsiteCrawler("example.com")

    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="https://slow.com">Slow</a>'
             '</body></html>', status=200)
    responses.add(responses.HEAD, 'https://slow.com',
        body=requests.ConnectionError("timeout"))

    crawler.crawl(collect_external=True, check_external=True)

    checked = {url: status for url, status in crawler.external_links_checked}
    assert checked['https://slow.com'] == 0


def test_save_external_links_with_status(tmp_path):
    """Test that external links CSV includes status code when checked."""
    crawler = WebsiteCrawler("example.com")
    crawler.external_links_checked = [
        ("https://good.com", 200),
        ("https://broken.com", 404),
    ]

    output_file = tmp_path / "external.csv"
    crawler.save_external_links_results(str(output_file))

    with open(output_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert rows[0] == ["External URL", "Status Code"]
    assert rows[1] == ["https://broken.com", "404"]
    assert rows[2] == ["https://good.com", "200"]


# --- Crawl limits (#6, #7, #8) ---

@responses.activate
def test_max_external_links_caps_checking(caplog):
    """Only max_external_links URLs are checked; the rest are skipped with a warning (#6)."""
    crawler = WebsiteCrawler("example.com", delay=0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><body>'
             '<a href="https://a.com">A</a>'
             '<a href="https://b.com">B</a>'
             '<a href="https://c.com">C</a>'
             '</body></html>', status=200)
    for d in ('a', 'b', 'c'):
        responses.add(responses.HEAD, f'https://{d}.com', status=200)

    with caplog.at_level(logging.WARNING):
        crawler.crawl(collect_external=True, check_external=True, max_external_links=2)

    assert len(crawler.external_links) == 3
    assert len(crawler.external_links_checked) == 2
    assert "checking only the first 2" in caplog.text


def test_order_external_links_interleaves_domains():
    """Same-domain links are spread apart round-robin (#7)."""
    crawler = WebsiteCrawler("example.com", delay=0)
    crawler.external_links = {
        'https://a.com/1', 'https://a.com/2', 'https://a.com/3',
        'https://b.com/1', 'https://c.com/1',
    }
    ordered = crawler._order_external_links()
    assert ordered == [
        'https://a.com/1', 'https://b.com/1', 'https://c.com/1',
        'https://a.com/2', 'https://a.com/3',
    ]


@responses.activate
def test_per_domain_rate_limit_sleeps_between_same_domain_requests():
    """Consecutive requests to one domain wait domain_delay seconds (#7)."""
    crawler = WebsiteCrawler("example.com", delay=0, domain_delay=5.0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><body>'
             '<a href="https://a.com/1">1</a>'
             '<a href="https://a.com/2">2</a>'
             '</body></html>', status=200)
    responses.add(responses.HEAD, 'https://a.com/1', status=200)
    responses.add(responses.HEAD, 'https://a.com/2', status=200)

    clock = [100.0]
    sleeps = []

    def fake_sleep(secs):
        sleeps.append(secs)
        clock[0] += secs

    with patch('sitewalker.crawler.time.monotonic', side_effect=lambda: clock[0]), \
         patch('sitewalker.crawler.time.sleep', side_effect=fake_sleep):
        crawler.crawl(collect_external=True, check_external=True)

    assert len(crawler.external_links_checked) == 2
    assert sleeps == [5.0]


@responses.activate
def test_per_domain_rate_limit_does_not_sleep_across_domains():
    """Requests to different domains are not delayed by domain_delay (#7)."""
    crawler = WebsiteCrawler("example.com", delay=0, domain_delay=5.0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><body>'
             '<a href="https://a.com">A</a>'
             '<a href="https://b.com">B</a>'
             '</body></html>', status=200)
    responses.add(responses.HEAD, 'https://a.com', status=200)
    responses.add(responses.HEAD, 'https://b.com', status=200)

    with patch('sitewalker.crawler.time.sleep') as mock_sleep:
        crawler.crawl(collect_external=True, check_external=True)

    mock_sleep.assert_not_called()


@responses.activate
def test_queue_size_is_capped(caplog):
    """The queued set stops growing at QUEUE_MULTIPLIER * max_pages (#8)."""
    crawler = WebsiteCrawler("example.com", delay=0)
    # Home page links to 20 pages; max_pages=2 → cap of 10 queued URLs
    links = ''.join(f'<a href="/p{i}">{i}</a>' for i in range(20))
    responses.add(responses.GET, 'https://example.com',
        body=f'<html><body>{links}</body></html>', status=200)
    for i in range(20):
        responses.add(responses.GET, f'https://example.com/p{i}',
            body='<html><body></body></html>', status=200)

    with caplog.at_level(logging.WARNING):
        crawler.crawl(recursive=True, max_pages=2)

    assert "Queue limit reached (10 URLs" in caplog.text
    # Only max_pages were actually visited
    assert len(crawler.visited_urls) == 2



# --- PageResult / Found On (#14 part 1) and title truncation (#9) ---

@responses.activate
def test_found_on_records_first_referrer():
    """Each result records the page it was first discovered on; the start URL has none."""
    crawler = WebsiteCrawler("example.com", delay=0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><head><title>Home</title></head><body>'
             '<a href="/a">A</a><a href="/b">B</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/a',
        body='<html><head><title>A</title></head><body>'
             '<a href="/b">B again</a><a href="/c">C</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/b',
        body='<html><head><title>B</title></head></html>', status=200)
    responses.add(responses.GET, 'https://example.com/c',
        body='<html><head><title>C</title></head></html>', status=200)

    crawler.crawl(recursive=True)

    found_on = {r.url: r.found_on for r in crawler.results}
    assert found_on['https://example.com'] == ''
    assert found_on['https://example.com/a'] == 'https://example.com'
    # /b is linked from both / and /a; BFS discovers it from / first
    assert found_on['https://example.com/b'] == 'https://example.com'
    assert found_on['https://example.com/c'] == 'https://example.com/a'


@responses.activate
def test_found_on_recorded_for_error_pages():
    """A 404 keeps its referrer so the broken link can be traced back."""
    crawler = WebsiteCrawler("example.com", delay=0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><body><a href="/missing">x</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/missing', status=404)

    crawler.crawl(recursive=True)

    broken = next(r for r in crawler.results if r.status == 404)
    assert broken.url == 'https://example.com/missing'
    assert broken.title == 'Error'
    assert broken.found_on == 'https://example.com'


@responses.activate
def test_title_is_truncated():
    """Titles longer than MAX_TITLE_LENGTH are cut to prevent CSV bloat."""
    crawler = WebsiteCrawler("example.com", delay=0)
    long_title = 'x' * (MAX_TITLE_LENGTH + 500)
    responses.add(responses.GET, 'https://example.com',
        body=f'<html><head><title>{long_title}</title></head></html>', status=200)

    crawler.crawl()

    assert len(crawler.results[0].title) == MAX_TITLE_LENGTH


def test_save_results_writes_found_on_column(tmp_path):
    crawler = WebsiteCrawler("example.com")
    crawler.results = [
        PageResult("https://example.com", "Home", 200),
        PageResult("https://example.com/about", "About", 200, found_on="https://example.com"),
    ]
    output_file = tmp_path / "results.csv"
    crawler.save_results(str(output_file))

    with open(output_file, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["URL", "Title", "Status Code", "Found On"]
    assert rows[1] == ["https://example.com", "Home", "200", ""]
    assert rows[2] == ["https://example.com/about", "About", "200", "https://example.com"]


def test_save_results_sanitizes_found_on(tmp_path):
    """Found On is a URL from the crawl and goes through the same CSV-injection guard."""
    crawler = WebsiteCrawler("example.com")
    crawler.results = [PageResult("https://example.com/x", "X", 200, found_on="=cmd|calc")]
    output_file = tmp_path / "results.csv"
    crawler.save_results(str(output_file))
    assert "'=cmd|calc" in output_file.read_text()


# --- Skipped rows in output (#14 part 2) ---

def test_skipped_rows_written_to_csv(tmp_path):
    """Depth-skipped rows appear in the CSV with an empty status."""
    crawler = WebsiteCrawler("example.com")
    crawler.results = [
        PageResult("https://example.com", "Home", 200),
        PageResult("https://example.com/deep", "skipped: max_depth", None,
                   found_on="https://example.com"),
    ]
    output_file = tmp_path / "results.csv"
    crawler.save_results(str(output_file))

    with open(output_file, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    assert rows[2] == ["https://example.com/deep", "skipped: max_depth", "",
                       "https://example.com"]


@responses.activate
def test_skipped_urls_do_not_count_as_visited():
    """Skipped rows are recorded but the URLs are never fetched."""
    crawler = WebsiteCrawler("example.com", delay=0)
    responses.add(responses.GET, 'https://example.com',
        body='<html><body><a href="/d1">1</a></body></html>', status=200)
    responses.add(responses.GET, 'https://example.com/d1',
        body='<html><body><a href="/d2">2</a></body></html>', status=200)

    crawler.crawl(recursive=True, max_depth=1)

    assert 'https://example.com/d2' not in crawler.visited_urls
    assert len(responses.calls) == 3  # robots.txt + 2 pages; /d2 never requested
