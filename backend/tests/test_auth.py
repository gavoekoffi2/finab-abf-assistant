from __future__ import annotations

from datetime import datetime, timedelta, timezone

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

def test_owner_can_grant_limited_and_unlimited_access() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    create = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": "subscriber@example.com",
            "password": "Subscriber-2026!",
            "full_name": "Abonné Test",
            "role": "advisor",
            "organization_name": "Cabinet Abonné Test",
            "plan": "finab_pro",
            "subscription_status": "active",
            "current_period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert create.status_code == 200
    user = create.json()
    assert user["subscription"]["has_access"] is True
    assert user["subscription"]["current_period_end"]

    grant = client.patch(
        f"/api/admin/users/{user['id']}",
        headers=headers,
        json={
            "plan": "enterprise",
            "subscription_status": "active",
            "current_period_end": None,
            "last_payment_status": "admin_grant",
        },
    )
    assert grant.status_code == 200
    data = grant.json()
    assert data["subscription"]["has_access"] is True
    assert data["subscription"]["current_period_end"] is None
    assert "illimité" in data["subscription"]["access_label"].lower()

    revoke = client.patch(
        f"/api/admin/users/{user['id']}",
        headers=headers,
        json={"plan": "free", "subscription_status": "incomplete", "current_period_end": None},
    )
    assert revoke.status_code == 200
    assert revoke.json()["subscription"]["has_access"] is False

def test_admin_director_can_access_admin_controls() -> None:
    client = TestClient(app)
    owner_login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['token']}"}

    create = client.post(
        "/api/admin/users",
        headers=owner_headers,
        json={
            "email": "director@example.com",
            "password": "Director-2026!",
            "full_name": "Directeur FINAB",
            "role": "admin",
            "organization_name": "FINAB Direction",
            "plan": "enterprise",
            "subscription_status": "active",
            "current_period_end": None,
        },
    )
    assert create.status_code == 200

    director_login = client.post("/api/auth/login", json={"email": "director@example.com", "password": "Director-2026!"})
    assert director_login.status_code == 200
    director_headers = {"Authorization": f"Bearer {director_login.json()['token']}"}

    overview = client.get("/api/admin/overview", headers=director_headers)
    assert overview.status_code == 200
    users = client.get("/api/admin/users", headers=director_headers)
    assert users.status_code == 200


def test_owner_create_existing_email_updates_access_and_password() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    create = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": "subscriber@example.com",
            "password": "FirstPass-2026!",
            "full_name": "Abonné Initial",
            "role": "advisor",
            "organization_name": "Cabinet Initial",
            "plan": "finab_pro",
            "subscription_status": "active",
            "current_period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert create.status_code == 200
    user_id = create.json()["id"]

    update = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": "subscriber@example.com",
            "password": "SecondPass-2026!",
            "full_name": "Abonné Promu",
            "role": "admin",
            "organization_name": "Cabinet Promu",
            "plan": "enterprise",
            "subscription_status": "active",
            "current_period_end": None,
        },
    )
    assert update.status_code == 200
    data = update.json()
    assert data["id"] == user_id
    assert data["full_name"] == "Abonné Promu"
    assert data["role"] == "admin"
    assert data["subscription"]["has_access"] is True
    assert data["subscription"]["current_period_end"] is None

    old_login = client.post("/api/auth/login", json={"email": "subscriber@example.com", "password": "FirstPass-2026!"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"email": "subscriber@example.com", "password": "SecondPass-2026!"})
    assert new_login.status_code == 200

