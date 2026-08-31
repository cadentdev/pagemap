"""Persistent settings from an optional TOML config file (#17).

Location: $XDG_CONFIG_HOME/sitewalker/config.toml (default
~/.config/sitewalker/config.toml), overridable with --config.
Precedence is CLI flags > config file > built-in defaults.
"""

import logging
import os
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

# Recognized keys and the TOML type each must have
VALID_KEYS = {
    'output_dir': str,
    'page_extensions': list,
}


def default_config_path() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME', '~/.config')
    return Path(base).expanduser() / 'sitewalker' / 'config.toml'


def load_config(path: str | None = None) -> dict:
    """Load and validate the config file.

    An explicit path must exist; the default path is silently optional.
    Raises ValueError on a missing explicit path, invalid TOML, an
    unknown key (catches typos), or a wrong value type.
    """
    if path is not None:
        config_path = Path(path).expanduser()
        if not config_path.is_file():
            raise ValueError(f"Config file not found: {config_path}")
    else:
        config_path = default_config_path()
        if not config_path.is_file():
            return {}

    with open(config_path, 'rb') as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in {config_path}: {e}") from e

    unknown = data.keys() - VALID_KEYS.keys()
    if unknown:
        raise ValueError(
            f"Unknown config key(s) in {config_path}: {', '.join(sorted(unknown))}. "
            f"Recognized keys: {', '.join(sorted(VALID_KEYS))}")
    for key, expected in VALID_KEYS.items():
        if key in data and not isinstance(data[key], expected):
            raise ValueError(
                f"Config key {key!r} in {config_path} must be a "
                f"{'string' if expected is str else 'list of strings'}")

    if 'page_extensions' in data:
        if not all(isinstance(e, str) for e in data['page_extensions']):
            raise ValueError(
                f"Config key 'page_extensions' in {config_path} must be a list of strings")
        # Normalize: lowercase, no leading dot ("HTML", ".htm" -> "html", "htm")
        data['page_extensions'] = {e.lower().lstrip('.') for e in data['page_extensions']}

    logger.info(f"Loaded config from {config_path}")
    return data
