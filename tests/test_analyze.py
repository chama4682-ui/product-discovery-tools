import json

import pytest

from collector.analyze import analyze_records
from collector.models import Record
from datetime import datetime, timezone

T = datetime(2026, 9, 26, tzinfo=timezone.utc)


def make_record(i):
    return Record(
        id=f"hn-{i}", source="hn", title_en=f"title {i}",
        text_en=f"text {i}", url="https://x.com", author="a",
        created_at=T, captured_at=T,
    )


class FakeResp:
    def __init__(self, content):
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}

    def raise_for_status(self):
        pass


def ok_content(ids):
    items = [
        {
            "id": rid, "is_demand": True, "demand_zh": "需求", "category": "dev",
            "score": 7, "willingness_to_pay": "weak", "reason_zh": "理由",
            "title_zh": f"标题{rid}", "summary_zh": "摘要",
        }
        for rid in ids
    ]
    return json.dumps({"items": items}, ensure_ascii=False)


def install_post(monkeypatch, content_for):
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        body = json.loads(kwargs["json"]["messages"][1]["content"])
        ids = [p["id"] for p in body]
        return FakeResp(content_for(ids))

    monkeypatch.setattr("requests.post", fake_post)
    return calls


CFG = {"model": "Agnes 3.0 Flash", "batch_size": 25}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")


def test_batches_60_records_into_3_calls(monkeypatch):
    records = [make_record(i) for i in range(60)]
    calls = install_post(monkeypatch, ok_content)
    analyze_records(records, CFG)
    assert calls["n"] == 3


def test_fills_ai_and_chinese_fields(monkeypatch):
    records = [make_record(1)]
    install_post(monkeypatch, ok_content)
    out = analyze_records(records, CFG)
    r = out[0]
    assert r.title_zh == "标题hn-1"
    assert r.summary_zh == "摘要"
    assert r.ai is not None
    assert r.ai.score == 7
    assert r.ai.willingness_to_pay == "weak"


def test_missing_id_in_response_raises(monkeypatch):
    records = [make_record(1), make_record(2)]

    def bad(ids):
        return ok_content(ids[:1])

    install_post(monkeypatch, bad)
    with pytest.raises(ValueError):
        analyze_records(records, CFG)


def test_unknown_id_in_response_raises(monkeypatch):
    records = [make_record(1)]

    def bad(ids):
        return ok_content(["hn-999"])

    install_post(monkeypatch, bad)
    with pytest.raises(ValueError):
        analyze_records(records, CFG)


def test_missing_api_key_raises_with_name(monkeypatch):
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    with pytest.raises(Exception, match="AGNES_API_KEY"):
        analyze_records([make_record(1)], CFG)
