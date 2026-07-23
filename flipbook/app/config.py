import os
from pathlib import Path
from dotenv import load_dotenv

MODULE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(MODULE_DIR / ".env")  # read .env into environment variables

STATIC_DIR = MODULE_DIR / "static"
DATA_DIR = MODULE_DIR / "data"
SCHOOLS_DIR = DATA_DIR / "schools"      
SCHOOLS_REGISTRY = DATA_DIR / "schools.json"  # slug -> {name, created}

# Slugs that can't be used as a school slug, since they'd collide with
# top-level routes/mounts (/static, /data, /api, /view).
RESERVED_SLUGS = {"static", "data", "api", "view"}

DEFAULT_DPI = 150          # higher = sharper images, but bigger and slower
IMAGE_FORMAT = "jpg"       # small files, great for newspaper photos
ALLOWED_EXTENSIONS = {".pdf"}
MAX_UPLOAD_MB = 50

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

CODE_TTL_SECONDS = 10 * 60           # login codes expire after 10 minutes
SESSION_TTL_SECONDS = 8 * 60 * 60    # a signed-in session lasts 8 hours

def ensure_dirs() -> None:
    """Create the data folders if they don't exist yet."""
    SCHOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if not SCHOOLS_REGISTRY.exists():
        SCHOOLS_REGISTRY.write_text("{}")