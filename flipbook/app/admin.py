from __future__ import annotations
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import config, mailer, sessions, storage, tokens
from .templating import templates

router = APIRouter()

@router.get("/{school}/admin", response_class=HTMLResponse)
def admin_login_page(school: str, request: Request):
    info = storage.get_school(school)
    if not info:
        raise HTTPException(status_code=404, detail="No such school")
    return templates.TemplateResponse(
        request, "admin/login.html", {"school": school, "info": info}
    )


@router.post("/{school}/admin/request-code", response_class=HTMLResponse)
def request_code(school: str, request: Request, email: str = Form(...)):
    info = storage.get_school(school)
    if not info:
        raise HTTPException(status_code=404, detail="No such school")

    # Only actually send a code if the email is a real admin — but respond the
    # same either way, so we never reveal who the admins are (no enumeration).
    if storage.is_admin(school, email):
        code = tokens.issue_code(school, email)
        mailer.send_login_code(email, code, info["name"])

    return templates.TemplateResponse(
        request, "admin/code-sent.html", {"school": school, "info": info}
    )


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
        # secure=True,       # UNCOMMENT in production (HTTPS only)
        secure=config.COOKIE_SECURE,  
    )
    return response


@router.get("/{school}/admin/dashboard", response_class=HTMLResponse)
def dashboard(school: str, request: Request, admin_email: str = Depends(require_admin)):
    info = storage.get_school(school)
    name = info["name"] if info else school
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"school": school, "name": name, "admin_email": admin_email},
    )


@router.post("/{school}/admin/logout")
def logout(school: str):
    response = RedirectResponse(url=f"/{school}/admin", status_code=303)
    response.delete_cookie(sessions.COOKIE_NAME)
    return response
