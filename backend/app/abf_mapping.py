from __future__ import annotations

from .calculations import estimate_financial_need, net_worth
from .formatting import compact_money, money
from .narratives import draft_agent_notes, draft_recommendations
from .schemas import AdvisorReview, ProspectSubmission

# ComboBox options must match the template's declared values verbatim
# (including trailing whitespace / carriage returns) or the reader ignores them.
_UNIVERSAL_LIFE = "Vie Universelle"
_DB_UNIFORM = "Uniforme\r"
_DB_INCREASING = "Croissant"
_COI_TRA = "TRA \r"
_COI_UNIFORM = "Uniforme"
_TERM_10 = "Avenant Temporaire 10 ans "
_TERM_20 = "Avenant Temporaire 20 ans"
_CI_RIDER = "MG Temp. 10 ans - 25 affections"


def _two_lines(text: str, width: int = 95) -> tuple[str, str]:
    """Split a short answer across the two stacked line-fields the KYC page
    exposes for every objective question."""
    words = " ".join((text or "").split()).split()
    line1, line2 = "", ""
    for word in words:
        if len(f"{line1} {word}".strip()) <= width or not line1:
            line1 = f"{line1} {word}".strip()
        else:
            line2 = f"{line2} {word}".strip()
    return line1, line2


def build_abf_values(prospect: ProspectSubmission, review: AdvisorReview) -> dict[str, str]:
    i = prospect.identity
    c = prospect.contact
    e = prospect.employment
    g = prospect.goals
    o = prospect.owner
    fna = estimate_financial_need(prospect, review.replacement_years)
    worth = net_worth(prospect)
    rec1, rec2, pref = draft_recommendations(prospect, fna, review)
    signed_date = review.signed_date.isoformat()
    notes = review.agent_notes or draft_agent_notes(prospect, fna, review)

    # The needs analysis result (page 5 total). The recommendation columns 1 & 2
    # illustrate the full need; the client-preference column may be reduced to
    # the affordable coverage the advisor finalized.
    full_need = fna["total_need"]
    pref_cov = review.final_recommended_coverage or full_need
    existing = fna["current_life"]
    monthly_net = e.monthly_net_income or round(fna["annual_income"] / 12, 2)

    # Client budget block (page 7). The monthly surplus is always shown and is
    # simply: revenu net mensuel - dépenses - remboursement de dette - épargnes.
    # When the client declared none of those the surplus equals the net income
    # (e.g. 12 500 $ - 0 - 0 - 0 = 12 500 $), per the advisor's workflow.
    fin = prospect.financial
    monthly_surplus = max(
        0.0,
        monthly_net - fin.monthly_expenses - fin.monthly_debt_repayment - fin.monthly_savings,
    )

    # Cover page: leave the 'Propriétaire' line blank when the insured is also
    # the owner; otherwise name the paying client.
    owner_name = "" if o.insured_is_owner else (o.name or "")
    owner_rel = "" if o.insured_is_owner else o.relationship
    owner_email = "" if o.insured_is_owner else str(o.email)
    owner_phone = "" if o.insured_is_owner else o.phone

    # Objective answers (each question spans two stacked line-fields on page 5).
    short_l1, short_l2 = _two_lines(g.short_term_goals)
    long_l1, long_l2 = _two_lines(g.long_term_goals)
    situation_l1, situation_l2 = _two_lines(g.current_financial_situation)
    death_l1, death_l2 = _two_lines(g.family_need_if_death)
    other_text = g.additional_info
    if g.medium_term_goals:
        other_text = f"Objectifs à moyen terme : {g.medium_term_goals}. {other_text}".strip()
    other_l1, other_l2 = _two_lines(other_text)

    # Half of the coverage is illustrated as universal (montant nominal) and half
    # as term; critical illness sits beside the total, never inside it.
    half_need = round(full_need / 2)
    half_pref = round(pref_cov / 2)
    ci = review.critical_illness_amount

    return {
        # Repeated identity/signature fields across pages.
        "Insured Name": i.full_name,
        "Owner Name": owner_name,
        "Advisor Name": review.advisor_name,
        "Advisor Phone": review.advisor_phone,
        "Advisor Email": review.advisor_email,
        "Date Signed-1": signed_date,
        "Date Signed-2": signed_date,
        "Date Signed-3": signed_date,
        # CSC "Connaître son client" page.
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
        "Relationship to Insured": owner_rel,
        "Email Owner": owner_email,
        "Phone Number Owner": owner_phone,
        # Client financial goals — five questions, two line-fields each.
        "Text Field1": short_l1,
        "Text Field2": short_l2,
        "Text Field3": long_l1,
        "Text Field4": long_l2,
        "Text Field5": situation_l1,
        "Text Field6": situation_l2,
        "Text Field7": death_l1,
        "Text Field8": death_l2,
        "Text Field9": other_l1,
        "Text Field10": other_l2,
        # Financial needs analysis page. A lone debt lands in 'Autre dette'.
        "DebtsFuneral": money(fna["debts"]),
        "Creditcards": money(prospect.financial.credit_cards),
        "CarLoan": money(prospect.financial.car_loan),
        "Student Loan": money(prospect.financial.student_loan),
        "PersonalLoan": money(prospect.financial.personal_loan),
        "OtherDebts": money(prospect.financial.total_debts),
        "IncometobeReplaced": money(fna["income_replacement"]),
        "AnnualIncome": money(fna["annual_income"]),
        "Yearsofincome": str(int(fna["replacement_years"])),
        "Mortgage": money(prospect.financial.mortgage),
        "EducationandChildcare": money(fna["education_childcare"]),
        "CurrentLife": money(existing),
        "TotalFNA": money(full_need),
        # Assets/passifs page. A lone asset lands in 'Autres Biens' (AS10).
        # Actifs section total = AS11; net-worth box: AS12 = total assets,
        # AS14 = total liabilities, AS15 = net worth (assets - debts).
        "AS1": money(prospect.financial.cash_savings),
        "AS10": money(worth["assets"]),
        "AS11": money(worth["assets"]),
        "AS12": money(worth["assets"]),
        "AS14": money(worth["debts"]),
        "AS15": money(worth["net_worth"]),
        "Additional Comments.0": "Brouillon calculé depuis le formulaire prospect; conseiller à valider.",
        # Product suitability page — client budget. Monthly net income defaults
        # to the annual figure / 12 when the client did not give a monthly one.
        "MonthlyNetIncome": money(monthly_net),
        "Expenses": money(fin.monthly_expenses) if fin.monthly_expenses else "",
        "DebtRepayment": money(fin.monthly_debt_repayment) if fin.monthly_debt_repayment else "",
        "Savings": money(fin.monthly_savings) if fin.monthly_savings else "",
        "Surplus": money(monthly_surplus),
        "Budget.0": money(review.recommendation_1_budget or prospect.goals.acceptable_monthly_budget),
        "Budget.1": money(review.recommendation_2_budget or prospect.goals.acceptable_monthly_budget),
        "Budget.2": money(review.client_preference_budget or prospect.goals.acceptable_monthly_budget),
        # Product type + death-benefit / cost options (advisor can override).
        "Product Type 7": _UNIVERSAL_LIFE,
        "Product Type 8": _UNIVERSAL_LIFE,
        "Product Type 9": _UNIVERSAL_LIFE,
        "Death Benefit Option 2": _DB_UNIFORM,
        "Death Benefit Option 3": _DB_INCREASING,
        "Death Benefit Option 4": _DB_UNIFORM,
        "COI 2": _COI_TRA,
        "COI 3": _COI_UNIFORM,
        "COI 4": _COI_TRA,
        # Montant nominal (universal) per column.
        "FaceAmount": compact_money(half_need),
        "FaceAmount0": compact_money(half_need),
        "FaceAmount1": compact_money(half_pref),
        # Riders: T10 (line 1), T20 amount (line 2), critical illness (line 3).
        "Combo Box 12": _TERM_10,
        "Combo Box 19": _TERM_10,
        "Combo Box 18": _TERM_20,
        "Combo Box 22": _TERM_20,
        "CI Rider Combo 2": _CI_RIDER,
        "CI Rider Combo 3": _CI_RIDER,
        "CI Rider Combo 4": _CI_RIDER,
        "Text Field18": compact_money(half_need),
        "Text Field24": compact_money(half_need),
        "Text Field30": compact_money(half_pref),
        "Text Field19": compact_money(ci),
        "Text Field25": compact_money(ci),
        "Text Field31": compact_money(ci),
        # Prestation de décès totale per column.
        "Text Field16": compact_money(full_need),
        "Text Field22": compact_money(full_need),
        "Text Field28": compact_money(pref_cov),
        # Couverture d'assurance existante per column.
        "CurrentLife1": compact_money(existing),
        "CurrentLife0": compact_money(existing),
        "CurrentLife2": compact_money(existing),
        # Total des besoins d'assurance per column.
        "TotalFNA0": compact_money(full_need),
        "TotalFNA1": compact_money(full_need),
        "TotalFNA2": compact_money(pref_cov),
        "Rationale1": review.recommendation_1_notes or rec1,
        "Rationale2": review.recommendation_2_notes or rec2,
        "Rationale3": review.preference_notes or pref,
        # Agent notes page: split across the 36 line-fields.
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
