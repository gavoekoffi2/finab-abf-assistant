from __future__ import annotations

from .schemas import ProspectSubmission


def estimate_financial_need(prospect: ProspectSubmission, replacement_years: int = 10) -> dict[str, float]:
    """Draft FNA only. Advisor must finalize before PDF export."""
    annual_income = prospect.employment.annual_income or prospect.employment.monthly_net_income * 12
    debts = prospect.financial.total_debts or (
        prospect.financial.credit_cards
        + prospect.financial.car_loan
        + prospect.financial.student_loan
        + prospect.financial.personal_loan
        + prospect.financial.mortgage
    )
    income_replacement = annual_income * replacement_years
    education_childcare = 0.0
    if prospect.identity.dependents_count:
        education_childcare = prospect.identity.dependents_count * 25_000
    current_life = prospect.insurance.existing_life_coverage
    total_need = max(0.0, debts + income_replacement + education_childcare - current_life)
    return {
        "debts": debts,
        "annual_income": annual_income,
        "replacement_years": float(replacement_years),
        "income_replacement": income_replacement,
        "education_childcare": education_childcare,
        "current_life": current_life,
        "total_need": total_need,
    }


def net_worth(prospect: ProspectSubmission) -> dict[str, float]:
    assets = prospect.financial.total_assets or (
        prospect.financial.cash_savings + prospect.financial.personal_property
    )
    debts = prospect.financial.total_debts
    return {"assets": assets, "debts": debts, "net_worth": assets - debts}
