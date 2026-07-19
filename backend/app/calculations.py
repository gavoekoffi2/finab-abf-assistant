from __future__ import annotations

from datetime import date

from .schemas import EmploymentInfo, IncomeType, ProspectSubmission

# Standard full-time assumption used to annualize an hourly wage.
HOURS_PER_WEEK = 40
WEEKS_PER_YEAR = 52


def annual_income(employment: EmploymentInfo) -> float:
    """Net annual income used as the replacement base.

    When the client reports an hourly wage we annualize it (rate x 40h x 52
    weeks); otherwise we fall back to the declared annual figure, or a monthly
    net income times twelve.
    """
    if employment.income_type == IncomeType.hourly and employment.hourly_rate:
        return employment.hourly_rate * HOURS_PER_WEEK * WEEKS_PER_YEAR
    return employment.annual_income or employment.monthly_net_income * 12


def age_on(dob: date | None, today: date | None = None) -> int | None:
    if not dob:
        return None
    today = today or date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return max(0, years)


def suggested_replacement_years(age: int | None) -> int:
    """Age-based coefficient for the number of years of income to replace.

    Younger clients protect a longer earning horizon, so the multiplier is
    larger. Confirmed business rule: <30 -> 30, 30-49 -> 20, 50+ -> 15.
    A missing age defaults to 20.
    """
    if age is None:
        return 20
    if age < 30:
        return 30
    if age < 50:
        return 20
    return 15


def resolve_replacement_years(prospect: ProspectSubmission, requested: int | None) -> int:
    """Use the advisor's explicit value when provided, otherwise suggest one
    from the client's age. `requested` of 0/None means 'auto'."""
    if requested:
        return requested
    return suggested_replacement_years(age_on(prospect.identity.date_of_birth))


def estimate_financial_need(
    prospect: ProspectSubmission,
    replacement_years: int | None = None,
    education_fund: float = 0.0,
) -> dict[str, float]:
    """Draft FNA only. Advisor must finalize before PDF export."""
    years = resolve_replacement_years(prospect, replacement_years)
    income = annual_income(prospect.employment)
    # 'Dettes et frais funéraires' excludes the mortgage: on the ABF form the
    # mortgage is its own line, added separately into the total below.
    debts = prospect.financial.total_debts or (
        prospect.financial.credit_cards
        + prospect.financial.car_loan
        + prospect.financial.student_loan
        + prospect.financial.personal_loan
    )
    mortgage = prospect.financial.mortgage
    income_replacement = income * years
    # Fonds d'éducation : jamais pré-rempli automatiquement — c'est le forfait
    # décidé par le conseiller (repère : 20 000 $ x 4 ans x nombre d'enfants).
    # Quand il est renseigné, il augmente le besoin total.
    education_childcare = float(education_fund or 0)
    current_life = prospect.insurance.existing_life_coverage
    # Formule imprimée sur le formulaire : Dettes et frais funéraires + Revenus
    # + Hypothèque + Éducation - Couverture d'assurance vie actuelle.
    total_need = max(0.0, debts + income_replacement + mortgage + education_childcare - current_life)
    return {
        "debts": debts,
        "annual_income": income,
        "replacement_years": float(years),
        "income_replacement": income_replacement,
        "mortgage": mortgage,
        "education_childcare": education_childcare,
        "current_life": current_life,
        "total_need": total_need,
    }


def net_worth(prospect: ProspectSubmission) -> dict[str, float]:
    assets = prospect.financial.total_assets or (
        prospect.financial.cash_savings + prospect.financial.personal_property
    )
    # 'Passif total (tiré de l'analyse des besoins financiers)' : same debts as
    # the FNA page (dettes et frais funéraires) plus the mortgage line.
    debts = (
        prospect.financial.total_debts
        or (
            prospect.financial.credit_cards
            + prospect.financial.car_loan
            + prospect.financial.student_loan
            + prospect.financial.personal_loan
        )
    ) + prospect.financial.mortgage
    return {"assets": assets, "debts": debts, "net_worth": assets - debts}
