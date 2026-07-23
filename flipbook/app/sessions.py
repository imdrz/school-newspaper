from __future__ import annotations
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from . import config

COOKIE_NAME = "admin_session"
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="admin-session")

def create_session(school: str, email: str) -> str:
    """Return a signed token proving 'email is an admin of this school'."""
    return _serializer.dumps({"school": school, "email": email})

def read_session(token: str) -> dict | None:
    """Return the payload if the token is validly signed and not expired."""
    try:
        return _serializer.loads(token, max_age=config.SESSION_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
