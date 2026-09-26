import os
from datetime import datetime, timezone

import requests

from collector.models import Record

_API = "https://api.producthunt.com/v2/api/graphql"
_TEXT_LIMIT = 2000

_QUERY = """
query($first: Int!) {
  posts(first: $first, order: NEWEST) {
    edges { node {
      id name tagline description websiteUrl url createdAt votesCount commentsCount
    } }
  }
}
"""


def fetch_ph(config: dict, session: requests.Session | None = None) -> list[Record]:
    token = os.environ.get("PH_TOKEN")
    if not token:
        raise RuntimeError("缺少环境变量 PH_TOKEN（Product Hunt developer token）")

    max_posts = config["ph"]["max_posts"]
    session = session or requests.Session()
    resp = session.post(
        _API,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": _QUERY, "variables": {"first": max_posts}},
        timeout=30,
    )
    resp.raise_for_status()
    edges = resp.json()["data"]["posts"]["edges"]

    now = datetime.now(timezone.utc)
    records = []
    for edge in edges:
        node = edge["node"]
        text = f"{node.get('tagline') or ''}\n{node.get('description') or ''}"
        records.append(Record(
            id=f"ph-{node['id']}",
            source="ph",
            title_en=node.get("name") or "",
            text_en=text[:_TEXT_LIMIT],
            url=node.get("websiteUrl") or node.get("url") or "",
            author="",
            created_at=datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00")),
            captured_at=now,
            metrics={"upvotes": node.get("votesCount") or 0, "comments": node.get("commentsCount") or 0},
        ))
    return records
