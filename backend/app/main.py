from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
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
    update_user_by_owner,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "samples" / "private" / "ABF_VIERGE.pdf"
OUTPUT_DIR = ROOT / "output"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Finab ABF Flow", version="0.3.0")


def current_user(authorization: str | None = Header(default=None)) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Connexion conseiller requise")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")
    return user


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
def organizations(user: dict = Depends(current_user)) -> list[dict]:
    if user["role"] != "owner":
        return [user["organization"]]
    return list_organizations()


@app.get("/api/admin/overview")
def admin_stats(user: dict = Depends(current_user)) -> dict:
    try:
        return admin_overview(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@app.get("/api/admin/users")
def admin_users(user: dict = Depends(current_user)) -> list[dict]:
    try:
        return list_users(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@app.post("/api/admin/users")
def admin_create_user(payload: AdminUserCreate, user: dict = Depends(current_user)) -> dict:
    try:
        return create_user_by_owner(user, payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, user: dict = Depends(current_user)) -> dict:
    try:
        return update_user_by_owner(user, user_id, payload.model_dump(exclude_unset=True))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable") from None


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, user: dict = Depends(current_user)) -> dict:
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
def prospects(user: dict = Depends(current_user)) -> list[dict]:
    organization_id = None if user["role"] == "owner" else user["organization_id"]
    return list_prospects(organization_id=organization_id)


@app.get("/api/prospects/{prospect_id}")
def prospect_detail(prospect_id: str, user: dict = Depends(current_user)) -> dict:
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
    user: dict = Depends(current_user),
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
def download(path: str, user: dict = Depends(current_user)) -> FileResponse:
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
