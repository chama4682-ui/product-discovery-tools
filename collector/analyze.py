import json
import os

import requests

from collector.models import AIResult, Record

_BASE_URL = "https://apihub.agnes-ai.com/v1"

_SYSTEM_PROMPT = (
    "你是产品机会分析员。对给出的每条海外社区帖子，判断它是否表达了真实的需求或痛点，"
    "并输出 JSON：{\"items\": [{\"id\": 原样返回的帖子id, \"is_demand\": 布尔, "
    "\"demand_zh\": \"一句话需求描述（中文）\", \"category\": \"类别英文小写如 dev-tools/health/finance\", "
    "\"score\": 0-10 的机会评分（痛点强度+付费意愿+受众广度综合）, "
    "\"willingness_to_pay\": \"strong|weak|none\", \"reason_zh\": \"评分理由（中文）\", "
    "\"title_zh\": \"标题的中文翻译\", \"summary_zh\": \"内容的中文摘要\"}]}。"
    "items 必须与输入帖子一一对应、id 原样返回，所有文字字段用中文，不输出 JSON 以外内容。"
)


_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "is_demand": {"type": "boolean"},
        "demand_zh": {"type": "string"},
        "category": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 10},
        "willingness_to_pay": {"type": "string", "enum": ["strong", "weak", "none"]},
        "reason_zh": {"type": "string"},
        "title_zh": {"type": "string"},
        "summary_zh": {"type": "string"},
    },
    "required": ["id", "is_demand", "demand_zh", "category", "score",
                 "willingness_to_pay", "reason_zh", "title_zh", "summary_zh"],
    "additionalProperties": False,
}

_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "demand_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"items": {"type": "array", "items": _ITEM_SCHEMA}},
            "required": ["items"],
            "additionalProperties": False,
        },
    },
}


def _analyze_batch(batch: list[Record], api_key: str, model: str) -> None:
    posts = [
        {
            "id": r.id,
            "title": r.title_en,
            "text": r.text_en,
            "upvotes": r.metrics.get("upvotes", 0),
            "comments": r.metrics.get("comments", 0),
        }
        for r in batch
    ]
    resp = requests.post(
        f"{_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "response_format": _RESPONSE_FORMAT,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(posts, ensure_ascii=False)},
            ],
        },
        timeout=300,
    )
    resp.raise_for_status()
    items = json.loads(resp.json()["choices"][0]["message"]["content"])["items"]
    by_id = {r.id: r for r in batch}
    seen = set()
    for item in items:
        if item["id"] not in by_id:
            raise ValueError(f"LLM 返回未知 id: {item['id']}")
        if item["id"] in seen:
            raise ValueError(f"LLM 重复返回 id: {item['id']}")
        seen.add(item["id"])
        r = by_id[item["id"]]
        r.title_zh = item["title_zh"]
        r.summary_zh = item["summary_zh"]
        r.ai = AIResult(
            is_demand=item["is_demand"],
            demand_zh=item["demand_zh"],
            category=item["category"],
            score=int(item["score"]),
            willingness_to_pay=item["willingness_to_pay"],
            reason_zh=item["reason_zh"],
        )
    missing = by_id.keys() - seen
    if missing:
        raise ValueError(f"LLM 漏掉 id: {sorted(missing)}")


def analyze_records(records: list[Record], config: dict) -> list[Record]:
    api_key = os.environ.get("AGNES_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 AGNES_API_KEY")
    batch_size = config["batch_size"]
    for i in range(0, len(records), batch_size):
        _analyze_batch(records[i : i + batch_size], api_key, config["model"])
    return records
