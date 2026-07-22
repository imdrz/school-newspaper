from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_schools_list_never_exposes_admin_emails():
    resp = client.get("/api/schools")
    assert resp.status_code == 200
    # No school object may carry admin_emails (or any private field) to the public.
    for school in resp.json():
        assert "admin_emails" not in school


def test_schools_list_still_returns_what_the_homepage_needs():
    # The fix must not break the site: index.html reads s.slug and s.name.
    resp = client.get("/api/schools")
    for school in resp.json():
        assert "slug" in school
        assert "name" in school


PRIVATE_FIELDS = {"admin_emails"}  # extend as you add private fields


def test_no_private_field_ever_appears():
    for school in client.get("/api/schools").json():
        assert PRIVATE_FIELDS.isdisjoint(school.keys())
