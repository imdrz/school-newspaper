from __future__ import annotations
import secrets, time
from . import config

# code -> {"school", "email", "expires_at"}.
# In memory: simple, but cleared on restart and not shared across processes.
# Moving this to a database is a stretch goal.
_pending: dict[str, dict] = {}

def issue_code(school: str, email: str) -> str:
    """Create a fresh code for (school, email), store it, and return it."""
    code = secrets.token_urlsafe(24)
    _pending[code] = {
        "school": school,
        "email": email.strip().lower(),
        "expires_at": time.time() + config.CODE_TTL_SECONDS,
    }
    return code

def consume_code(school: str, code: str) -> str | None:
    """If `code` is valid for `school`, return the email and burn the code.
    Otherwise return None. 'Valid' = exists, right school, not expired."""
    entry = _pending.get(code)
    if not entry:
        return None
    if entry["school"] != school:
        return None
    if time.time() > entry["expires_at"]:
        _pending.pop(code, None)
        return None
    _pending.pop(code)
    return entry["email"]
