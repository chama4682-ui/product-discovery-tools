import time
from datetime import datetime, timezone

import requests

from collector.models import Record

_API = "https://hn.algolia.com/api/v1/search_by_date"
_TEXT_LIMIT = 2000


def fetch_hn(config: dict, session: requests.Session | None = None) -> list[Record]:
    hn = config["hn"]
    max_per_keyword = hn["max_per_keyword"]
    cutoff = int(time.time()) - 86400
    session = session or requests.Session()

    by_id: dict[str, dict] = {}
    for keyword in hn["keywords"]:
        resp = session.get(
            _API,
            params={
                "query": keyword,
                "tags": "story",
                "hitsPerPage": max_per_keyword,
                "numericFilters": f"created_at_i>{cutoff}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        for hit in resp.json().get("hits", []):
            if int(hit["created_at_i"]) > cutoff:
                by_id[hit["objectID"]] = hit

    now = datetime.now(timezone.utc)
    return [
        Record(
            id=f"hn-{oid}",
            source="hn",
            title_en=hit.get("title") or "",
            text_en=(hit.get("story_text") or "")[:_TEXT_LIMIT],
            url=hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
            author=hit.get("author") or "",
            created_at=datetime.fromtimestamp(int(hit["created_at_i"]), tz=timezone.utc),
            captured_at=now,
            metrics={"upvotes": hit.get("points") or 0, "comments": hit.get("num_comments") or 0},
        )
        for oid, hit in by_id.items()
    ]
