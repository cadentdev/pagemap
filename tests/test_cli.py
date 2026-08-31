import pytest
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime
from sitewalker.cli import main, setup_logging
import os
import argparse
import logging

@pytest.fixture
def reset_logging():
    """Reset logging configuration before and after each test"""
    logging.root.handlers = []
    logging.root.setLevel(logging.WARNING)
    yield
    logging.root.handlers = []
    logging.root.setLevel(logging.WARNING)

def test_main_with_no_arguments(capsys):
    """Test main function with no command line arguments"""
    with patch.object(sys, 'argv', ['sitewalker']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "usage: sitewalker" in captured.err
        assert "target" in captured.err

def test_main_with_domain():
    """Test main function with a valid domain argument"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=False, check_external=False, recursive=False, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
                mock_crawler.save_results.assert_called_once()

def test_main_with_full_url():
    """Test main function with a full URL (skips HTTPS probe)"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
        with patch.object(sys, 'argv', ['sitewalker', 'http://example.com']):
            main()

            mock_crawler.crawl.assert_called_once_with(collect_external=False, check_external=False, recursive=False, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
            mock_crawler.save_results.assert_called_once()

def test_main_bare_domain_https_fails(capsys, reset_logging):
    """Test that bare domain with HTTPS failure exits with helpful message"""
    import requests as req
    with patch('sitewalker.cli.requests.head', side_effect=req.ConnectionError("refused")):
        with patch.object(sys, 'argv', ['sitewalker', 'myserver.lan']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "sitewalker http://myserver.lan" in captured.err

def test_main_with_external_links():
    """Test main function with external links flag saves both internal and external CSVs"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-e']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=True, check_external=False, recursive=False, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
                mock_crawler.save_external_links_results.assert_called_once()
                mock_crawler.save_results.assert_called_once()

def test_main_with_recursive():
    """Test main function with recursive flag"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-r']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=False, check_external=False, recursive=True, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
                mock_crawler.save_results.assert_called_once()

def test_setup_logging_verbose(reset_logging):
    """Test logging setup in verbose mode"""
    setup_logging(verbose=True)
    assert logging.getLogger().level == logging.DEBUG

def test_setup_logging_normal(reset_logging):
    """Test logging setup in normal mode"""
    setup_logging(verbose=False)
    assert logging.getLogger().level == logging.INFO

def test_main_with_error(capsys, reset_logging):
    """Test main function when crawler encounters an error"""
    mock_crawler = MagicMock()
    test_error = Exception("Network error")
    mock_crawler.crawl.side_effect = test_error

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com']):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                captured = capsys.readouterr()
                assert "An error occurred: Network error" in captured.err

def test_main_with_all_options():
    """Test main function with all flags enabled"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-e', '-v', '-r']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=True, check_external=False, recursive=True, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
                mock_crawler.save_external_links_results.assert_called_once()
                mock_crawler.save_results.assert_called_once()


def test_main_with_check_external():
    """Test main function with --check-external flag"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-e', '--check-external']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=True, check_external=True, recursive=False, pages_only=False, max_pages=1000, max_depth=10, max_external_links=500, include_assets=False)
                mock_crawler.save_external_links_results.assert_called_once()
                mock_crawler.save_results.assert_called_once()


# --- Output path control (#16) and filename sanitization (#9) ---

from sitewalker.cli import sanitize_filename_component, resolve_output_paths


@pytest.mark.parametrize("raw,expected", [
    ("example.com", "example.com"),
    ("sub.example.co.uk", "sub.example.co.uk"),
    ("example.com:8080", "example.com_8080"),
    ("../../etc/passwd", "passwd"),
    ("..example.com", "example.com"),
    ("-rf", "rf"),
    ("bad\x00name.com", "bad_name.com"),
    ("~user/site", "site"),
    ("", "site"),
    ("!!!", "site"),
])
def test_sanitize_filename_component(raw, expected):
    assert sanitize_filename_component(raw) == expected


def test_sanitize_filename_component_truncates_long_names():
    long = "a" * 300 + ".com"
    result = sanitize_filename_component(long)
    assert len(result) == 100


def test_resolve_output_paths_default_is_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results, external = resolve_output_paths(None, None, "example.com", "2026-08-29T1200")
    assert results == tmp_path / "example.com_2026-08-29T1200.csv"
    assert external == tmp_path / "example.com_2026-08-29T1200_external_links.csv"


def test_resolve_output_paths_creates_output_dir(tmp_path):
    target = tmp_path / "nested" / "out"
    results, external = resolve_output_paths(str(target), None, "example.com", "T")
    assert target.is_dir()
    assert results.parent == target
    assert external.parent == target


def test_resolve_output_paths_rejects_file_as_dir(tmp_path):
    f = tmp_path / "afile"
    f.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        resolve_output_paths(str(f), None, "example.com", "T")


def test_resolve_output_paths_rejects_unwritable_dir(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        if os.access(ro, os.W_OK):
            pytest.skip("running as a user that ignores directory permissions")
        with pytest.raises(ValueError, match="not writable"):
            resolve_output_paths(str(ro), None, "example.com", "T")
    finally:
        ro.chmod(0o700)


def test_resolve_output_paths_custom_filename(tmp_path):
    results, external = resolve_output_paths(str(tmp_path), "audit", "example.com", "T")
    assert results == tmp_path / "audit.csv"
    assert external == tmp_path / "audit_external_links.csv"


def test_resolve_output_paths_custom_filename_strips_csv_suffix(tmp_path):
    results, external = resolve_output_paths(str(tmp_path), "audit.CSV", "example.com", "T")
    assert results == tmp_path / "audit.csv"
    assert external == tmp_path / "audit_external_links.csv"


@pytest.mark.parametrize("bad", [
    "/abs/path.csv",
    "sub/dir.csv",
    "..\\up.csv",
    "../escape.csv",
    "..",
])
def test_resolve_output_paths_rejects_path_in_filename(tmp_path, bad):
    with pytest.raises(ValueError, match="bare filename"):
        resolve_output_paths(str(tmp_path), bad, "example.com", "T")


def test_resolve_output_paths_rejects_empty_filename(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        resolve_output_paths(str(tmp_path), ".csv", "example.com", "T")


def test_main_with_output_dir_and_filename(tmp_path):
    """--output-dir and --output-filename flow through to save calls."""
    mock_crawler = MagicMock()
    out = tmp_path / "results"
    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-e',
                                            '--output-dir', str(out),
                                            '--output-filename', 'audit']):
                main()
    mock_crawler.save_results.assert_called_once_with(str(out / "audit.csv"))
    mock_crawler.save_external_links_results.assert_called_once_with(
        str(out / "audit_external_links.csv"))


def test_main_bad_output_dir_fails_before_crawl(tmp_path, capsys, reset_logging):
    """A bad --output-dir exits 1 without starting the crawl."""
    f = tmp_path / "afile"
    f.write_text("x")
    mock_crawler = MagicMock()
    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '--output-dir', str(f)]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
    assert exc_info.value.code == 1
    mock_crawler.crawl.assert_not_called()
    assert "not a directory" in capsys.readouterr().err


# --- --broken-only summary (#14) ---

from sitewalker.cli import print_broken_summary
from sitewalker.crawler import PageResult


def _crawler_with(results, external_checked=()):
    c = MagicMock()
    c.results = results
    c.external_links_checked = list(external_checked)
    return c


def test_print_broken_summary_lists_non_200_with_referrer(capsys):
    crawler = _crawler_with([
        PageResult("https://example.com", "Home", 200),
        PageResult("https://example.com/missing", "Error", 404, found_on="https://example.com"),
        PageResult("https://example.com/deep", "skipped: max_depth", None,
                   found_on="https://example.com"),
    ], external_checked=[("https://gone.com", 404), ("https://ok.com", 200)])

    print_broken_summary(crawler)
    out = capsys.readouterr().out
    assert "Broken internal links (1):" in out
    assert "404  https://example.com/missing  (found on: https://example.com)" in out
    # skipped rows and 200s are not broken
    assert "skipped" not in out
    assert "https://example.com/deep" not in out
    assert "Broken external links (1):" in out
    assert "404  https://gone.com" in out
    assert "https://ok.com" not in out


def test_print_broken_summary_all_ok(capsys):
    crawler = _crawler_with([PageResult("https://example.com", "Home", 200)])
    print_broken_summary(crawler)
    assert capsys.readouterr().out == "No broken links found.\n"


def test_main_broken_only_flag(capsys):
    """--broken-only prints the summary after the crawl."""
    mock_crawler = MagicMock()
    mock_crawler.results = [
        PageResult("https://example.com/bad", "Error", 500, found_on="https://example.com"),
    ]
    mock_crawler.external_links_checked = []
    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '--broken-only']):
                main()
    out = capsys.readouterr().out
    assert "500  https://example.com/bad" in out


def test_main_with_assets_flag():
    """-a passes include_assets=True to crawl."""
    mock_crawler = MagicMock()
    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-a']):
                main()
    assert mock_crawler.crawl.call_args.kwargs['include_assets'] is True
