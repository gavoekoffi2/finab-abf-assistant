from __future__ import annotations

from datetime import date

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
    assert values["Owner Relationship"] == ""


def test_owner_section_filled_for_third_party() -> None:
    prospect = _prospect()
    prospect.owner = OwnerInfo(insured_is_owner=False, name="Jean Payeur", relationship="Ami")
    values = build_abf_values(prospect, AdvisorReview())
    assert values["Owner Name"] == "Jean Payeur"
    assert values["Owner Relationship"] == "Ami"


def test_goals_are_mapped_by_horizon() -> None:
    prospect = _prospect()
    prospect.goals = GoalsInfo(
        short_term_goals="Régulariser mes documents",
        medium_term_goals="Acheter une voiture",
        long_term_goals="Bâtir ma liberté financière",
    )
    values = build_abf_values(prospect, AdvisorReview())
    assert values["ShortTermGoals"] == "Régulariser mes documents"
    assert values["MediumTermGoals"] == "Acheter une voiture"
    assert values["LongTermGoals"] == "Bâtir ma liberté financière"


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
