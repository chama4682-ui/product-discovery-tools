from datetime import datetime, timezone

import pytest

from collector.fetch_ph import fetch_ph

T = "2026-09-26T09:00:00Z"


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def make_node(pid, tagline="tag", description="desc", website=None):
    return {
        "id": pid,
        "name": "ProductX",
        "tagline": tagline,
        "description": description,
        "websiteUrl": website,
        "url": f"https://www.producthunt.com/posts/x-{pid}",
        "createdAt": T,
        "votesCount": 120,
        "commentsCount": 10,
    }


def install(monkeypatch, nodes):
    def fake_post(self, url, headers=None, json=None, timeout=None):
        return FakeResp({"data": {"posts": {"edges": [{"node": n} for n in nodes]}}})

    monkeypatch.setattr("requests.Session.post", fake_post)


CFG = {"ph": {"max_posts": 30}}


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("PH_TOKEN", "phtok")


def test_parses_post_into_record(monkeypatch):
    install(monkeypatch, [make_node("100")])
    r = fetch_ph(CFG)[0]
    assert r.id == "ph-100"
    assert r.source == "ph"
    assert r.title_en == "ProductX"
    assert r.text_en == "tag\ndesc"
    assert r.url == "https://www.producthunt.com/posts/x-100"
    assert r.metrics == {"upvotes": 120, "comments": 10}
    assert r.created_at == datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)


def test_website_url_preferred(monkeypatch):
    install(monkeypatch, [make_node("101", website="https://productx.dev")])
    assert fetch_ph(CFG)[0].url == "https://productx.dev"


def test_zero_posts_returns_empty(monkeypatch):
    install(monkeypatch, [])
    assert fetch_ph(CFG) == []


def test_long_text_truncated(monkeypatch):
    install(monkeypatch, [make_node("102", description="z" * 3000)])
    assert len(fetch_ph(CFG)[0].text_en) == 2000


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("PH_TOKEN", raising=False)
    with pytest.raises(Exception, match="PH_TOKEN"):
        fetch_ph(CFG)
