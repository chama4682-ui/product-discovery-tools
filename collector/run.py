import argparse
import json
import os
from pathlib import Path

from collector import load_config
from collector.analyze import analyze_records
from collector.dedupe import merge_records
from collector.fetch_hn import fetch_hn
from collector.models import Record

_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = _ROOT / "data" / "opportunities.json"
DOTENV_FILE = _ROOT / ".env"


def load_env_secrets() -> None:
    if os.environ.get("AGNES_API_KEY") or not DOTENV_FILE.exists():
        return
    for line in DOTENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip().strip('"'), value.strip().strip('"'))


def main(dry_run: bool = False) -> int:
    config = load_config()

    existing: list[Record] = []
    if DATA_FILE.exists():
        existing = [Record.model_validate(r) for r in json.loads(DATA_FILE.read_text(encoding="utf-8"))]

    existing_ids = {r.id for r in existing}
    fetchers = {"hn": fetch_hn}
    new_records: list[Record] = []
    for source in config["enabled_sources"]:
        if source not in fetchers:
            raise ValueError(f"未知数据源: {source}")
        fetched = fetchers[source](config)
        fresh = [r for r in fetched if r.id not in existing_ids]
        print(f"{source}: 抓取 {len(fetched)} 条，新 {len(fresh)} 条")
        new_records.extend(fresh)

    if dry_run:
        print("dry-run：不分析不写文件")
        return 0

    if not new_records:
        print("无新记录，跳过分析")
        return 0

    analyzed = analyze_records(new_records, config)
    merged = merge_records(existing, analyzed, config["retention_days"])
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps([r.model_dump(mode="json") for r in merged], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"写入 {len(merged)} 条机会（新增 {len(analyzed)}）")
    return 0
