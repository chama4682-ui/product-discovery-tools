from datetime import datetime, timezone

from collector.models import Record


def merge_records(existing: list[Record], new: list[Record], retention_days: int) -> list[Record]:
    by_id = {r.id: r for r in existing}
    for r in new:
        if r.id not in by_id:
            by_id[r.id] = r
    cutoff = datetime.now(timezone.utc).toordinal() - retention_days
    kept = [r for r in by_id.values() if r.created_at.toordinal() >= cutoff]
    kept.sort(key=lambda r: r.created_at, reverse=True)
    return kept
