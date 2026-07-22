from __future__ import annotations
import datetime
import html
import json
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import admin, config, renderer, storage
from .admin import require_admin

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
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/data", StaticFiles(directory=config.DATA_DIR), name="data")


@app.post("/api/schools/{school}/issues")
def create_issue(school: str, file: UploadFile, title: str = Form(...), date: str | None = Form(None),
                 admin_email: str = Depends(require_admin)):
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
            storage.source_pdf_path(school, issue_id), out_dir, issue_id,
            school=school, title=title, date=date,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    # 4. respond
    return {"id": issue_id, "page_count": manifest["page_count"],
            "view_url": f"/{school}/{issue_id}"}


@app.delete("/api/schools/{school}/issues/{edition_id}")
def delete_issue(school: str, edition_id: str, admin_email: str = Depends(require_admin)):
    if not storage.issue_exists(school, edition_id):
        raise HTTPException(status_code=404, detail="No such issue")
    shutil.rmtree(storage.issue_dir(school, edition_id))
    return {"deleted": edition_id}


# The public contract for a school, enforced by FastAPI: any field not declared
# here is stripped from the response before it reaches the client — a structural
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


@app.get("/{school}")
def school_home(school: str, request: Request):
    info = storage.get_school(school)
    if info is None:
        raise HTTPException(status_code=404, detail="No such school")

    # Is the current viewer a signed-in admin of this school? If so we render the
    # upload panel; otherwise it isn't sent to the browser at all. (The upload
    # API is independently protected by require_admin, so this is UI-only.)
    is_admin = admin.current_admin(school, request) is not None

    editions = storage.list_editions(school)

    def fmt_date(value: str | None) -> str:
        if not value:
            return "Undated"
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d").strftime("%b %-d, %Y")
        except (ValueError, TypeError):
            return value

    cards = []
    for ed in editions:
        eid = ed["id"]
        title = ed.get("title") or eid
        pages = ed.get("pages") or []
        n = ed.get("page_count", 0)
        pp = f"{n} page" + ("" if n == 1 else "s")
        href = f"/{html.escape(school)}/{html.escape(eid)}"
        if pages:
            cover = (f"/data/schools/{html.escape(school)}/issues/"
                     f"{html.escape(eid)}/{html.escape(pages[0]['image'])}")
            frame = (f'<img src="{cover}" loading="lazy" '
                     f'alt="Cover of {html.escape(title)}" />')
        else:
            frame = f'<div class="cover-card__blank">{html.escape(title)}</div>'
        cards.append(f"""<li class="cover-card">
        <a href="{href}">
          <div class="cover-card__frame">{frame}</div>
          <div class="cover-card__meta">
            <p class="cover-card__title">{html.escape(title)}</p>
            <p class="cover-card__sub">{html.escape(fmt_date(ed.get('date')))} · {pp}</p>
          </div>
        </a>
      </li>""")

    editions_block = (
        f'<ul class="cover-grid">{"".join(cards)}</ul>'
        if cards else '<p class="status">No editions yet — the press is warm.</p>'
    )

    # Masthead link reflects sign-in state; upload panel + its script are only
    # emitted for a signed-in admin (empty strings otherwise).
    if is_admin:
        admin_link = (f'<a href="/{html.escape(school)}/admin/dashboard">'
                      f'Admin dashboard</a>')
        upload_html = f"""<section class="press-panel">
        <h2 class="press-panel__head">Submit to press</h2>
        <p class="press-panel__note">Signed in as admin</p>
        <form id="upload-form">
          <label class="field">
            <span class="field__label">Title</span>
            <input type="text" id="title" name="title" required />
          </label>
          <label class="field">
            <span class="field__label">Date</span>
            <input type="date" id="date" name="date" />
          </label>
          <label class="field">
            <span class="field__label">PDF file</span>
            <input type="file" id="file" name="file" accept="application/pdf" required />
          </label>
          <button class="btn" type="submit" id="submit">Upload &amp; render</button>
        </form>
        <p class="status" id="status"></p>
      </section>"""
        upload_script = f"""<script>
    const school = {json.dumps(school)};
    const form = document.getElementById('upload-form');
    const statusEl = document.getElementById('status');
    const submitBtn = document.getElementById('submit');

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const fileInput = document.getElementById('file');
      if (!fileInput.files.length) return;

      submitBtn.disabled = true;
      statusEl.className = 'status';
      statusEl.textContent = 'Uploading and rendering…';

      const data = new FormData();
      data.append('file', fileInput.files[0]);
      data.append('title', document.getElementById('title').value);
      data.append('date', document.getElementById('date').value);

      try {{
        const res = await fetch(`/api/schools/${{school}}/issues`, {{ method: 'POST', body: data }});
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || 'Upload failed');
        statusEl.textContent = `Done — ${{body.page_count}} pages. Opening…`;
        window.location.href = body.view_url;
      }} catch (err) {{
        statusEl.className = 'status status--error';
        statusEl.textContent = err.message;
        submitBtn.disabled = false;
      }}
    }});
  </script>"""
    else:
        admin_link = f'<a href="/{html.escape(school)}/admin">Admin sign in</a>'
        upload_html = ""
        upload_script = ""

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(info['name'])} — Editions</title>
  <link rel="stylesheet" href="/static/brand.css" />
</head>
<body>
  <div class="sheet">
    <header class="masthead">
      <p class="masthead__over">
        <span class="reg-strip" aria-hidden="true">
          <span class="c"></span><span class="m"></span><span class="y"></span><span class="k"></span>
        </span>
        <a href="/">← All papers</a>
        <span class="spacer"></span>
        {admin_link}
      </p>
      <h1 class="masthead__title">{html.escape(info['name'])}</h1>
      <p class="dateline">Every edition, ready to read</p>
      <hr class="rule" />
    </header>

    <main>
      <p class="eyebrow">Editions</p>
      {editions_block}

      {upload_html}
    </main>

    <footer class="sheet-foot">
      <span class="reg-strip" aria-hidden="true">
        <span class="c"></span><span class="m"></span><span class="y"></span><span class="k"></span>
      </span>
      <span>{html.escape(info['name'])}</span>
    </footer>
  </div>

  {upload_script}
</body>
</html>"""
    return HTMLResponse(page)


@app.get("/{school}/{edition_id}")
def view(school: str, edition_id: str):
    if not storage.school_exists(school) or not storage.issue_exists(school, edition_id):
        raise HTTPException(status_code=404, detail="No such issue")
    return FileResponse(config.STATIC_DIR / "viewer" / "index.html")
