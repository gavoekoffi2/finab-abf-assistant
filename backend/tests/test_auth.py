from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app import storage
from app.main import app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "finab_abf_test.sqlite3")


def test_advisor_routes_require_login() -> None:
    client = TestClient(app)
    response = client.get("/api/prospects")
    assert response.status_code == 401


def test_default_advisor_can_login_and_access_own_prospects() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["organization"]["slug"] == "finab"

    prospects = client.get("/api/prospects", headers=headers)
    assert prospects.status_code == 200
    assert isinstance(prospects.json(), list)


def test_public_registration_creates_advisor_account() -> None:
    client = TestClient(app)
    email = "advisor-flow-test@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "FlowTest-2026!",
            "full_name": "Conseiller Flow Test",
            "organization_name": "Cabinet Flow Test",
            "advisor_phone": "5140000000",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "advisor"
    assert data["user"]["organization"]["slug"]


def test_owner_can_access_admin_users() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    overview = client.get("/api/admin/overview", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["users"] >= 1

    users = client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert any(user["role"] == "owner" for user in users.json())
