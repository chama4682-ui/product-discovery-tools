import json
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config(path=None):
    with open(path or _DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)
