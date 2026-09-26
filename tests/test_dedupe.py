from datetime import datetime, timedelta, timezone

from collector.dedupe import merge_records
from collector.models import AIResult, Record


def make_record(rid, created, days_old=0, ai=True):
    return Record(
        id=rid,
        source="hn",
        title_en="t",
        title_zh="",
        text_en="",
        summary_zh="",
        url="https://example.com",
        author="a",
        created_at=created,
        captured_at=created,
        metrics={"upvotes": 1, "comments": 0},
        ai=AIResult(
            is_demand=True, demand_zh="d", category="c", score=5,
            willingness_to_pay="weak", reason_zh="r",
        ) if ai else None,
    )


NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def test_duplicate_id_keeps_existing_record():
    old = make_record("hn-1", NOW)
    new = make_record("hn-1", NOW)
    merged = merge_records([old], [new], retention_days=90)
    assert len(merged) == 1
    assert merged[0] is old


def test_sorted_by_created_at_desc():
    a = make_record("hn-a", NOW - timedelta(days=2))
    b = make_record("hn-b", NOW)
    c = make_record("hn-c", NOW - timedelta(days=1))
    merged = merge_records([a, b], [c], retention_days=90)
    assert [r.id for r in merged] == ["hn-b", "hn-c", "hn-a"]


def test_records_older_than_retention_are_dropped():
    fresh = make_record("hn-fresh", NOW)
    stale = make_record("hn-stale", NOW - timedelta(days=91))
    merged = merge_records([], [fresh, stale], retention_days=90)
    assert [r.id for r in merged] == ["hn-fresh"]


def test_empty_inputs_return_empty():
    assert merge_records([], [], retention_days=90) == []
