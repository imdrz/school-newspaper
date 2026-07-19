from __future__ import annotations
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, renderer, storage

config.ensure_dirs()
app = FastAPI(title="My Flipbook")

# Serve our front-end files at /static and generated pages at /data.
config.STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/data", StaticFiles(directory=config.DATA_DIR), name="data")

@app.post("/api/issues")
def create_issue(file: UploadFile):
    # 1. validate
    if Path(file.filename or "").suffix.lower() not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload a .pdf file")
    contents = file.file.read()
    if len(contents) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too big")

    # 2. save under a fresh issue id
    issue_id = storage.new_issue_id()
    out_dir = storage.issue_dir(issue_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    storage.source_pdf_path(issue_id).write_bytes(contents)

    # 3. render (stubbed for now)
    try:
        manifest = renderer.render_pdf_to_pages(
            storage.source_pdf_path(issue_id), out_dir, issue_id
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    # 4. respond
    return {"id": issue_id, "page_count": manifest["page_count"],
            "view_url": f"/view/{issue_id}"}


@app.get("/")
def home():
    return FileResponse(config.STATIC_DIR / "index.html")

@app.get("/view/{issue_id}")
def view(issue_id: str):
    if not storage.issue_exists(issue_id):
        raise HTTPException(status_code=404, detail="No such issue")
    return FileResponse(config.STATIC_DIR / "viewer" / "index.html")