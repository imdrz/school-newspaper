"""One-off migration: move the old flat data/issues/<id>/ layout into
data/schools/default-school/issues/<id>/ and register "default-school".

Run once, from modules/flipbook-practice/:
    .venv/bin/python scripts/migrate_default_school.py
"""
from __future__ import annotations
import datetime
import json
import shutil
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))

from app import config, storage  # noqa: E402

OLD_ISSUES_DIR = MODULE_DIR / "data" / "issues"
SCHOOL_SLUG = "default-school"
SCHOOL_NAME = "Default School"


def main() -> None:
    config.ensure_dirs()
    registry = storage.load_registry()
    if SCHOOL_SLUG not in registry:
        registry[SCHOOL_SLUG] = {
            "name": SCHOOL_NAME,
            "created": datetime.date.today().isoformat(),
        }
        storage.save_registry(registry)
        print(f"Registered school '{SCHOOL_SLUG}'.")
    else:
        print(f"School '{SCHOOL_SLUG}' already registered, leaving as-is.")

    if not OLD_ISSUES_DIR.exists():
        print("No old data/issues/ directory found — nothing to migrate.")
        return

    dest_issues_dir = storage.issues_dir(SCHOOL_SLUG)
    dest_issues_dir.mkdir(parents=True, exist_ok=True)

    migrated, skipped = [], []
    for old_dir in sorted(OLD_ISSUES_DIR.iterdir()):
        if not old_dir.is_dir():
            continue
        issue_id = old_dir.name
        manifest_file = old_dir / "manifest.json"
        if not manifest_file.exists():
            skipped.append(issue_id)
            continue

        new_dir = dest_issues_dir / issue_id
        if new_dir.exists():
            print(f"  {issue_id}: already present at destination, skipping move.")
        else:
            shutil.move(str(old_dir), str(new_dir))

        manifest = json.loads((new_dir / "manifest.json").read_text())
        manifest["school"] = SCHOOL_SLUG
        manifest.setdefault("title", issue_id)
        if not manifest.get("date"):
            pdf = new_dir / "source.pdf"
            mtime = pdf.stat().st_mtime if pdf.exists() else new_dir.stat().st_mtime
            manifest["date"] = datetime.date.fromtimestamp(mtime).isoformat()
        (new_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        migrated.append(issue_id)

    print(f"Migrated {len(migrated)} edition(s): {', '.join(migrated) or '(none)'}")
    if skipped:
        print(
            f"Skipped {len(skipped)} entr{'y' if len(skipped) == 1 else 'ies'} "
            f"with no manifest.json (left in place, not migrated): {', '.join(skipped)}"
        )

    remaining = [p.name for p in OLD_ISSUES_DIR.iterdir() if p.is_dir()]
    if remaining:
        print(f"data/issues/ still contains: {', '.join(remaining)} — not removed.")
    else:
        OLD_ISSUES_DIR.rmdir()
        print("data/issues/ is now empty and was removed.")


if __name__ == "__main__":
    main()
