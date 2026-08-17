from __future__ import annotations
import json
import uuid
from pathlib import Path

from fastapi import Request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from . import config

# Anonymous visitor cookie: a signed random id, minted on first edition open,
# used only to count *unique* viewers. Mirrors the session cookie in sessions.py.
VISITOR_COOKIE = "flipbook_vid"
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="visitor")


# ---- per-edition stats --------------------------------------------------
# One JSON file per edition, OUTSIDE DATA_DIR so the visitor ids it holds are
# never reachable through the public /data mount:
#   {"total": <every-open counter>, "visitors": [<vid>, ...]}

def _stats_path(school: str, edition_id: str) -> Path:
    return config.ANALYTICS_DIR / school / f"{edition_id}.json"


def read_stats(school: str, edition_id: str) -> dict:
    path = _stats_path(school, edition_id)
    if not path.exists():
        return {"total": 0, "visitors": []}
    return json.loads(path.read_text())


def record_view(school: str, edition_id: str, visitor_id: str) -> None:
    """Count one open (total += 1) and remember the visitor for unique counts."""
    stats = read_stats(school, edition_id)
    stats["total"] = stats.get("total", 0) + 1
    if visitor_id not in stats["visitors"]:
        stats["visitors"].append(visitor_id)
    path = _stats_path(school, edition_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2))


def view_count(school: str, edition_id: str) -> int:
    return read_stats(school, edition_id).get("total", 0)


def unique_count(school: str, edition_id: str) -> int:
    return len(read_stats(school, edition_id).get("visitors", []))


# ---- visitor cookie -----------------------------------------------------

def read_visitor_id(request: Request) -> str | None:
    """Return the visitor id from a validly signed cookie, else None."""
    token = request.cookies.get(VISITOR_COOKIE)
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=config.VISITOR_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def mint_visitor_id() -> tuple[str, str]:
    """Return (visitor_id, signed_cookie_token) for a brand-new visitor."""
    vid = uuid.uuid4().hex
    return vid, _serializer.dumps(vid)
