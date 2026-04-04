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

                mock_crawler.crawl.assert_called_once_with(recursive=False, pages_only=False, max_pages=1000, max_depth=10)
                mock_crawler.save_results.assert_called_once()

def test_main_with_full_url():
    """Test main function with a full URL (skips HTTPS probe)"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
        with patch.object(sys, 'argv', ['sitewalker', 'http://example.com']):
            main()

            mock_crawler.crawl.assert_called_once_with(recursive=False, pages_only=False, max_pages=1000, max_depth=10)
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
    """Test main function with external links flag"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-e']):
                main()

                mock_crawler.crawl.assert_called_once_with(collect_external=True, recursive=False, pages_only=False, max_pages=1000, max_depth=10)
                mock_crawler.save_external_links_results.assert_called_once()
                assert not mock_crawler.save_results.called

def test_main_with_recursive():
    """Test main function with recursive flag"""
    mock_crawler = MagicMock()

    with patch('sitewalker.cli.requests.head'):
        with patch('sitewalker.cli.WebsiteCrawler', return_value=mock_crawler):
            with patch.object(sys, 'argv', ['sitewalker', 'example.com', '-r']):
                main()

                mock_crawler.crawl.assert_called_once_with(recursive=True, pages_only=False, max_pages=1000, max_depth=10)
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

                mock_crawler.crawl.assert_called_once_with(collect_external=True, recursive=True, pages_only=False, max_pages=1000, max_depth=10)
                mock_crawler.save_external_links_results.assert_called_once()
                assert not mock_crawler.save_results.called
