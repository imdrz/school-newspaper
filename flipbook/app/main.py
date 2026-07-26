from __future__ import annotations
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import admin, config, renderer, storage
from .admin import require_admin
from .templating import templates


config.ensure_dirs()
app = FastAPI(title="My Flipbook")

# Must be included before the /static, /data mounts, and before the
# /{school}/{edition_id} viewer route further down: GET /{school}/admin is a
# two-segment path structurally identical to /{school}/{edition_id}, and
# Starlette matches routes in registration order — the viewer route would
# otherwise swallow every /{school}/admin request first.
app.include_router(admin.router)

# Serve our front-end files at /static and generated pages at /data.
# These mounts (and every route below, until the school catch-all at the
# bottom) must be registered before the /{school} routes, since Starlette
# matches routes in registration order and /{school}/{edition_id} would
# otherwise swallow two-segment paths like /static/foo.js.
config.STATIC_DIR.mkdir(exist_ok=True)

# app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
# app.mount("/data", StaticFiles(directory=config.DATA_DIR), name="data")


class CachedStaticFiles(StaticFiles):
    IMMUTABLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, *args, immutable_assets: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.immutable_assets = immutable_assets

    def file_response(self, full_path, *args, **kwargs):
        response = super().file_response(full_path, *args, **kwargs)
        cacheable = (
            self.immutable_assets
            and Path(full_path).suffix.lower() in self.IMMUTABLE_SUFFIXES
        )
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if cacheable else "no-cache"
        )
        return response


app.mount("/static", CachedStaticFiles(directory=config.STATIC_DIR), name="static")
app.mount(
    "/data",
    CachedStaticFiles(directory=config.DATA_DIR, immutable_assets=True),
    name="data",
)


@app.post("/api/schools/{school}/issues")
def create_issue(
    school: str,
    file: UploadFile,
    title: str = Form(...),
    date: str | None = Form(None),
    admin_email: str = Depends(require_admin),
):
    if not storage.school_exists(school):
        raise HTTPException(status_code=404, detail="No such school")

    # 1. validate
    if Path(file.filename or "").suffix.lower() not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload a .pdf file")
    contents = file.file.read()
    if len(contents) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too big")

    # 2. save under a fresh issue id
    issue_id = storage.new_issue_id()
    out_dir = storage.issue_dir(school, issue_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    storage.source_pdf_path(school, issue_id).write_bytes(contents)

    # 3. render (stubbed for now)
    try:
        manifest = renderer.render_pdf_to_pages(
            storage.source_pdf_path(school, issue_id),
            out_dir,
            issue_id,
            school=school,
            title=title,
            date=date,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    # 4. respond
    return {
        "id": issue_id,
        "page_count": manifest["page_count"],
        "view_url": f"/{school}/{issue_id}",
    }


@app.delete("/api/schools/{school}/issues/{edition_id}")
def delete_issue(
    school: str, edition_id: str, admin_email: str = Depends(require_admin)
):
    if not storage.issue_exists(school, edition_id):
        raise HTTPException(status_code=404, detail="No such issue")
    shutil.rmtree(storage.issue_dir(school, edition_id))
    return {"deleted": edition_id}


# The public contract for a school, enforced by FastAPI: any field not declared
# here is stripped from the response before it reaches the client - a structural
# second gate beneath storage.public_school's allow-list.
class PublicSchool(BaseModel):
    slug: str
    name: str
    created: str | None = None


@app.get("/api/schools", response_model=list[PublicSchool])
def list_schools():
    return storage.list_schools()


@app.get("/")
def home():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/{school}", response_class=HTMLResponse)
def school_home(school: str, request: Request):
    info = storage.get_school(school)
    if info is None:
        raise HTTPException(status_code=404, detail="No such school")

    return templates.TemplateResponse(
        request,
        "school.html",
        {
            "school": school,
            "info": info,
            "editions": storage.list_editions(school),
            "is_admin": admin.current_admin(school, request) is not None,
        },
    )


@app.get("/{school}/{edition_id}")
def view(school: str, edition_id: str):
    if not storage.school_exists(school) or not storage.issue_exists(
        school, edition_id
    ):
        raise HTTPException(status_code=404, detail="No such issue")
    return FileResponse(config.STATIC_DIR / "viewer" / "index.html")
