from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .abf_mapping import build_abf_values
from .pdf_fill import fill_acroform
from .schemas import AbfGenerationRequest, AbfGenerationResult

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "samples" / "private" / "ABF_VIERGE.pdf"
OUTPUT_DIR = ROOT / "output"

app = FastAPI(title="FINAB ABF Assistant", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "finab-abf-assistant", "template_exists": TEMPLATE.exists()}


@app.post("/abf/generate", response_model=AbfGenerationResult)
def generate_abf(request: AbfGenerationRequest) -> AbfGenerationResult:
    if not request.review.reviewed_by_advisor and not request.allow_draft_watermark:
        raise HTTPException(
            status_code=400,
            detail="Le conseiller financier doit réviser/valider avant génération finale.",
        )
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
