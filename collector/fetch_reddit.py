import os
import time
from datetime import datetime, timezone

import requests

from collector.models import Record

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_LISTING_URL = "https://oauth.reddit.com/r/{sub}/hot"
_UA = "windows:demand-radar:v1.0 (by /u/chama4682-ui)"
_TEXT_LIMIT = 2000


def fetch_reddit(config: dict, session: requests.Session | None = None) -> list[Record]:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id:
        raise RuntimeError("缺少环境变量 REDDIT_CLIENT_ID（Reddit 应用 client_id）")
    if not client_secret:
        raise RuntimeError("缺少环境变量 REDDIT_CLIENT_SECRET（Reddit 应用 secret）")

    reddit = config["reddit"]
    max_per_sub = reddit["max_per_sub"]
    cutoff = int(time.time()) - 86400
    session = session or requests.Session()

    token_resp = session.post(
        _TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _UA},
        timeout=30,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["access_token"]

    def request_headers():
        return {"Authorization": f"Bearer {token}", "User-Agent": _UA}

    by_id: dict[str, dict] = {}
    for sub in reddit["subreddits"]:
        resp = session.get(
            _LISTING_URL.format(sub=sub),
            params={"limit": max_per_sub},
            headers=request_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        for child in resp.json().get("data", {}).get("children", []):
            post = child["data"]
            if int(post["created_utc"]) > cutoff:
                by_id[post["name"]] = post

    now = datetime.now(timezone.utc)
    return [
        Record(
            id=f"reddit-{name}",
            source="reddit",
            title_en=post.get("title") or "",
            text_en=(post.get("selftext") or "")[:_TEXT_LIMIT],
            url="https://www.reddit.com" + (post.get("permalink") or ""),
            author=post.get("author") or "",
            created_at=datetime.fromtimestamp(int(post["created_utc"]), tz=timezone.utc),
            captured_at=now,
            metrics={"upvotes": post.get("ups") or 0, "comments": post.get("num_comments") or 0},
        )
        for name, post in by_id.items()
    ]
