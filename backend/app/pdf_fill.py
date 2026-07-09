from __future__ import annotations

from pathlib import Path
from typing import Mapping

import fitz

_EDITABLE_TYPES = {"Text", "ComboBox"}
_MULTILINE_FLAG = 1 << 12  # Ff bit 13 (Multiline) per the PDF spec.

# NOTE: we deliberately do NOT set the AcroForm NeedAppearances flag. PyMuPDF's
# widget.update() bakes a fresh appearance stream (/AP) holding the single
# current value with the field's own bold default appearance. Setting
# NeedAppearances on top asks readers to re-render the value over that baked
# appearance, which is what caused the old and new values to overlap in the
# same field. Relying on the baked /AP keeps one clean, bold value in every
# reader — identical to the original fill.


def _keep_editable(widget: fitz.Widget) -> None:
    # Clear the read-only bit (Ff bit 1) so the field stays editable in the
    # browser/PDF reader until the counselor locks the final document.
    widget.field_flags = int(widget.field_flags or 0) & ~1


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
            if widget.field_type_string in _EDITABLE_TYPES:
                # Keep every generated AcroForm widget editable in the
                # browser/PDF reader, including fields that are not populated by
                # the server but may need a counselor correction later.
                _keep_editable(widget)
            if name not in values:
                if widget.field_type_string in _EDITABLE_TYPES:
                    widget.update()
                continue
            if widget.field_type_string not in _EDITABLE_TYPES:
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


def list_acroform_fields(source: Path) -> list[dict]:
    """Return the editable AcroForm fields with their on-page geometry.

    Coordinates are normalized (0..1) against each page so the frontend can
    overlay a real input exactly on top of the widget shown in the rendered
    page image, without guessing positions.
    """
    doc = fitz.open(source)
    fields: list[dict] = []
    try:
        for page in doc:
            page_rect = page.rect
            width = page_rect.width or 1
            height = page_rect.height or 1
            for widget in page.widgets() or []:
                if widget.field_type_string not in _EDITABLE_TYPES:
                    continue
                rect = widget.rect
                fields.append(
                    {
                        "name": widget.field_name,
                        "value": widget.field_value or "",
                        "type": widget.field_type_string,
                        "page": page.number,
                        "rect": [
                            (rect.x0 - page_rect.x0) / width,
                            (rect.y0 - page_rect.y0) / height,
                            (rect.x1 - page_rect.x0) / width,
                            (rect.y1 - page_rect.y0) / height,
                        ],
                        "multiline": bool(int(widget.field_flags or 0) & _MULTILINE_FLAG),
                        "max_length": int(getattr(widget, "text_maxlen", 0) or 0),
                        "options": list(getattr(widget, "choice_values", None) or []),
                    }
                )
    finally:
        doc.close()
    return fields


def update_acroform_fields(source: Path, output: Path, values: Mapping[str, str]) -> dict:
    """Edit only the named AcroForm fields on an already generated PDF.

    The existing document is opened and patched in place (every other field,
    page and visual element is preserved) instead of regenerating the ABF from
    the original web form. Fields stay editable and widget.update() re-bakes the
    appearance so each edited field shows a single clean value with no leftover
    of the previous text underneath.
    """
    if not source.exists():
        raise FileNotFoundError(source)
    doc = fitz.open(source)
    before_pages = len(doc)
    before_form = bool(doc.is_form_pdf)
    available: set[str] = set()
    updated = 0

    for page in doc:
        for widget in page.widgets() or []:
            if widget.field_type_string not in _EDITABLE_TYPES:
                continue
            name = widget.field_name
            available.add(name)
            _keep_editable(widget)
            if name in values:
                widget.field_value = str(values[name])
                widget.update()
                updated += 1
            else:
                widget.update()

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output, garbage=3, deflate=True, incremental=False)
    doc.close()

    out_doc = fitz.open(output)
    report = {
        "pages_before": before_pages,
        "pages_after": len(out_doc),
        "is_form_pdf_before": before_form,
        "is_form_pdf_after": bool(out_doc.is_form_pdf),
        "filled_widget_updates": updated,
        "missing_fields": [key for key in values if key not in available],
        "layout_preserved": before_pages == len(out_doc),
    }
    out_doc.close()
    return report
