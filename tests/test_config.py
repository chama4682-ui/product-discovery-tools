import pytest

from collector import load_config


def test_load_config_returns_defaults():
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert cfg["enabled_sources"] == ["hn"]
    assert cfg["batch_size"] == 25
    assert cfg["model"] == "agnes-3.0-flash"
    assert cfg["retention_days"] == 90
    assert cfg["hn"]["max_per_keyword"] == 30


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.json")
