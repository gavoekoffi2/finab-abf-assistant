#!/usr/bin/env python3
"""Proof of concept: fill the official Greatway ABF AcroForm without rebuilding layout.

This script MUST preserve the original PDF pages, colors and layout. It only updates
existing form fields in the official ABF PDF and writes a new PDF copy.
"""
from __future__ import annotations

from pathlib import Path
import json
import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "samples" / "private" / "ABF_VIERGE.pdf"
OUT = ROOT / "output" / "ABF_TEST_PRESERVE_LAYOUT.pdf"
REPORT = ROOT / "output" / "ABF_TEST_REPORT.json"

TEST_VALUES = {
    # Repeated field names update all widgets with the same name across pages.
    "Insured Name": "CLIENT TEST FINAB",
    "Owner Name": "CLIENT TEST FINAB",
    "Advisor Name": "KOFFI ABRAHAM AKPOBI",
    "Email Insured": "client.test@example.com",
    "Phone Number Insured": "5140000000",
    "DOB": "1990-01-15",
    "Place of Birth": "TOGO",
    "Marital Status": "Marié",
    "Residency Status": "Résident permanent",
    "Home Address": "123 Rue Exemple",
    "City": "Montréal",
    "Province": "QC",
    "Postal Code": "H1A 1A1",
    "Employment/Occupation": "Préposé aux bénéficiaires",
    "Employer's Name": "Employeur Exemple",
    "AnnualIncome": "C$ 50,000.00",
    "DebtsFuneral": "C$ 5,000.00",
    "OtherDebts": "C$ 10,000.00",
    "IncometobeReplaced": "C$ 500,000.00",
    "Yearsofincome": "10",
    "TotalFNA": "C$ 515,000.00",
    "AS1": "C$ 2,000.00",
    "AS14": "C$ 15,000.00",
    "AS15": "C$ 15,000.00",
    "Budget.0": "C$ 100.00",
    "Budget.1": "C$ 150.00",
    "Budget.2": "C$ 200.00",
    "FaceAmount": "$ 500,000",
    "Rationale1": "Brouillon IA à réviser par le conseiller financier avant présentation au client.",
    "Rationale2": "Option alternative selon le budget et les objectifs déclarés par le client.",
    "Rationale3": "Préférence client à confirmer après calcul final du conseiller.",
    "AgentNotes.0": "BROUILLON - préparé à partir du formulaire prospect.",
    "AgentNotes.1": "Le conseiller financier doit réviser et finaliser les calculs avant génération finale.",
    "Date Signed-1": "2026-06-26",
    "Date Signed-2": "2026-06-26",
    "Date Signed-3": "2026-06-26",
}


def fill_pdf(template: Path, output: Path) -> dict:
    if not template.exists():
        raise FileNotFoundError(template)

    doc = fitz.open(template)
    before_pages = len(doc)
    before_form = bool(doc.is_form_pdf)
    filled = []
    missing = []
    available = set()

    for page in doc:
        for widget in page.widgets() or []:
            available.add(widget.field_name)
            if widget.field_name in TEST_VALUES and widget.field_type_string in {"Text", "ComboBox"}:
                widget.field_value = TEST_VALUES[widget.field_name]
                widget.update()
                filled.append({
                    "page": page.number + 1,
                    "field": widget.field_name,
                    "value": TEST_VALUES[widget.field_name],
                })

    for key in TEST_VALUES:
        if key not in available:
            missing.append(key)

    output.parent.mkdir(parents=True, exist_ok=True)
    # garbage=3 compacts without rasterizing/rebuilding the page; deflate keeps size moderate.
    doc.save(output, garbage=3, deflate=True, incremental=False)
    doc.close()

    out_doc = fitz.open(output)
    report = {
        "template": str(template),
        "output": str(output),
        "pages_before": before_pages,
        "pages_after": len(out_doc),
        "is_form_pdf_before": before_form,
        "is_form_pdf_after": bool(out_doc.is_form_pdf),
        "filled_widget_updates": len(filled),
        "unique_fields_available": len(available),
        "missing_test_fields": missing,
        "filled_preview": filled[:40],
        "layout_preservation_rule": "The script updates existing AcroForm fields only; it does not redraw or reconstruct ABF pages.",
    }
    out_doc.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(fill_pdf(TEMPLATE, OUT), ensure_ascii=False, indent=2))
