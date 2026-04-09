"""sitewalker — Crawl a website and create a structured map of its pages."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("sitewalker")
except PackageNotFoundError:
    __version__ = "dev"
