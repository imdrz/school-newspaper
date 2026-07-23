from __future__ import annotations
import json
import re
import uuid
from pathlib import Path
from . import config

SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def new_issue_id() -> str:
    """A short unique id"""
    return uuid.uuid4().hex[:8]


# ---- schools -----------------------------------------------------------

def is_valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug)) and slug not in config.RESERVED_SLUGS


def load_registry() -> dict:
    if not config.SCHOOLS_REGISTRY.exists():
        return {}
    return json.loads(config.SCHOOLS_REGISTRY.read_text())


def save_registry(registry: dict) -> None:
    config.SCHOOLS_REGISTRY.write_text(json.dumps(registry, indent=2))


def school_exists(school: str) -> bool:
    return school in load_registry()


def get_school(school: str) -> dict | None:
    return load_registry().get(school)


def list_schools() -> list[dict]:
    return [public_school(slug, info) for slug, info in load_registry().items()]

PUBLIC_SCHOOL_FIELDS = ("slug", "name", "created")

def public_school(slug: str, info: dict) -> dict:
    """Return only the fields safe to send to an unauthenticated client."""
    public = {}
    for field in PUBLIC_SCHOOL_FIELDS:
        if field == "slug":
            public[field] = slug
        else:
            public[field] = info.get(field)
    return public


def school_dir(school: str) -> Path:
    return config.SCHOOLS_DIR / school


def is_admin(school: str, email: str) -> bool:
    info = get_school(school)
    if not info:
        return False
    allowed = [e.strip().lower() for e in info.get("admin_emails", [])]
    return email.strip().lower() in allowed


# ---- issues (editions) --------------------------------------------------

def issues_dir(school: str) -> Path:
    return school_dir(school) / "issues"


def issue_dir(school: str, issue_id: str) -> Path:
    return issues_dir(school) / issue_id


def source_pdf_path(school: str, issue_id: str) -> Path:
    return issue_dir(school, issue_id) / "source.pdf"


def manifest_path(school: str, issue_id: str) -> Path:
    return issue_dir(school, issue_id) / "manifest.json"


def pages_dir(school: str, issue_id: str) -> Path:
    return issue_dir(school, issue_id) / "pages"


def issue_exists(school: str, issue_id: str) -> bool:
    return manifest_path(school, issue_id).exists()


def list_editions(school: str) -> list[dict]:
    """Manifests for every edition of a school, newest date first."""
    editions = []
    if issues_dir(school).exists():
        for child in issues_dir(school).iterdir():
            manifest_file = child / "manifest.json"
            if manifest_file.exists():
                editions.append(json.loads(manifest_file.read_text()))
    editions.sort(key=lambda m: m.get("date") or "", reverse=True)
    return editions
