from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import config, mailer, sessions, storage, tokens

router = APIRouter()

# The CMYK registration strip — the brand's signature, echoed on admin pages.
_REG = ('<span class="reg-strip" aria-hidden="true">'
        '<span class="c"></span><span class="m"></span>'
        '<span class="y"></span><span class="k"></span></span>')


def _page(title: str, body: str) -> str:
    """Wrap an admin fragment in a full, brand-styled document."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="stylesheet" href="/static/brand.css" />
</head>
<body>
  <div class="auth">
{body}
  </div>
</body>
</html>"""


@router.get("/{school}/admin", response_class=HTMLResponse)
def admin_login_page(school: str):
    info = storage.get_school(school)
    if not info:
        raise HTTPException(status_code=404, detail="No such school")
    body = f"""    <header class="masthead masthead--sm">
      <p class="masthead__over">{_REG}<a href="/{school}">← {info['name']}</a></p>
      <h1 class="masthead__title">Admin sign in</h1>
      <hr class="rule" />
    </header>
    <section class="press-panel">
      <h2 class="press-panel__head">Sign in to publish</h2>
      <p class="press-panel__note">{info['name']}</p>
      <form method="post" action="/{school}/admin/request-code">
        <label class="field">
          <span class="field__label">Email</span>
          <input name="email" type="email" placeholder="you@school.org" required>
        </label>
        <button class="btn">Email me a code</button>
      </form>
    </section>"""
    return _page(f"{info['name']} — Admin", body)


@router.post("/{school}/admin/request-code", response_class=HTMLResponse)
def request_code(school: str, email: str = Form(...)):
    info = storage.get_school(school)
    if not info:
        raise HTTPException(status_code=404, detail="No such school")

    # Only actually send a code if the email is a real admin — but respond the
    # SAME either way, so we never reveal who the admins are (no enumeration).
    if storage.is_admin(school, email):
        code = tokens.issue_code(school, email)
        mailer.send_login_code(email, code, info["name"])

    body = f"""    <header class="masthead masthead--sm">
      <p class="masthead__over">{_REG}<a href="/{school}/admin">← Back</a></p>
      <h1 class="masthead__title">Check your email</h1>
      <hr class="rule" />
    </header>
    <section class="press-panel">
      <p class="hint">If that address is an admin of {info['name']}, a code is on its way.</p>
      <form method="post" action="/{school}/admin/verify">
        <label class="field">
          <span class="field__label">Sign-in code</span>
          <input name="code" type="text" placeholder="paste your code" required>
        </label>
        <button class="btn">Sign in</button>
      </form>
    </section>"""
    return _page(f"{info['name']} — Check your email", body)


def current_admin(school: str, request: Request) -> str | None:
    """Return the signed-in admin's email for THIS school, or None. Never raises —
    use it for optional UI gating (e.g. deciding whether to render the upload
    panel). For endpoints that must reject non-admins, use require_admin instead."""
    token = request.cookies.get(sessions.COOKIE_NAME)
    data = sessions.read_session(token) if token else None
    if not data or data.get("school") != school:
        return None
    return data["email"]


def require_admin(school: str, request: Request) -> str:
    """Return the signed-in admin's email, or raise 401. Also enforces that the
    session is for THIS school. `school` is bound from the path parameter of
    whichever route depends on this — the names must match, or FastAPI won't
    pick it up from the URL at all."""
    email = current_admin(school, request)
    if email is None:
        raise HTTPException(status_code=401, detail="Admin login required")
    return email


@router.post("/{school}/admin/verify")
def verify(school: str, code: str = Form(...)):
    email = tokens.consume_code(school, code)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    token = sessions.create_session(school, email)
    response = RedirectResponse(
        url=f"/{school}/admin/dashboard", status_code=303
    )
    response.set_cookie(
        sessions.COOKIE_NAME, token,
        httponly=True,       # JavaScript can't read it (blocks XSS theft)
        samesite="lax",      # not sent on cross-site POSTs (blocks CSRF)
        max_age=config.SESSION_TTL_SECONDS,
        # secure=True,       # ← UNCOMMENT in production (HTTPS only)
    )
    return response


@router.get("/{school}/admin/dashboard", response_class=HTMLResponse)
def dashboard(school: str, admin_email: str = Depends(require_admin)):
    info = storage.get_school(school)
    name = info["name"] if info else school
    body = f"""    <header class="masthead masthead--sm">
      <p class="masthead__over">{_REG}<span>Signed in</span></p>
      <h1 class="masthead__title">You're in</h1>
      <hr class="rule" />
    </header>
    <section class="press-panel">
      <p class="hint">Signed in as <strong>{admin_email}</strong>, admin of {name}.</p>
      <a class="btn" href="/{school}">Go to the paper →</a>
      <form method="post" action="/{school}/admin/logout" style="margin-top:1rem">
        <button class="btn btn--ghost">Log out</button>
      </form>
    </section>"""
    return _page(f"{name} — Admin dashboard", body)


@router.post("/{school}/admin/logout")
def logout(school: str):
    response = RedirectResponse(url=f"/{school}/admin", status_code=303)
    response.delete_cookie(sessions.COOKIE_NAME)
    return response
