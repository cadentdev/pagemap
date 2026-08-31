"""Tests for the TOML config file (#17)."""
import pytest
from sitewalker.config import load_config, default_config_path


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the default config location at an empty temp dir."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))
    return tmp_path


def write_config(tmp_path, content):
    p = tmp_path / "config.toml"
    p.write_text(content)
    return str(p)


def test_default_path_honors_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', '/custom/cfg')
    assert str(default_config_path()) == '/custom/cfg/sitewalker/config.toml'


def test_missing_default_config_returns_empty():
    assert load_config(None) == {}


def test_default_path_is_read_when_present(tmp_path, monkeypatch):
    cfg_dir = tmp_path / 'xdg' / 'sitewalker'
    cfg_dir.mkdir(parents=True)
    (cfg_dir / 'config.toml').write_text('output_dir = "/tmp/crawls"\n')
    assert load_config(None) == {'output_dir': '/tmp/crawls'}


def test_missing_explicit_config_errors(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_config(str(tmp_path / "nope.toml"))


def test_valid_config(tmp_path):
    path = write_config(tmp_path, 'output_dir = "~/crawls"\n'
                                  'page_extensions = ["html", ".HTM", "cfm"]\n')
    config = load_config(path)
    assert config['output_dir'] == '~/crawls'
    assert config['page_extensions'] == {'html', 'htm', 'cfm'}


def test_unknown_key_errors(tmp_path):
    path = write_config(tmp_path, 'output_dri = "/tmp"\n')
    with pytest.raises(ValueError, match="Unknown config key.*output_dri.*Recognized"):
        load_config(path)


def test_invalid_toml_errors(tmp_path):
    path = write_config(tmp_path, 'output_dir = [unclosed\n')
    with pytest.raises(ValueError, match="Invalid TOML"):
        load_config(path)


@pytest.mark.parametrize("content,key", [
    ('output_dir = 3\n', 'output_dir'),
    ('page_extensions = "html"\n', 'page_extensions'),
    ('page_extensions = ["html", 7]\n', 'page_extensions'),
])
def test_wrong_type_errors(tmp_path, content, key):
    path = write_config(tmp_path, content)
    with pytest.raises(ValueError, match=key):
        load_config(path)
