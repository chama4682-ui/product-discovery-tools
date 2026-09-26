import json
from datetime import datetime, timezone

import pytest

from collector import run
from collector.models import AIResult, Record

T = datetime(2026, 9, 26, tzinfo=timezone.utc)


def make_record(rid, with_ai=False):
    return Record(
        id=rid, source="hn", title_en="t", title_zh="标题" if with_ai else "",
        text_en="x", summary_zh="摘要" if with_ai else "",
        url="https://x.com", author="a", created_at=T, captured_at=T,
        ai=AIResult(
            is_demand=True, demand_zh="d", category="dev", score=6,
            willingness_to_pay="weak", reason_zh="r",
        ) if with_ai else None,
    )


@pytest.fixture
def data_file(tmp_path, monkeypatch):
    f = tmp_path / "opportunities.json"
    monkeypatch.setattr(run, "DATA_FILE", f)
    return f


def fake_analyze(monkeypatch, seen_ids=None):
    def _analyze(records, config):
        if seen_ids is not None:
            seen_ids.extend(r.id for r in records)
        return [make_record(r.id, with_ai=True) for r in records]

    monkeypatch.setattr(run, "analyze_records", _analyze)


def fake_fetch(monkeypatch, records):
    monkeypatch.setattr(run, "fetch_hn", lambda config, session=None: records)


def test_new_data_merged_and_written(data_file, monkeypatch):
    data_file.write_text(
        json.dumps([json.loads(make_record("hn-1", with_ai=True).model_dump_json())],
                   ensure_ascii=False),
        encoding="utf-8",
    )
    fake_fetch(monkeypatch, [make_record("hn-1"), make_record("hn-2")])
    fake_analyze(monkeypatch)
    assert run.main() == 0
    saved = json.loads(data_file.read_text(encoding="utf-8"))
    assert len(saved) == 2
    assert {r["id"] for r in saved} == {"hn-1", "hn-2"}


def test_existing_ids_not_sent_to_analysis(data_file, monkeypatch):
    data_file.write_text(
        json.dumps([json.loads(make_record("hn-1", with_ai=True).model_dump_json())],
                   ensure_ascii=False),
        encoding="utf-8",
    )
    fake_fetch(monkeypatch, [make_record("hn-1"), make_record("hn-2")])
    seen = []
    fake_analyze(monkeypatch, seen)
    run.main()
    assert seen == ["hn-2"]


def test_no_new_records_skips_write(data_file, monkeypatch):
    fake_fetch(monkeypatch, [])
    fake_analyze(monkeypatch)
    assert run.main() == 0
    assert not data_file.exists()


def test_corrupted_json_raises(data_file, monkeypatch):
    data_file.write_text("{broken", encoding="utf-8")
    fake_fetch(monkeypatch, [])
    with pytest.raises(json.JSONDecodeError):
        run.main()


def test_dry_run_does_not_write_or_analyze(data_file, monkeypatch):
    called = []
    monkeypatch.setattr(run, "analyze_records", lambda r, c: called.append(1))
    fake_fetch(monkeypatch, [make_record("hn-1")])
    assert run.main(dry_run=True) == 0
    assert not data_file.exists()
    assert called == []


def test_load_env_secrets_reads_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('AGNES_API_KEY="abc123"\n', encoding="utf-8")
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    monkeypatch.setattr(run, "DOTENV_FILE", env_file)
    run.load_env_secrets()
    import os

    assert os.environ["AGNES_API_KEY"] == "abc123"
