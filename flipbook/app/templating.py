import datetime

from fastapi.templating import Jinja2Templates
from . import config

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def fmt_date(value: str | None) -> str:
    """Render an ISO date as 'Jul 26, 2026'; pass anything unparseable through."""
    if not value:
        return "Undated"
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").strftime("%b %-d, %Y")
    except (ValueError, TypeError):
        return value


templates.env.filters["fmt_date"] = fmt_date