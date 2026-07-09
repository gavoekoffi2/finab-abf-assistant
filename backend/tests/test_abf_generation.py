from __future__ import annotations

import json
from pathlib import Path

import fitz

from app.abf_mapping import build_abf_values
from app.pdf_fill import fill_acroform
from app.schemas import AbfGenerationRequest

ROOT = Path(__file__).resolve().parents[2]


def load_payload() -> AbfGenerationRequest:
    data = json.loads((ROOT / "samples/private/jocelina_payload.json").read_text(encoding="utf-8"))
    return AbfGenerationRequest.model_validate(data)


def test_mapping_contains_core_abf_fields() -> None:
    req = load_payload()
    values = build_abf_values(req.prospect, req.review)
    assert values["Insured Name"] == "Jocelina TUSEWU NZAZI"
    assert values["DOB"] == "1995-05-17"
    assert values["TotalFNA"] == "C$ 908,000.00"
    assert "conseiller" in values["AgentNotes.0"].lower() or "originaire" in values["AgentNotes.0"].lower()


def test_fill_preserves_abf_layout(tmp_path: Path) -> None:
    req = load_payload()
    values = build_abf_values(req.prospect, req.review)
    template = ROOT / "samples/private/ABF_VIERGE.pdf"
    output = tmp_path / "abf_test.pdf"
    report = fill_acroform(template, output, values)
    assert report["pages_before"] == 16
    assert report["pages_after"] == 16
    assert report["is_form_pdf_before"] is True
    assert report["is_form_pdf_after"] is True
    assert report["layout_preserved"] is True
    assert report["filled_widget_updates"] >= 50
    assert not report["missing_fields"]

    doc = fitz.open(output)
    assert len(doc) == 16
    text = "\n".join(page.get_text() for page in doc)
    assert "Jocelina TUSEWU NZAZI" in text
