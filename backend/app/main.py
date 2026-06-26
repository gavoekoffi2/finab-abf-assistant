from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .abf_mapping import build_abf_values
from .pdf_fill import fill_acroform
from .schemas import AbfGenerationRequest, AbfGenerationResult, AdvisorReview, ProspectSubmission
from .storage import (
    create_prospect,
    default_review,
    get_prospect,
    list_documents,
    list_prospects,
    prospect_submission,
    save_abf_document,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "samples" / "private" / "ABF_VIERGE.pdf"
OUTPUT_DIR = ROOT / "output"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="FINAB ABF Assistant", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "finab-abf-assistant",
        "template_exists": TEMPLATE.exists(),
        "frontend_exists": FRONTEND_DIST.exists(),
    }


@app.post("/api/prospects")
def submit_prospect(payload: ProspectSubmission, advisor_slug: str = "finab") -> dict:
    return create_prospect(advisor_slug=advisor_slug, prospect=payload)


@app.get("/api/prospects")
def prospects(advisor_slug: str | None = None) -> list[dict]:
    return list_prospects(advisor_slug=advisor_slug)


@app.get("/api/prospects/{prospect_id}")
def prospect_detail(prospect_id: str) -> dict:
    try:
        record = get_prospect(prospect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    record["documents"] = list_documents(prospect_id)
    return record


@app.post("/api/prospects/{prospect_id}/generate-abf", response_model=AbfGenerationResult)
def generate_prospect_abf(prospect_id: str, review: AdvisorReview | None = None) -> AbfGenerationResult:
    try:
        prospect = prospect_submission(prospect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Prospect introuvable") from None
    review = review or default_review(prospect)
    result = _generate_abf(AbfGenerationRequest(prospect=prospect, review=review))
    save_abf_document(prospect_id, result.output_path, result.model_dump())
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
    output = OUTPUT_DIR / f"ABF_{request.prospect.identity.full_name.replace(' ', '_')}_{uuid4().hex[:8]}.pdf"
    report = fill_acroform(TEMPLATE, output, values)
    return AbfGenerationResult(output_path=str(output), **report)


@app.get("/abf/download")
def download(path: str) -> FileResponse:
    p = Path(path).resolve()
    if OUTPUT_DIR.resolve() not in p.parents or not p.exists():
        raise HTTPException(status_code=404, detail="PDF introuvable")
    return FileResponse(p, media_type="application/pdf", filename=p.name)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str) -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    if index.exists() and not full_path.startswith("api/"):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
