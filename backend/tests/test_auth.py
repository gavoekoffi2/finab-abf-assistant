from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app import storage
import app.main as main
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


def test_checkout_success_endpoint_syncs_access_immediately(monkeypatch) -> None:
    client = TestClient(app)
    register = client.post(
        "/api/auth/register",
        json={
            "email": "paid-return@example.com",
            "password": "PaidReturn-2026!",
            "full_name": "Conseiller Paiement",
            "organization_name": "Cabinet Paiement",
            "advisor_phone": "5140001111",
        },
    )
    assert register.status_code == 200
    session = register.json()
    user = session["user"]
    storage.set_stripe_customer(user["id"], "cus_paid_return")
    headers = {"Authorization": f"Bearer {session['token']}"}

    class FakeCheckoutSession:
        @staticmethod
        def retrieve(session_id, expand=None):
            assert session_id == "cs_paid_return"
            return {
                "id": session_id,
                "customer": "cus_paid_return",
                "metadata": {"finab_user_id": user["id"]},
                "payment_status": "paid",
                "subscription": {
                    "id": "sub_paid_return",
                    "status": "active",
                    "trial_end": None,
                    "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                },
            }

    class FakeStripe:
        checkout = type("Checkout", (), {"Session": FakeCheckoutSession})
        Subscription = type("Subscription", (), {"retrieve": staticmethod(lambda subscription_id: None)})

    monkeypatch.setattr(main, "require_stripe", lambda: (FakeStripe, "price_test"))
    response = client.get("/api/billing/checkout-status?session_id=cs_paid_return", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["has_access"] is True
    assert data["user"]["subscription"]["status"] == "active"
    assert data["user"]["subscription"]["last_payment_status"] == "paid"

    prospects = client.get("/api/prospects", headers=headers)
    assert prospects.status_code == 200



def test_owner_can_correct_prospect_before_pdf_generation() -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    payload = {
        "identity": {
            "legal_last_name": "Initial",
            "first_names": "Client",
            "date_of_birth": "1990-01-01",
            "marital_status": "célibataire",
        },
        "contact": {"phone": "5140000000", "email": "client@example.com", "address": "1 Rue A"},
        "employment": {"occupation": "Employé", "annual_income": 40000},
        "financial": {"total_assets": 10000, "total_debts": 2000},
        "insurance": {"has_existing_life_insurance": False},
        "goals": {"priority_projects": "Protection famille", "acceptable_monthly_budget": 150},
        "health": {"height": "170 cm", "weight": "70 kg"},
        "meeting": {"availability": "Soir", "consent_acknowledged": True},
    }
    created = client.post("/api/prospects", json=payload)
    assert created.status_code == 200
    prospect_id = created.json()["id"]

    payload["identity"]["legal_last_name"] = "Corrigé"
    payload["contact"]["phone"] = "4381112222"
    payload["goals"]["acceptable_monthly_budget"] = 225
    update = client.patch(f"/api/prospects/{prospect_id}", headers=headers, json=payload)
    assert update.status_code == 200
    data = update.json()
    assert data["client_name"] == "Client Corrigé"
    assert data["phone"] == "4381112222"
    assert data["payload"]["goals"]["acceptable_monthly_budget"] == 225

    detail = client.get(f"/api/prospects/{prospect_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["payload"]["identity"]["legal_last_name"] == "Corrigé"


def test_owner_can_save_advisor_review_used_for_pdf_generation(monkeypatch) -> None:
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    payload = {
        "identity": {
            "legal_last_name": "Export",
            "first_names": "Client",
            "date_of_birth": "1990-01-01",
            "marital_status": "célibataire",
        },
        "contact": {"phone": "5140000000", "email": "client-export@example.com", "address": "1 Rue A"},
        "employment": {"occupation": "Employé", "annual_income": 40000},
        "financial": {"total_assets": 10000, "total_debts": 2000},
        "insurance": {"has_existing_life_insurance": False},
        "goals": {"priority_projects": "Protection famille", "acceptable_monthly_budget": 150},
        "meeting": {"availability": "Soir", "consent_acknowledged": True},
    }
    created = client.post("/api/prospects", json=payload)
    prospect_id = created.json()["id"]

    review = {
        "reviewed_by_advisor": True,
        "advisor_name": "Conseiller Correction",
        "advisor_phone": "4382223333",
        "advisor_email": "conseiller@example.com",
        "signed_date": "2026-07-06",
        "replacement_years": 12,
        "final_recommended_coverage": 350000,
        "recommendation_1_budget": 180,
        "recommendation_2_budget": 250,
        "client_preference_budget": 200,
        "recommendation_1_notes": "Correction produit 1",
        "recommendation_2_notes": "Correction produit 2",
        "preference_notes": "Correction préférence",
        "agent_notes": "Notes finales corrigées",
    }
    saved = client.patch(f"/api/prospects/{prospect_id}/review", headers=headers, json=review)
    assert saved.status_code == 200
    assert saved.json()["advisor_review"]["final_recommended_coverage"] == 350000

    captured = {}

    def fake_generate(request):
        captured["review"] = request.review
        return main.AbfGenerationResult(
            output_path="/tmp/ABF_test.pdf",
            pages_before=1,
            pages_after=1,
            is_form_pdf_before=True,
            is_form_pdf_after=True,
            filled_widget_updates=1,
            missing_fields=[],
            layout_preserved=True,
        )

    monkeypatch.setattr(main, "_generate_abf", fake_generate)
    generated = client.post(f"/api/prospects/{prospect_id}/generate-abf", headers=headers, json={})
    assert generated.status_code == 200
    assert captured["review"].final_recommended_coverage == 350000
    assert captured["review"].recommendation_1_notes == "Correction produit 1"
