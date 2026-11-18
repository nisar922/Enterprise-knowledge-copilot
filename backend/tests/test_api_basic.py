from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_protected_endpoint_requires_token():
    assert client.get("/documents").status_code == 401


def test_register_rejects_short_password():
    response = client.post(
        "/auth/register",
        json={"username": "tester", "email": "t@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_register_rejects_invalid_email():
    response = client.post(
        "/auth/register",
        json={"username": "tester", "email": "not-an-email", "password": "long-enough-123"},
    )
    assert response.status_code == 422


def test_root_redirects_to_login_page():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/html/login.html"