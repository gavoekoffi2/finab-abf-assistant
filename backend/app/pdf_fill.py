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


# --- Embedded PDF auto-calculation ------------------------------------------
# The exported ABF keeps recalculating itself when edited later in Adobe
# Acrobat/Reader: every derived field carries an AcroForm calculation script
# (/AA /C) and the AcroForm /CO array orders them so intermediate totals
# (dettes, revenus à remplacer, éducation) resolve before the grand total.
#
# The helpers are inlined in each script because field-level JavaScript runs
# in its own context. FNUM parses any money format we or the advisor may
# write ("C$ 5,000.00", "$ 5 000", "5000,50"); CMON/SMON reproduce the
# backend money()/compact_money() formats so recalculated values look
# identical to the generated ones.
_JS_PREAMBLE = (
    # Capture the Doc once: `this` is only guaranteed to be the document at
    # the top level of a field script, not inside the helper functions.
    "var DOC=this;"
    "var FNUM=function(n){var f=DOC.getField(n);if(!f)return 0;"
    "var s=String(f.value==null?'':f.value).replace(/[^0-9.,-]/g,'');"
    "if(s.indexOf('.')>=0&&s.indexOf(',')>=0){s=s.replace(/,/g,'');}"
    "else if(s.indexOf(',')>=0){s=/,[0-9]{1,2}$/.test(s)?s.replace(',','.'):s.replace(/,/g,'');}"
    "var v=parseFloat(s);return isNaN(v)?0:v;};"
    "var FTXT=function(n){var f=DOC.getField(n);"
    "return f?String(f.value==null?'':f.value).replace(/\\s/g,'')!=='':false;};"
    "var CMON=function(v){return 'C$ '+util.printf('%,0.2f',v);};"
    "var SMON=function(v){return '$ '+util.printf('%,0.0f',v);};"
)

_DEBT_ITEM_FIELDS = (
    "Creditcards",
    "LinesofCredits",
    "CarLoan",
    "Student Loan",
    "PersonalLoan",
    "OtherDebts",
    "Funeral Expense",
)

_CALC_SCRIPTS: dict[str, str] = {
    # Total de la section 'Dettes et frais funéraires' (l'hypothèque a sa
    # propre ligne et entre séparément dans le besoin total).
    "DebtsFuneral": "event.value=CMON(" + "+".join(f"FNUM('{name}')" for name in _DEBT_ITEM_FIELDS) + ");",
    # Revenus à remplacer = revenu annuel x nombre d'années.
    "IncometobeReplaced": "event.value=CMON(FNUM('AnnualIncome')*FNUM('Yearsofincome'));",
    # Total éducation + garde d'enfants : calculé depuis les deux sous-lignes
    # seulement quand l'une d'elles est remplie, pour que le conseiller puisse
    # aussi taper un forfait directement dans le total.
    "EducationandChildcare": (
        "if(FTXT('EducationFund')||FTXT('ChildCare')){"
        "event.value=CMON(FNUM('EducationFund')+FNUM('ChildCare'));}"
    ),
    # Besoin total = Dettes + Revenus à remplacer + Hypothèque + Éducation
    # - Couverture d'assurance vie actuelle (jamais négatif).
    "TotalFNA": (
        "event.value=CMON(Math.max(0,FNUM('DebtsFuneral')+FNUM('IncometobeReplaced')"
        "+FNUM('Mortgage')+FNUM('EducationandChildcare')-FNUM('CurrentLife')));"
    ),
    # Budget client : revenu mensuel = revenu annuel / 12, et surplus =
    # revenu mensuel - dépenses - remboursement de dettes - épargnes.
    "MonthlyNetIncome": "var a=FNUM('AnnualIncome');if(a>0){event.value=CMON(a/12);}",
    "Surplus": (
        "event.value=CMON(Math.max(0,FNUM('MonthlyNetIncome')-FNUM('Expenses')"
        "-FNUM('DebtRepayment')-FNUM('Savings')));"
    ),
    # Les colonnes recommandation 1 & 2 illustrent toujours le besoin complet
    # et la couverture existante suit sur les trois colonnes. La colonne
    # 'préférence client' et la répartition universelle/temporaire restent
    # libres : ce sont des choix du conseiller.
    "TotalFNA0": "event.value=SMON(FNUM('TotalFNA'));",
    "TotalFNA1": "event.value=SMON(FNUM('TotalFNA'));",
    "Text Field16": "event.value=SMON(FNUM('TotalFNA'));",
    "Text Field22": "event.value=SMON(FNUM('TotalFNA'));",
    "CurrentLife0": "event.value=SMON(FNUM('CurrentLife'));",
    "CurrentLife1": "event.value=SMON(FNUM('CurrentLife'));",
    "CurrentLife2": "event.value=SMON(FNUM('CurrentLife'));",
}

# Dependencies first, grand totals next, mirrored columns last.
_CALC_ORDER = (
    "DebtsFuneral",
    "IncometobeReplaced",
    "EducationandChildcare",
    "MonthlyNetIncome",
    "TotalFNA",
    "Surplus",
    "TotalFNA0",
    "TotalFNA1",
    "Text Field16",
    "Text Field22",
    "CurrentLife0",
    "CurrentLife1",
    "CurrentLife2",
)


def _set_calculation_order(doc: fitz.Document, refs: list[str]) -> None:
    array = "[" + " ".join(refs) + "]"
    catalog = doc.pdf_catalog()
    kind, value = doc.xref_get_key(catalog, "AcroForm")
    if kind == "xref":
        doc.xref_set_key(int(value.split()[0]), "CO", array)
    else:
        doc.xref_set_key(catalog, "AcroForm/CO", array)


def attach_calculation_scripts(doc: fitz.Document) -> int:
    """Embed the auto-calculation JavaScript into the AcroForm fields."""
    attached = 0
    field_xrefs: dict[str, int] = {}
    for page in doc:
        for widget in page.widgets() or []:
            name = widget.field_name
            field_xrefs.setdefault(name, widget.xref)
            script = _CALC_SCRIPTS.get(name)
            if script and widget.field_type_string in _EDITABLE_TYPES:
                widget.script_calc = _JS_PREAMBLE + script
                widget.update()
                attached += 1
    order = [f"{field_xrefs[name]} 0 R" for name in _CALC_ORDER if name in field_xrefs]
    if order:
        _set_calculation_order(doc, order)
    return attached


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

    attach_calculation_scripts(doc)
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

    # Older generated PDFs may predate the embedded auto-calculation: attach
    # (or refresh) the scripts on every direct-edit pass too.
    attach_calculation_scripts(doc)
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
