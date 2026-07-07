from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.pdf_fill import list_acroform_fields, update_acroform_fields


def _build_form(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    for index, (name, value) in enumerate(
        [("Insured Name", "Alice"), ("Advisor Name", ""), ("AgentNotes.0", "note")]
    ):
        widget = fitz.Widget()
        widget.field_name = name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(50, 50 + index * 60, 350, 90 + index * 60)
        widget.field_value = value
        page.add_widget(widget)
    doc.save(path)
    doc.close()


def test_list_acroform_fields_reports_geometry(tmp_path: Path) -> None:
    source = tmp_path / "form.pdf"
    _build_form(source)
    fields = list_acroform_fields(source)
    by_name = {field["name"]: field for field in fields}
    assert set(by_name) == {"Insured Name", "Advisor Name", "AgentNotes.0"}
    insured = by_name["Insured Name"]
    assert insured["value"] == "Alice"
    assert insured["page"] == 0
    x0, y0, x1, y1 = insured["rect"]
    assert 0 <= x0 < x1 <= 1
    assert 0 <= y0 < y1 <= 1


def test_update_acroform_fields_persists_and_stays_editable(tmp_path: Path) -> None:
    source = tmp_path / "form.pdf"
    output = tmp_path / "form_edited.pdf"
    _build_form(source)

    report = update_acroform_fields(
        source, output, {"Insured Name": "Alice EDITED", "Advisor Name": "Bob Conseiller"}
    )
    assert report["filled_widget_updates"] == 2
    assert report["is_form_pdf_after"] is True
    assert report["layout_preserved"] is True
    assert not report["missing_fields"]

    edited = {field["name"]: field["value"] for field in list_acroform_fields(output)}
    assert edited["Insured Name"] == "Alice EDITED"
    assert edited["Advisor Name"] == "Bob Conseiller"
    assert edited["AgentNotes.0"] == "note"  # untouched field is preserved

    doc = fitz.open(output)
    try:
        text = doc[0].get_text()
        # The edited field shows a single clean value: the previous text must not
        # remain underneath, and the new value must appear exactly once.
        assert "Alice EDITED" in text
        assert text.count("Alice EDITED") == 1
        assert "Alice" not in text.replace("Alice EDITED", "")  # no leftover old value
        # NeedAppearances is intentionally NOT set so readers keep the baked,
        # single-value appearance instead of re-rendering over it.
        catalog = doc.pdf_catalog()
        assert doc.xref_get_key(catalog, "AcroForm/NeedAppearances")[0] == "null"
        for widget in doc[0].widgets() or []:
            assert not (int(widget.field_flags or 0) & 1)  # read-only bit cleared
    finally:
        doc.close()


def test_update_acroform_fields_reports_unknown_field(tmp_path: Path) -> None:
    source = tmp_path / "form.pdf"
    output = tmp_path / "form_edited.pdf"
    _build_form(source)
    report = update_acroform_fields(source, output, {"Does Not Exist": "x"})
    assert report["missing_fields"] == ["Does Not Exist"]
    assert report["filled_widget_updates"] == 0


def test_edit_filled_pdf_fields_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reopen a generated ABF, edit a field directly, save, and confirm it persists."""
    template = tmp_path / "template.pdf"
    _build_form(template)  # exposes 'Insured Name', 'Advisor Name', 'AgentNotes.0'
    monkeypatch.setattr(main, "TEMPLATE", template)

    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "KOFFI.AKPOBI@MYGREATWAY.CA", "password": "Finab-ABF-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    payload = {
        "identity": {"legal_last_name": "PDF", "first_names": "Client", "date_of_birth": "1990-01-01", "marital_status": "célibataire"},
        "contact": {"phone": "5140000000", "email": "client-fields@example.com", "address": "1 Rue A"},
        "employment": {"occupation": "Employé", "annual_income": 40000},
        "goals": {"priority_projects": "Protection famille", "acceptable_monthly_budget": 150},
        "meeting": {"availability": "Soir", "consent_acknowledged": True},
    }
    prospect_id = client.post("/api/prospects", json=payload).json()["id"]
    generated = client.post(f"/api/prospects/{prospect_id}/generate-abf", headers=headers, json={})
    assert generated.status_code == 200
    source_path = generated.json()["output_path"]

    listed = client.get(f"/api/pdf/fields?path={source_path}", headers=headers)
    assert listed.status_code == 200
    names = {field["name"] for field in listed.json()["fields"]}
    assert {"Insured Name", "Advisor Name"} <= names

    edited = client.patch(
        f"/api/prospects/{prospect_id}/pdf-fields",
        headers=headers,
        json={"path": source_path, "fields": {"Advisor Name": "Conseiller Corrigé"}},
    )
    assert edited.status_code == 200
    output_path = edited.json()["output_path"]
    assert output_path != source_path
    assert Path(output_path).exists()

    persisted = {field["name"]: field["value"] for field in list_acroform_fields(Path(output_path))}
    assert persisted["Advisor Name"] == "Conseiller Corrigé"

    # An empty field payload is rejected so we never silently rewrite the PDF.
    empty = client.patch(
        f"/api/prospects/{prospect_id}/pdf-fields",
        headers=headers,
        json={"path": source_path, "fields": {}},
    )
    assert empty.status_code == 400

    Path(source_path).unlink(missing_ok=True)
    Path(output_path).unlink(missing_ok=True)
