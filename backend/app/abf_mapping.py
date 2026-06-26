from __future__ import annotations

from .calculations import estimate_financial_need, net_worth
from .formatting import compact_money, money
from .narratives import draft_agent_notes, draft_recommendations
from .schemas import AdvisorReview, ProspectSubmission


def build_abf_values(prospect: ProspectSubmission, review: AdvisorReview) -> dict[str, str]:
    i = prospect.identity
    c = prospect.contact
    e = prospect.employment
    fna = estimate_financial_need(prospect, review.replacement_years)
    worth = net_worth(prospect)
    rec1, rec2, pref = draft_recommendations(prospect)
    signed_date = review.signed_date.isoformat()
    final_coverage = review.final_recommended_coverage or fna["total_need"]
    notes = review.agent_notes or draft_agent_notes(prospect)

    return {
        # Repeated identity/signature fields across pages.
        "Insured Name": i.full_name,
        "Owner Name": i.full_name,
        "Advisor Name": review.advisor_name,
        "Advisor Phone": review.advisor_phone,
        "Advisor Email": review.advisor_email,
        "Date Signed-1": signed_date,
        "Date Signed-2": signed_date,
        "Date Signed-3": signed_date,
        # CSC page 5.
        "Gender": i.sex.value,
        "DOB": i.date_of_birth.isoformat(),
        "Marital Status": i.marital_status.value,
        "Place of Birth": i.place_of_birth,
        "Residency Status": i.residency_status,
        "Home Address": c.address,
        "City": c.city,
        "Province": c.province,
        "Postal Code": c.postal_code,
        "Email Insured": str(c.email),
        "Phone Number Insured": c.phone,
        "Employment/Occupation": e.occupation,
        "Employer's Name": e.employer_name,
        # Financial needs analysis page 6.
        "DebtsFuneral": money(fna["debts"]),
        "Creditcards": money(prospect.financial.credit_cards),
        "CarLoan": money(prospect.financial.car_loan),
        "Student Loan": money(prospect.financial.student_loan),
        "PersonalLoan": money(prospect.financial.personal_loan),
        "OtherDebts": money(prospect.financial.total_debts),
        "IncometobeReplaced": money(fna["income_replacement"]),
        "AnnualIncome": money(fna["annual_income"]),
        "Yearsofincome": str(review.replacement_years),
        "Mortgage": money(prospect.financial.mortgage),
        "EducationandChildcare": money(fna["education_childcare"]),
        "CurrentLife": money(fna["current_life"]),
        "TotalFNA": money(final_coverage),
        # Assets/passifs page 7.
        "AS1": money(prospect.financial.cash_savings),
        "AS14": money(worth["assets"]),
        "AS15": money(worth["net_worth"]),
        "AS12": money(worth["debts"]),
        "Additional Comments.0": "Brouillon calculé depuis le formulaire prospect; conseiller à valider.",
        # Product suitability page 8.
        "MonthlyNetIncome": money(e.monthly_net_income),
        "Expenses": money(prospect.financial.monthly_expenses),
        "DebtRepayment": money(prospect.financial.monthly_debt_repayment),
        "Savings": money(prospect.financial.monthly_savings),
        "Surplus": money(max(0, e.monthly_net_income - prospect.financial.monthly_expenses - prospect.financial.monthly_debt_repayment)),
        "Budget.0": money(review.recommendation_1_budget or prospect.goals.acceptable_monthly_budget),
        "Budget.1": money(review.recommendation_2_budget or prospect.goals.acceptable_monthly_budget),
        "Budget.2": money(review.client_preference_budget or prospect.goals.acceptable_monthly_budget),
        "FaceAmount": compact_money(final_coverage),
        "FaceAmount0": compact_money(final_coverage),
        "FaceAmount1": compact_money(final_coverage),
        "Rationale1": review.recommendation_1_notes or rec1,
        "Rationale2": review.recommendation_2_notes or rec2,
        "Rationale3": review.preference_notes or pref,
        # Agent notes page 10: split across lines.
        **{f"AgentNotes.{idx}": line for idx, line in enumerate(_split_notes(notes, 36))},
    }


def _split_notes(text: str, max_lines: int) -> list[str]:
    words = " ".join(text.split()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > 90 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:max_lines]
