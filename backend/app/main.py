from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .abf_mapping import build_abf_values
from .pdf_fill import fill_acroform
from .schemas import (
    AbfGenerationRequest,
    AbfGenerationResult,
    AdminUserCreate,
    AdminUserUpdate,
    AdvisorReview,
    LoginRequest,
    LoginResult,
    ProspectSubmission,
    RegisterRequest,
)
from .storage import (
    admin_overview,
    authenticate,
    create_prospect,
    create_user_by_owner,
    default_review,
    delete_user_by_owner,
    get_user_by_id,
    get_prospect,
    get_session_user,
    get_organization,
    get_organization_by_slug,
    list_documents,
    list_organizations,
    list_prospects,
    list_users,
    prospect_submission,
    register_account,
    revoke_session,
    save_abf_document,
    set_stripe_customer,
    update_subscription_by_customer,
    update_subscription_by_user,
    update_user_by_owner,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "samples" / "private" / "ABF_VIERGE.pdf"
OUTPUT_DIR = ROOT / "output"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Finab ABF Flow", version="0.3.0")

PLAN_PRICE_USD = 199
TRIAL_DAYS = 3


def public_base_url() -> str:
    return os.getenv("FINAB_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def unix_to_iso(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def require_stripe():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    price_id = os.getenv("STRIPE_PRICE_ID", "").strip()
    if not secret or not price_id:
        raise HTTPException(
            status_code=503,
            detail="Stripe n'est pas encore configuré. Ajoutez STRIPE_SECRET_KEY et STRIPE_PRICE_ID.",
        )
    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Le package stripe doit être installé côté serveur.") from exc
    stripe.api_key = secret
    return stripe, price_id


def current_user(authorization: str | None = Header(default=None)) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Connexion conseiller requise")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")
    return user


def current_paid_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") == "owner" or user.get("subscription", {}).get("has_access"):
        return user
    raise HTTPException(status_code=402, detail="Abonnement requis pour accéder à FINAB ABF Flow")


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "finab-abf-flow",
        "template_exists": TEMPLATE.exists(),
        "frontend_exists": FRONTEND_DIST.exists(),
    }


@app.post("/api/auth/login", response_model=LoginResult)
def login(payload: LoginRequest) -> LoginResult:
    result = authenticate(payload.email, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    return LoginResult.model_validate(result)


@app.post("/api/auth/register", response_model=LoginResult)
def register(payload: RegisterRequest) -> LoginResult:
    try:
        result = register_account(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            organization_name=payload.organization_name,
            advisor_phone=payload.advisor_phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return LoginResult.model_validate(result)


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    _, _, token = (authorization or "").partition(" ")
    if token:
        revoke_session(token)
    return {"ok": True}


@app.get("/api/billing/config")
def billing_config(user: dict = Depends(current_user)) -> dict:
    return {
        "plan_name": "FINAB ABF Flow Pro",
        "price_usd": PLAN_PRICE_USD,
        "trial_days": TRIAL_DAYS,
        "stripe_publishable_key_configured": bool(os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()),
        "stripe_secret_configured": bool(os.getenv("STRIPE_SECRET_KEY", "").strip()),
        "stripe_price_configured": bool(os.getenv("STRIPE_PRICE_ID", "").strip()),
        "subscription": user.get("subscription", {}),
    }


@app.post("/api/billing/checkout")
def create_billing_checkout(user: dict = Depends(current_user)) -> dict:
    if user.get("role") == "owner":
        return {"url": "/conseiller", "message": "Accès direction déjà actif"}
    stripe, price_id = require_stripe()
    customer_id = user.get("subscription", {}).get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            name=user["full_name"],
            metadata={"finab_user_id": user["id"], "organization_id": user["organization_id"]},
        )
        customer_id = customer.id
        user = set_stripe_customer(user["id"], customer_id)
    checkout = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        payment_method_collection="always",
        line_items=[{"price": price_id, "quantity": 1}],
        subscription_data={
            "trial_period_days": TRIAL_DAYS,
            "metadata": {"finab_user_id": user["id"], "plan": "finab_pro"},
        },
        success_url=f"{public_base_url()}/conseiller?checkout=success",
        cancel_url=f"{public_base_url()}/conseiller?checkout=cancelled",
        metadata={"finab_user_id": user["id"], "plan": "finab_pro"},
    )
    return {"url": checkout.url}


@app.post("/api/billing/portal")
def create_billing_portal(user: dict = Depends(current_user)) -> dict:
    customer_id = user.get("subscription", {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=409, detail="Aucun client Stripe lié à ce compte")
    stripe, _ = require_stripe()
    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{public_base_url()}/conseiller",
    )
    return {"url": portal.url}


@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Le package stripe doit être installé côté serveur.") from exc
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret) if webhook_secret else stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Webhook Stripe invalide") from exc

    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        user_id = obj.get("metadata", {}).get("finab_user_id")
        subscription_id = obj.get("subscription")
        if user_id and subscription_id:
            try:
                stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
                subscription = stripe.Subscription.retrieve(subscription_id)
                update_subscription_by_user(
                    user_id,
                    status=subscription.status,
                    stripe_subscription_id=subscription.id,
                    trial_ends_at=unix_to_iso(subscription.trial_end),
                    current_period_end=unix_to_iso(subscription.current_period_end),
                    last_payment_status=obj.get("payment_status"),
                )
            except Exception:
                update_subscription_by_user(user_id, status="trialing", stripe_subscription_id=subscription_id, last_payment_status=obj.get("payment_status"))
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        update_subscription_by_customer(
            obj.get("customer"),
            status=obj.get("status", "incomplete"),
            stripe_subscription_id=obj.get("id"),
            trial_ends_at=unix_to_iso(obj.get("trial_end")),
            current_period_end=unix_to_iso(obj.get("current_period_end")),
        )
    elif event_type in {"invoice.payment_failed", "invoice.payment_succeeded"}:
        status = "active" if event_type == "invoice.payment_succeeded" else "past_due"
        update_subscription_by_customer(obj.get("customer"), status=status, last_payment_status=obj.get("status"))
    return {"received": True}


@app.get("/api/organizations/{advisor_slug}/public")
def public_organization(advisor_slug: str) -> dict:
    try:
        organization = get_organization_by_slug(advisor_slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conseiller introuvable") from None
    return {
        "name": organization["name"],
        "slug": organization["slug"],
        "advisor_name": organization["advisor_name"],
        "advisor_phone": organization["advisor_phone"],
        "advisor_email": organization["advisor_email"],
    }


@app.get("/api/organizations")
def organizations(user: dict = Depends(current_paid_user)) -> list[dict]:
    if user["role"] != "owner":
        return [user["organization"]]
    return list_organizations()


@app.get("/api/admin/overview")
def admin_stats(user: dict = Depends(current_paid_user)) -> dict:
    try:
        return admin_overview(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@app.get("/api/admin/users")
def admin_users(user: dict = Depends(current_paid_user)) -> list[dict]:
    try:
        return list_users(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@app.post("/api/admin/users")
def admin_create_user(payload: AdminUserCreate, user: dict = Depends(current_paid_user)) -> dict:
    try:
        return create_user_by_owner(user, payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, user: dict = Depends(current_paid_user)) -> dict:
    try:
        return update_user_by_owner(user, user_id, payload.model_dump(exclude_unset=True))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable") from None


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, user: dict = Depends(current_paid_user)) -> dict:
    try:
        delete_user_by_owner(user, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable") from None
    return {"ok": True}


@app.post("/api/prospects")
def submit_prospect(payload: ProspectSubmission, advisor_slug: str = "finab") -> dict:
    return create_prospect(advisor_slug=advisor_slug, prospect=payload)


@app.get("/api/prospects")
def prospects(user: dict = Depends(current_paid_user)) -> list[dict]:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    return list_prospects(organization_id=organization_id)


@app.get("/api/prospects/{prospect_id}")
def prospect_detail(prospect_id: str, user: dict = Depends(current_paid_user)) -> dict:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        record = get_prospect(prospect_id, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    record["documents"] = list_documents(prospect_id, organization_id=organization_id)
    return record


@app.post("/api/prospects/{prospect_id}/generate-abf", response_model=AbfGenerationResult)
def generate_prospect_abf(
    prospect_id: str,
    review: AdvisorReview | None = None,
    user: dict = Depends(current_paid_user),
) -> AbfGenerationResult:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        prospect = prospect_submission(prospect_id, organization_id=organization_id)
        prospect_record = get_prospect(prospect_id, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    target_organization_id = prospect_record.get("organization_id") or user["organization_id"]
    organization = get_organization(target_organization_id)
    review = review or default_review(prospect, organization=organization)
    result = _generate_abf(AbfGenerationRequest(prospect=prospect, review=review))
    save_abf_document(prospect_id, result.output_path, result.model_dump(), organization_id=target_organization_id)
    return result


@app.post("/abf/generate", response_model=AbfGenerationResult)
def generate_abf(request: AbfGenerationRequest) -> AbfGenerationResult:
    if not request.review.reviewed_by_advisor and not request.allow_draft_watermark:
        raise HTTPException(
            status_code=400,
            detail="Le conseiller financier doit réviser/valider avant génération finale.",
        )
    return _generate_abf(request)


def _generate_abf(request: AbfGenerationRequest) -> AbfGenerationResult:
    values = build_abf_values(request.prospect, request.review)
    safe_name = "_".join(request.prospect.identity.full_name.split()) or "client"
    output = OUTPUT_DIR / f"ABF_{safe_name}_{uuid4().hex[:8]}.pdf"
    report = fill_acroform(TEMPLATE, output, values)
    return AbfGenerationResult(output_path=str(output), **report)


@app.get("/abf/download")
def download(path: str, user: dict = Depends(current_paid_user)) -> FileResponse:
    p = Path(path).resolve()
    if OUTPUT_DIR.resolve() not in p.parents or not p.exists():
        raise HTTPException(status_code=404, detail="PDF introuvable")
    # The path itself is only revealed by protected prospect/document endpoints.
    return FileResponse(p, media_type="application/pdf", filename=p.name)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str) -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    if index.exists() and not full_path.startswith("api/"):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
