import time

import pytest

from collector.fetch_hn import fetch_hn

NOW = int(time.time())
FRESH = NOW - 3600
STALE = NOW - 90000


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def make_hit(oid, created_i, story_text=None, title="Title", url="https://x.com/a"):
    return {
        "objectID": oid,
        "title": title,
        "url": url,
        "author": "alice",
        "created_at_i": created_i,
        "points": 42,
        "num_comments": 7,
        "story_text": story_text,
    }


@pytest.fixture
def patch_get(monkeypatch):
    def install(responses_by_keyword):
        def fake_get(self, url, params=None, timeout=None):
            return FakeResponse({"hits": responses_by_keyword[params["query"]]})

        monkeypatch.setattr("requests.Session.get", fake_get)

    return install


def make_config(keywords, max_per_keyword=30):
    return {"hn": {"keywords": keywords, "max_per_keyword": max_per_keyword}}


def test_parses_hit_into_record(patch_get):
    patch_get({"kw": [make_hit("1001", FRESH)]})
    records = fetch_hn(make_config(["kw"]))
    assert len(records) == 1
    r = records[0]
    assert r.id == "hn-1001"
    assert r.source == "hn"
    assert r.title_en == "Title"
    assert r.url == "https://x.com/a"
    assert r.author == "alice"
    assert r.metrics == {"upvotes": 42, "comments": 7}
    assert r.ai is None
    assert r.created_at.timestamp() == pytest.approx(FRESH, abs=1)


def test_posts_older_than_24h_are_filtered(patch_get):
    patch_get({"kw": [make_hit("1", FRESH), make_hit("2", STALE)]})
    records = fetch_hn(make_config(["kw"]))
    assert [r.id for r in records] == ["hn-1"]


def test_zero_hits_returns_empty(patch_get):
    patch_get({"kw": []})
    assert fetch_hn(make_config(["kw"])) == []


def test_long_story_text_truncated_to_2000(patch_get):
    patch_get({"kw": [make_hit("9", FRESH, story_text="x" * 3000)]})
    records = fetch_hn(make_config(["kw"]))
    assert len(records[0].text_en) == 2000


def test_same_object_id_across_keywords_deduplicated(patch_get):
    patch_get({"a": [make_hit("42", FRESH)], "b": [make_hit("42", FRESH)]})
    records = fetch_hn(make_config(["a", "b"]))
    assert len(records) == 1
