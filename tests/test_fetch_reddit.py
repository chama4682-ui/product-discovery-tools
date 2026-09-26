import time
from datetime import datetime, timezone

import pytest

from collector.fetch_reddit import fetch_reddit

NOW = int(time.time())
FRESH = NOW - 3600
STALE = NOW - 90000

UA = "windows:demand-radar:v1 (test)"


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def make_post(pid, created_utc, selftext=None, subreddit="SaaS", title="Title"):
    return {
        "name": f"t3_{pid}",
        "id": pid,
        "subreddit": subreddit,
        "title": title,
        "selftext": selftext or "",
        "permalink": f"/r/{subreddit}/comments/{pid}/x/",
        "author": "bob",
        "created_utc": created_utc,
        "ups": 55,
        "num_comments": 9,
    }


def install(monkeypatch, listings_by_sub):
    monkeypatch.setattr("requests.Session.post", lambda self, url, **kw: FakeResp({"access_token": "tok"}))

    def fake_get(self, url, params=None, headers=None, timeout=None):
        sub = url.split("/r/")[1].split("/")[0]
        return FakeResp({"data": {"children": [{"data": p} for p in listings_by_sub[sub]]}})

    monkeypatch.setattr("requests.Session.get", fake_get)


def make_config(subs=("SaaS",), max_per_sub=30):
    return {"reddit": {"subreddits": list(subs), "max_per_sub": max_per_sub}}


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "cid")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "csecret")


def test_parses_post_into_record(monkeypatch):
    install(monkeypatch, {"SaaS": [make_post("abc", FRESH)]})
    records = fetch_reddit(make_config())
    r = records[0]
    assert r.id == "reddit-t3_abc"
    assert r.source == "reddit"
    assert r.title_en == "Title"
    assert r.url == "https://www.reddit.com/r/SaaS/comments/abc/x/"
    assert r.author == "bob"
    assert r.metrics == {"upvotes": 55, "comments": 9}
    assert r.created_at.timestamp() == pytest.approx(FRESH, abs=1)


def test_old_posts_filtered(monkeypatch):
    install(monkeypatch, {"SaaS": [make_post("1", FRESH), make_post("2", STALE)]})
    assert [r.id for r in fetch_reddit(make_config())] == ["reddit-t3_1"]


def test_zero_posts_returns_empty(monkeypatch):
    install(monkeypatch, {"SaaS": []})
    assert fetch_reddit(make_config()) == []


def test_selftext_truncated(monkeypatch):
    install(monkeypatch, {"SaaS": [make_post("3", FRESH, selftext="y" * 3000)]})
    assert len(fetch_reddit(make_config())[0].text_en) == 2000


def test_same_post_across_subs_deduplicated(monkeypatch):
    install(monkeypatch, {"SaaS": [make_post("42", FRESH)], "startup": [make_post("42", FRESH, subreddit="startup")]})
    assert len(fetch_reddit(make_config(("SaaS", "startup")))) == 1


def test_missing_credentials_raise(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    with pytest.raises(Exception, match="REDDIT_CLIENT_ID"):
        fetch_reddit(make_config())
