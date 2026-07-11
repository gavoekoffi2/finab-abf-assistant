from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.abf_mapping import build_abf_values
from app.calculations import (
    annual_income,
    age_on,
    estimate_financial_need,
    suggested_replacement_years,
)
from app.narratives import draft_agent_notes, draft_recommendations
from app.schemas import (
    AdvisorReview,
    ClientIdentity,
    EmploymentInfo,
    GoalsInfo,
    IncomeType,
    OwnerInfo,
    ProspectSubmission,
    Sex,
)


def _prospect(**identity_overrides) -> ProspectSubmission:
    identity = dict(
        legal_last_name="LAWSON",
        first_names="Alphadir",
        date_of_birth=date(2001, 7, 23),
        sex=Sex.male,
        place_of_birth="Njissé au Cameroun",
        residency_status="Demandeur d'asile",
        arrival_in_canada=date(2025, 8, 1),
        dependents_count=0,
    )
    identity.update(identity_overrides)
    return ProspectSubmission(identity=ClientIdentity(**identity))


def test_hourly_wage_is_annualized() -> None:
    e = EmploymentInfo(income_type=IncomeType.hourly, hourly_rate=25)
    assert annual_income(e) == 25 * 40 * 52  # 52,000
    # A declared annual figure is used as-is when income type is annual.
    assert annual_income(EmploymentInfo(annual_income=60000)) == 60000


def test_age_coefficient_brackets() -> None:
    assert suggested_replacement_years(24) == 30  # < 30
    assert suggested_replacement_years(29) == 30
    assert suggested_replacement_years(30) == 20  # 30-49
    assert suggested_replacement_years(49) == 20
    assert suggested_replacement_years(50) == 15  # 50+
    assert suggested_replacement_years(None) == 20  # unknown age


def test_estimate_uses_age_coefficient_when_years_not_forced() -> None:
    prospect = _prospect()
    prospect.employment = EmploymentInfo(annual_income=60000)
    # 24-year-old -> coefficient 30 -> 60k * 30 = 1.8M when years auto (0/None).
    auto = estimate_financial_need(prospect, 0)
    assert auto["replacement_years"] == 30
    assert auto["income_replacement"] == 60000 * 30
    # An explicit advisor value wins over the age suggestion.
    forced = estimate_financial_need(prospect, 20)
    assert forced["replacement_years"] == 20
    assert forced["income_replacement"] == 60000 * 20


def test_owner_section_blank_when_insured_is_owner() -> None:
    prospect = _prospect()
    prospect.owner = OwnerInfo(insured_is_owner=True)
    values = build_abf_values(prospect, AdvisorReview())
    assert values["Owner Name"] == ""
    assert values["Relationship to Insured"] == ""


def test_owner_section_filled_for_third_party() -> None:
    prospect = _prospect()
    prospect.owner = OwnerInfo(insured_is_owner=False, name="Jean Payeur", relationship="Ami")
    values = build_abf_values(prospect, AdvisorReview())
    assert values["Owner Name"] == "Jean Payeur"
    assert values["Relationship to Insured"] == "Ami"


def test_goals_are_mapped_to_real_kyc_fields() -> None:
    prospect = _prospect()
    prospect.goals = GoalsInfo(
        short_term_goals="Régulariser mes documents",
        medium_term_goals="Acheter une voiture",
        long_term_goals="Bâtir ma liberté financière",
    )
    values = build_abf_values(prospect, AdvisorReview())
    # Question 1 (court terme) -> Text Field1/2; Question 2 (long) -> 3/4.
    assert values["Text Field1"] == "Régulariser mes documents"
    assert values["Text Field3"] == "Bâtir ma liberté financière"
    # Medium term has no dedicated slot, so it is preserved in 'autres' (9/10).
    assert "moyen terme" in values["Text Field9"].lower()
    assert "Acheter une voiture" in values["Text Field9"]


def test_agent_notes_are_substantial_and_personalized() -> None:
    prospect = _prospect(dependents_count=2)
    prospect.employment = EmploymentInfo(occupation="Serveur", employer_name="Bar Burrito", annual_income=60000)
    fna = estimate_financial_need(prospect, 0)
    notes = draft_agent_notes(prospect, fna, AdvisorReview())
    assert "Alphadir LAWSON" in notes
    assert "Canada" in notes
    assert "Demandeur d'asile" in notes
    assert "Bar Burrito" in notes
    # Should be a rich narrative, not a one-liner.
    assert len(notes.split()) >= 80


def test_recommendations_follow_example_structure() -> None:
    prospect = _prospect()
    prospect.employment = EmploymentInfo(annual_income=60000)
    review = AdvisorReview(replacement_years=20, critical_illness_amount=30000, client_preference_budget=300)
    fna = estimate_financial_need(prospect, 20)  # 1.2M
    rec1, rec2, pref = draft_recommendations(prospect, fna, review)
    assert "universelle" in rec1.lower()
    assert "maladies graves" in rec1.lower()
    assert "1 200 000" in rec1  # total need, french formatting
    assert "600 000" in rec1  # 50/50 split
    assert "croissante" in rec2.lower()
    assert "300 $" in pref  # preference budget surfaced


def test_existing_coverage_reduces_total_need() -> None:
    prospect = _prospect()
    prospect.employment = EmploymentInfo(annual_income=100000)  # 24yo -> 30 years
    prospect.insurance.has_existing_life_insurance = True
    prospect.insurance.existing_life_coverage = 2_400_000
    fna = estimate_financial_need(prospect, 0)
    assert fna["income_replacement"] == 3_000_000
    assert fna["current_life"] == 2_400_000
    # Total need is net of the existing coverage: 3,000,000 - 2,400,000.
    assert fna["total_need"] == 600_000
    values = build_abf_values(prospect, AdvisorReview())
    # Existing coverage surfaces on the FNA page and on every rec column.
    assert "2,400,000" in values["CurrentLife"]
    assert "2,400,000" in values["CurrentLife0"]
    assert "600,000" in values["TotalFNA"]


def test_education_fund_is_advisor_controlled_and_increases_need() -> None:
    prospect = _prospect(dependents_count=2)
    prospect.employment = EmploymentInfo(annual_income=100000)  # 24yo -> 30 years
    # Children alone never auto-fill the education fund: the advisor decides.
    auto = estimate_financial_need(prospect, 0)
    assert auto["education_childcare"] == 0
    assert auto["total_need"] == 3_000_000
    values = build_abf_values(prospect, AdvisorReview())
    assert values["EducationandChildcare"] == ""  # left blank for the advisor
    # The advisor's forfait (e.g. 20k x 4 years x 1 child) raises the total.
    fna = estimate_financial_need(prospect, 0, education_fund=80_000)
    assert fna["education_childcare"] == 80_000
    assert fna["total_need"] == 3_080_000
    values = build_abf_values(prospect, AdvisorReview(education_fund=80_000))
    assert "80,000" in values["EducationandChildcare"]
    assert "3,080,000" in values["TotalFNA"]


def test_monthly_surplus_always_computed() -> None:
    prospect = _prospect()
    prospect.employment = EmploymentInfo(annual_income=150000)  # 12,500 / month
    # No expenses/debt/savings declared -> surplus equals the net income.
    values = build_abf_values(prospect, AdvisorReview())
    assert "12,500" in values["MonthlyNetIncome"]
    assert "12,500" in values["Surplus"]
    # With declared outflows the surplus subtracts all three.
    prospect.financial.monthly_expenses = 4000
    prospect.financial.monthly_debt_repayment = 1000
    prospect.financial.monthly_savings = 500
    values = build_abf_values(prospect, AdvisorReview())
    assert "7,000" in values["Surplus"]  # 12,500 - 4,000 - 1,000 - 500


TEMPLATE = Path(__file__).resolve().parents[2] / "samples/private/ABF_VIERGE.pdf"


@pytest.mark.skipif(not TEMPLATE.exists(), reason="private ABF_VIERGE.pdf not available")
def test_generated_pdf_embeds_auto_calculation(tmp_path) -> None:
    """The exported ABF must keep recalculating itself in Adobe: every derived
    field carries a calculation script and the AcroForm declares the order."""
    import fitz

    from app.pdf_fill import fill_acroform

    prospect = _prospect()
    prospect.employment = EmploymentInfo(annual_income=50000)
    values = build_abf_values(prospect, AdvisorReview(replacement_years=15))
    output = tmp_path / "calc.pdf"
    fill_acroform(TEMPLATE, output, values)

    doc = fitz.open(output)
    try:
        scripted: dict[str, str] = {}
        for page in doc:
            for widget in page.widgets() or []:
                kind, ref = doc.xref_get_key(widget.xref, "AA/C/JS")
                if kind == "xref":
                    scripted[widget.field_name] = doc.xref_stream(int(ref.split()[0])).decode()
                elif kind == "string":
                    scripted[widget.field_name] = ref
        for name in ("DebtsFuneral", "IncometobeReplaced", "EducationandChildcare", "TotalFNA", "MonthlyNetIncome", "Surplus", "TotalFNA0", "CurrentLife0"):
            assert name in scripted, f"{name} lacks a calculation script"
        assert "FNUM('AnnualIncome')*FNUM('Yearsofincome')" in scripted["IncometobeReplaced"]
        assert "-FNUM('CurrentLife')" in scripted["TotalFNA"]
        assert "-FNUM('Savings')" in scripted["Surplus"]
        # Calculation order so intermediate totals resolve before the totals.
        catalog = doc.pdf_catalog()
        kind, value = doc.xref_get_key(catalog, "AcroForm")
        co_kind, co = (
            doc.xref_get_key(int(value.split()[0]), "CO")
            if kind == "xref"
            else doc.xref_get_key(catalog, "AcroForm/CO")
        )
        assert co_kind == "array" and co.count(" R") >= 10
    finally:
        doc.close()


@pytest.mark.skipif(not TEMPLATE.exists(), reason="private ABF_VIERGE.pdf not available")
def test_fills_real_template_pages(tmp_path) -> None:
    """Every mapped key must hit a real field and render on the actual form."""
    import fitz

    from app.pdf_fill import fill_acroform

    prospect = _prospect()
    prospect.employment = EmploymentInfo(occupation="Serveur", employer_name="Bar Burrito", annual_income=60000)
    prospect.financial.total_assets = 10000
    prospect.goals = GoalsInfo(
        short_term_goals="Régulariser mes documents",
        long_term_goals="Bâtir sa liberté financière",
        current_financial_situation="Acceptable",
        family_need_if_death="Ma famille",
        acceptable_monthly_budget=500,
    )
    review = AdvisorReview(replacement_years=20, final_recommended_coverage=1000000, client_preference_budget=300)
    values = build_abf_values(prospect, review)

    output = tmp_path / "generated.pdf"
    report = fill_acroform(TEMPLATE, output, values)
    assert report["pages_after"] == 16
    assert report["missing_fields"] == []  # no stray/guessed field names
    assert report["filled_widget_updates"] >= 150

    doc = fitz.open(output)
    try:
        kyc = doc[4].get_text()
        assert "Homme" in kyc and "Demandeur" in kyc and "Bar Burrito" in kyc
        assert "Régulariser mes documents" in kyc
        product = doc[7].get_text()
        assert "Vie Universelle" in product
        assert "600,000" in product and "1,200,000" in product  # rec 1/2 full need
        assert "500,000" in product and "1,000,000" in product  # preference reduced
        assert "24 ans" in doc[9].get_text()  # agent notes narrative
    finally:
        doc.close()
