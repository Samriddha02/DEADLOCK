from __future__ import annotations

import datetime
from typing import Any


def parse_timestamp(value: Any) -> datetime.datetime | None:
    """
    Parse ISO-like timestamp strings or date values deterministically.
    Returns timezone-naive UTC datetime for consistent comparison.
    """
    if not value or not isinstance(value, (str, int, float)):
        return None

    str_val = str(value).strip()
    if not str_val:
        return None

    str_val = str_val.replace("Z", "+00:00")

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(str_val, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue

    try:
        dt = datetime.datetime.fromisoformat(str_val)
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def classify_entity_state(entity: dict[str, Any], entity_type: str) -> str:
    """
    Classify entity state into:
    - ACTIVE: Currently ongoing, unresolved, or open.
    - HISTORICAL: Successfully completed, closed, merged, or past.
    - STALE: Inactive for a long period or superseded by newer work.
    - UNKNOWN: Incomplete information.
    """
    if not isinstance(entity, dict):
        return "UNKNOWN"

    raw_status = str(entity.get("status") or entity.get("state") or "").strip().lower()
    entity_type = entity_type.lower()

    if entity_type in {"pull_request", "pr"}:
        if raw_status in {"merged", "closed"}:
            return "HISTORICAL"
        if bool(entity.get("merged_at")) or bool(entity.get("merged")):
            return "HISTORICAL"
        if raw_status in {"open", "draft", "in_review", "review_requested"}:
            return "ACTIVE"
        if raw_status in {"abandoned", "stale"}:
            return "STALE"

    elif entity_type in {"issue", "task"}:
        if raw_status in {"closed", "completed", "done", "resolved"}:
            return "HISTORICAL"
        if bool(entity.get("closed_at")):
            return "HISTORICAL"
        if raw_status in {"open", "in_progress", "todo", "blocked"}:
            return "ACTIVE"

    elif entity_type in {"deployment", "deploy"}:
        if raw_status in {"success", "completed", "deployed", "passed"}:
            return "HISTORICAL"
        if raw_status in {"pending", "running", "in_progress", "queued", "blocked", "failed"}:
            return "ACTIVE"

    elif entity_type in {"deadline", "milestone"}:
        due_str = entity.get("due_date") or entity.get("due_at") or entity.get("due_on")
        due_dt = parse_timestamp(due_str)
        if due_dt:
            now = datetime.datetime(2026, 9, 18, 0, 0, 0)
            if due_dt < now:
                return "HISTORICAL"
            return "ACTIVE"
        if raw_status in {"closed", "reached", "completed"}:
            return "HISTORICAL"
        return "ACTIVE"

    return "ACTIVE" if raw_status in {"open", "active", "pending"} else "UNKNOWN"


def validate_temporal_sequence(events: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """
    Validate chronological consistency among connected events.
    Returns (is_valid, list_of_inconsistencies).
    """
    inconsistencies: list[str] = []

    for event in events:
        entity_type = event.get("type", "").lower()
        created_at = parse_timestamp(event.get("created_at") or event.get("timestamp"))
        closed_at = parse_timestamp(event.get("closed_at") or event.get("merged_at") or event.get("completed_at"))

        # Check 1: Entity closed before created
        if created_at and closed_at and closed_at < created_at:
            inconsistencies.append(
                f"{entity_type} {event.get('id', '')} closed/merged ({closed_at}) before created ({created_at})"
            )

        # Check 2: Reviews timestamp vs PR created timestamp
        reviews = event.get("reviews", [])
        if isinstance(reviews, list) and created_at:
            for rev in reviews:
                if isinstance(rev, dict):
                    rev_time = parse_timestamp(rev.get("submitted_at") or rev.get("created_at") or rev.get("timestamp"))
                    if rev_time and rev_time < created_at:
                        inconsistencies.append(
                            f"Review on {event.get('id', '')} submitted ({rev_time}) before PR was created ({created_at})"
                        )

    is_valid = len(inconsistencies) == 0
    return is_valid, inconsistencies


def check_contradictory_evidence(
    root_entity: dict[str, Any],
    related_entities: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    Check if newer or higher-precedence evidence contradicts the active risk hypothesis.
    Returns (has_contradiction, explanation).
    """
    if not root_entity:
        return False, ""

    root_id = str(root_entity.get("id", root_entity.get("number", "")))

    # Contradiction A: PR has blocking comment, but a newer review approved it
    reviews = root_entity.get("reviews", [])
    if isinstance(reviews, list) and len(reviews) > 1:
        def _sort_key(r: dict) -> datetime.datetime:
            return parse_timestamp(r.get("submitted_at") or r.get("created_at")) or datetime.datetime.min

        sorted_reviews = sorted([r for r in reviews if isinstance(r, dict)], key=_sort_key)
        if sorted_reviews:
            latest = sorted_reviews[-1]
            latest_state = str(latest.get("state") or latest.get("status") or "").upper()
            if latest_state in {"APPROVED", "PASSED"}:
                earlier_blocking = any(
                    str(r.get("state") or r.get("status") or "").upper() in {"CHANGES_REQUESTED", "BLOCKED"}
                    for r in sorted_reviews[:-1]
                )
                if earlier_blocking:
                    return True, f"Earlier blocking reviews on {root_id} superseded by newer approval review ({latest.get('id', '')})"

    # Contradiction B: Root PR is open, but newer related entity shows migration completed
    for rel in related_entities:
        if isinstance(rel, dict):
            rel_type = str(rel.get("type", "")).lower()
            rel_status = str(rel.get("status") or rel.get("state") or "").lower()
            if rel_type in {"issue", "pr"} and rel_status in {"closed", "merged", "completed"}:
                if rel.get("resolved_by") and rel.get("resolved_by") != root_id:
                    return True, f"Target dependency {rel.get('id')} was already resolved by {rel.get('resolved_by')}"

    return False, ""


def deduplicate_evidence(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate evidence items by structured key to prevent artificial confidence inflation.
    """
    if not evidence_list or not isinstance(evidence_list, list):
        return []

    seen = set()
    deduped = []

    for item in evidence_list:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("type", "")),
            str(item.get("id", "")),
            str(item.get("detail", item.get("title", item.get("reason", "")))),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


def calculate_bounded_confidence(
    base_confidence: float,
    evidence: list[dict[str, Any]],
    contradictions: list[str] | None = None,
    has_temporal_inconsistency: bool = False,
) -> float:
    """
    Calculate confidence deterministically strictly bounded within [0.0, 1.0].
    Penalizes contradictions and temporal inconsistencies.
    """
    if contradictions or has_temporal_inconsistency:
        return 0.0

    unique_evidence = deduplicate_evidence(evidence)
    evidence_factor = min(0.2, len(unique_evidence) * 0.04)

    conf = base_confidence + evidence_factor
    return max(0.0, min(1.0, round(conf, 2)))
