from pathlib import Path

# This file is app/config.py, so .parent.parent is your module folder.
MODULE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = MODULE_DIR / "static"      # HTML/JS/CSS we serve to the browser
DATA_DIR = MODULE_DIR / "data"          # everything we generate at runtime
ISSUES_DIR = DATA_DIR / "issues"        # one sub-folder per uploaded issue

DEFAULT_DPI = 150          # higher = sharper images, but bigger and slower
IMAGE_FORMAT = "jpg"       # small files, great for newspaper photos
ALLOWED_EXTENSIONS = {".pdf"}
MAX_UPLOAD_MB = 50

def ensure_dirs() -> None:
    """Create the data folders if they don't exist yet."""
    ISSUES_DIR.mkdir(parents=True, exist_ok=True)