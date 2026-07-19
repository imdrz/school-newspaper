from __future__ import annotations
import uuid
from pathlib import Path
from . import config

def new_issue_id() -> str:
    """A short unique id like '3f9a1c2b'."""
    return uuid.uuid4().hex[:8]

def issue_dir(issue_id: str) -> Path:
    return config.ISSUES_DIR / issue_id

def source_pdf_path(issue_id: str) -> Path:
    return issue_dir(issue_id) / "source.pdf"

def manifest_path(issue_id: str) -> Path:
    return issue_dir(issue_id) / "manifest.json"

def pages_dir(issue_id: str) -> Path:
    return issue_dir(issue_id) / "pages"

def issue_exists(issue_id: str) -> bool:
    return manifest_path(issue_id).exists()