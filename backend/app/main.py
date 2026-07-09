from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .abf_mapping import build_abf_values
from .pdf_fill import fill_acroform, list_acroform_fields, update_acroform_fields
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
    get_pdf_field_overrides,
    get_user_by_id,
    get_prospect,
    get_session_user,
    get_organization,
    get_organization_by_slug,
    list_documents,
    list_organizations,
    list_prospects,
    list_users,
    merge_pdf_field_overrides,
    prospect_review,
    prospect_submission,
    register_account,
    revoke_session,
    save_abf_document,
    set_stripe_customer,
    update_subscription_by_customer,
    update_prospect_payload,
    update_prospect_review,
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


class PdfTextEdit(BaseModel):
    page: int = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    text: str = Field(min_length=1, max_length=600)
    size: int = Field(default=11, ge=7, le=30)
    cover: bool = True


class PdfEditRequest(BaseModel):
    path: str
    edits: list[PdfTextEdit]


class PdfFieldEditRequest(BaseModel):
    path: str
    fields: dict[str, str] = Field(default_factory=dict)


class PdfOverridesRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)


def public_base_url() -> str:
    return os.getenv("FINAB_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def unix_to_iso(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def stripe_value(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def sync_user_from_checkout_session(stripe, session_id: str, user: dict) -> dict:
    checkout = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    metadata = stripe_value(checkout, "metadata", {}) or {}
    checkout_user_id = metadata.get("finab_user_id") if isinstance(metadata, dict) else stripe_value(metadata, "finab_user_id")
    checkout_customer_id = stripe_value(checkout, "customer")
    expected_customer_id = user.get("subscription", {}).get("stripe_customer_id")
    if checkout_user_id != user["id"] and checkout_customer_id != expected_customer_id:
        raise HTTPException(status_code=403, detail="Session Stripe non liée à ce compte")

    subscription = stripe_value(checkout, "subscription")
    if isinstance(subscription, str):
        subscription = stripe.Subscription.retrieve(subscription)
    if not subscription:
        raise HTTPException(status_code=409, detail="Abonnement Stripe en attente de confirmation")

    synced_user = update_subscription_by_user(
        user["id"],
        status=stripe_value(subscription, "status", "trialing"),
        stripe_subscription_id=stripe_value(subscription, "id"),
        trial_ends_at=unix_to_iso(stripe_value(subscription, "trial_end")),
        current_period_end=unix_to_iso(stripe_value(subscription, "current_period_end")),
        last_payment_status=stripe_value(checkout, "payment_status"),
    )
    return synced_user


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


def _user_from_token(token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Connexion conseiller requise")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")
    return user


def _resolve_output_pdf(path: str) -> Path:
    p = Path(path).resolve()
    output_root = OUTPUT_DIR.resolve()
    if output_root not in p.parents or not p.exists() or p.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF introuvable")
    return p


def current_user(authorization: str | None = Header(default=None)) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Connexion conseiller requise")
    return _user_from_token(token)


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
        success_url=f"{public_base_url()}/conseiller?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{public_base_url()}/conseiller?checkout=cancelled",
        metadata={"finab_user_id": user["id"], "plan": "finab_pro"},
    )
    return {"url": checkout.url}


@app.get("/api/billing/checkout-status")
def billing_checkout_status(session_id: str, user: dict = Depends(current_user)) -> dict:
    if user.get("role") == "owner":
        return {"user": user, "subscription": user.get("subscription", {}), "has_access": True}
    stripe, _ = require_stripe()
    synced_user = sync_user_from_checkout_session(stripe, session_id, user)
    return {
        "user": synced_user,
        "subscription": synced_user.get("subscription", {}),
        "has_access": bool(synced_user.get("subscription", {}).get("has_access")),
    }


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
        target_organization_id = record.get("organization_id") or user["organization_id"]
        if record.get("advisor_review") is None:
            record["advisor_review"] = prospect_review(
                prospect_id,
                organization_id=organization_id,
                organization=get_organization(target_organization_id),
            ).model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    record["documents"] = list_documents(prospect_id, organization_id=organization_id)
    return record


@app.patch("/api/prospects/{prospect_id}")
def update_prospect(prospect_id: str, payload: ProspectSubmission, user: dict = Depends(current_paid_user)) -> dict:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        record = update_prospect_payload(prospect_id, payload, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    record["documents"] = list_documents(prospect_id, organization_id=organization_id)
    return record


@app.patch("/api/prospects/{prospect_id}/review")
def update_prospect_advisor_review(prospect_id: str, review: AdvisorReview, user: dict = Depends(current_paid_user)) -> dict:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        record = update_prospect_review(prospect_id, review, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    if record.get("advisor_review") is None:
        record["advisor_review"] = review.model_dump(mode="json")
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
    if review is None or review == AdvisorReview():
        review = prospect_review(prospect_id, organization_id=organization_id, organization=organization)
    overrides = get_pdf_field_overrides(prospect_id, organization_id=organization_id)
    result = _generate_abf(AbfGenerationRequest(prospect=prospect, review=review), overrides=overrides)
    save_abf_document(prospect_id, result.output_path, result.model_dump(), organization_id=target_organization_id)
    return result


@app.get("/api/pdf/info")
def pdf_info(path: str, user: dict = Depends(current_paid_user)) -> dict:
    p = _resolve_output_pdf(path)
    import fitz

    with fitz.open(p) as doc:
        return {"page_count": doc.page_count, "filename": p.name}


@app.get("/api/pdf/fields")
def pdf_fields(path: str, user: dict = Depends(current_paid_user)) -> dict:
    p = _resolve_output_pdf(path)
    return {"path": str(p), "fields": list_acroform_fields(p)}


@app.get("/api/pdf/page-image")
def pdf_page_image(path: str, page: int = 0, token: str | None = None) -> FileResponse:
    user = _user_from_token(token)
    if not (user.get("role") == "owner" or user.get("subscription", {}).get("has_access")):
        raise HTTPException(status_code=402, detail="Abonnement requis pour accéder à FINAB ABF Flow")
    p = _resolve_output_pdf(path)
    import fitz

    with fitz.open(p) as doc:
        if page < 0 or page >= doc.page_count:
            raise HTTPException(status_code=404, detail="Page PDF introuvable")
        cache_key = f"preview_{p.stem}_m{int(p.stat().st_mtime)}_p{page}.png"
        image_path = OUTPUT_DIR / cache_key
        if not image_path.exists():
            rendered = doc[page].get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            rendered.save(image_path)
    return FileResponse(image_path, media_type="image/png", filename=image_path.name, content_disposition_type="inline")


@app.post("/api/prospects/{prospect_id}/pdf-edits", response_model=AbfGenerationResult)
def apply_pdf_edits(prospect_id: str, request: PdfEditRequest, user: dict = Depends(current_paid_user)) -> AbfGenerationResult:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        prospect_record = get_prospect(prospect_id, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    source = _resolve_output_pdf(request.path)
    if not request.edits:
        raise HTTPException(status_code=400, detail="Aucune modification PDF à appliquer")

    import fitz

    output = OUTPUT_DIR / f"{source.stem}_modifie_{uuid4().hex[:8]}.pdf"
    with fitz.open(source) as doc:
        page_count = doc.page_count
        for edit in request.edits:
            if edit.page >= doc.page_count:
                continue
            page = doc[edit.page]
            rect = page.rect
            x = rect.x0 + edit.x * rect.width
            y = rect.y0 + edit.y * rect.height
            text = edit.text.strip()
            if not text:
                continue
            box_width = min(max(len(text) * edit.size * 0.58, 70), rect.width - x - 12)
            lines = max(text.count("\n") + 1, 1)
            box_height = max(edit.size * 1.55 * lines, edit.size + 8)
            target = fitz.Rect(x, y, min(x + box_width + 10, rect.x1 - 8), min(y + box_height + 8, rect.y1 - 8))
            if edit.cover:
                page.draw_rect(target, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_textbox(
                target,
                text,
                fontsize=edit.size,
                fontname="helv",
                color=(0.02, 0.08, 0.16),
                align=fitz.TEXT_ALIGN_LEFT,
                overlay=True,
            )
        doc.save(output, garbage=4, deflate=True)

    report = {
        "pages_before": page_count,
        "pages_after": page_count,
        "is_form_pdf_before": True,
        "is_form_pdf_after": True,
        "filled_widget_updates": len([edit for edit in request.edits if edit.text.strip()]),
        "missing_fields": [],
        "layout_preserved": True,
    }
    target_organization_id = prospect_record.get("organization_id") or user["organization_id"]
    result = AbfGenerationResult(output_path=str(output), **report)
    save_abf_document(prospect_id, result.output_path, result.model_dump(), organization_id=target_organization_id)
    return result


@app.patch("/api/prospects/{prospect_id}/pdf-overrides")
def save_prospect_pdf_overrides(
    prospect_id: str, request: PdfOverridesRequest, user: dict = Depends(current_paid_user)
) -> dict:
    """Store the counselor's direct PDF field edits without producing a new PDF.

    Saving only records the overrides; the final document is created solely when
    the counselor clicks "Générer le PDF", so the workspace is not flooded with
    intermediate PDF versions.
    """
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    if not request.fields:
        raise HTTPException(status_code=400, detail="Aucune modification PDF à enregistrer")
    try:
        overrides = merge_pdf_field_overrides(prospect_id, request.fields, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    return {"pdf_field_overrides": overrides}


@app.patch("/api/prospects/{prospect_id}/pdf-fields", response_model=AbfGenerationResult)
def update_prospect_pdf_fields(
    prospect_id: str, request: PdfFieldEditRequest, user: dict = Depends(current_paid_user)
) -> AbfGenerationResult:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    try:
        prospect_record = get_prospect(prospect_id, organization_id=organization_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    source = _resolve_output_pdf(request.path)
    if not request.fields:
        raise HTTPException(status_code=400, detail="Aucun champ PDF à modifier")

    output = OUTPUT_DIR / f"{source.stem}_modifie_{uuid4().hex[:8]}.pdf"
    try:
        report = update_acroform_fields(source, output, request.fields)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF introuvable") from None

    # Remember the manual edits so a later "Générer le PDF final" keeps them
    # instead of reverting to the values derived from the client form.
    merge_pdf_field_overrides(prospect_id, request.fields, organization_id=organization_id)

    target_organization_id = prospect_record.get("organization_id") or user["organization_id"]
    result = AbfGenerationResult(output_path=str(output), **report)
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


def _generate_abf(request: AbfGenerationRequest, overrides: dict | None = None) -> AbfGenerationResult:
    values = build_abf_values(request.prospect, request.review)
    if overrides:
        # The counselor's direct PDF field edits win over the form-derived
        # values so regenerating the ABF keeps every manual correction.
        values.update({name: str(value) for name, value in overrides.items()})
    safe_name = "_".join(request.prospect.identity.full_name.split()) or "client"
    output = OUTPUT_DIR / f"ABF_{safe_name}_{uuid4().hex[:8]}.pdf"
    report = fill_acroform(TEMPLATE, output, values)
    return AbfGenerationResult(output_path=str(output), **report)


@app.get("/abf/download")
def download(path: str, user: dict = Depends(current_paid_user)) -> FileResponse:
    p = _resolve_output_pdf(path)
    # The path itself is only revealed by protected prospect/document endpoints.
    return FileResponse(p, media_type="application/pdf", filename=p.name)


@app.get("/abf/view")
def view_pdf(path: str, token: str | None = None) -> FileResponse:
    user = _user_from_token(token)
    if not (user.get("role") == "owner" or user.get("subscription", {}).get("has_access")):
        raise HTTPException(status_code=402, detail="Abonnement requis pour accéder à FINAB ABF Flow")
    p = _resolve_output_pdf(path)
    # Native browser PDF viewers cannot send Authorization headers from an iframe.
    # This protected query-token endpoint lets the advisor see and fill the actual
    # generated AcroForm PDF directly in the workspace instead of only downloading it.
    return FileResponse(p, media_type="application/pdf", filename=p.name, content_disposition_type="inline")


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str) -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    if index.exists() and not full_path.startswith("api/"):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
