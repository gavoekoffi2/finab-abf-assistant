from __future__ import annotations

from pathlib import Path
from typing import Mapping

import fitz


def fill_acroform(template: Path, output: Path, values: Mapping[str, str]) -> dict:
    """Fill existing AcroForm fields only. Never reconstruct the ABF layout."""
    if not template.exists():
        raise FileNotFoundError(template)
    doc = fitz.open(template)
    before_pages = len(doc)
    before_form = bool(doc.is_form_pdf)
    filled = []
    available = set()

    for page in doc:
        for widget in page.widgets() or []:
            name = widget.field_name
            available.add(name)
            if name not in values:
                continue
            if widget.field_type_string not in {"Text", "ComboBox"}:
                continue
            widget.field_value = str(values[name])
            widget.update()
            filled.append({"page": page.number + 1, "field": name})

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output, garbage=3, deflate=True, incremental=False)
    doc.close()

    out_doc = fitz.open(output)
    report = {
        "pages_before": before_pages,
        "pages_after": len(out_doc),
        "is_form_pdf_before": before_form,
        "is_form_pdf_after": bool(out_doc.is_form_pdf),
        "filled_widget_updates": len(filled),
        "missing_fields": [key for key in values if key not in available],
        "layout_preserved": before_pages == len(out_doc),
    }
    out_doc.close()
    return report
