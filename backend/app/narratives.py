from __future__ import annotations

from .formatting import money, truncate_field
from .schemas import ProspectSubmission


def draft_agent_notes(prospect: ProspectSubmission) -> str:
    i = prospect.identity
    g = prospect.goals
    f = prospect.financial
    ins = prospect.insurance
    parts = [
        f"BROUILLON À RÉVISER — {i.full_name} a fourni ses renseignements via le formulaire prospect FINAB.",
        f"Situation familiale: {i.marital_status.value}, personnes à charge: {i.dependents_count}.",
    ]
    if prospect.employment.occupation:
        parts.append(f"Profession/emploi: {prospect.employment.occupation}.")
    if g.priority_projects:
        parts.append(f"Priorités déclarées: {truncate_field(g.priority_projects, 220)}")
    if g.family_need_if_death:
        parts.append(f"Besoin exprimé en cas de décès prématuré: {truncate_field(g.family_need_if_death, 220)}")
    parts.append(
        f"Budget mensuel indiqué: {money(g.acceptable_monthly_budget)}. "
        "Le conseiller financier doit finaliser les calculs et confirmer la recommandation avec le client."
    )
    if ins.has_existing_life_insurance:
        parts.append(f"Assurance existante déclarée: {money(ins.existing_life_coverage)}.")
    else:
        parts.append("Aucune assurance vie individuelle active déclarée ou information à confirmer.")
    if f.total_debts:
        parts.append(f"Passifs déclarés: {money(f.total_debts)}.")
    return " ".join(parts)


def draft_recommendations(prospect: ProspectSubmission) -> tuple[str, str, str]:
    budget = prospect.goals.acceptable_monthly_budget
    base = (
        "Brouillon généré à partir des renseignements du prospect. "
        "La couverture, les avenants et le budget doivent être confirmés par le conseiller financier."
    )
    rec1 = f"Option protection familiale équilibrée selon le budget déclaré ({money(budget)}). {base}"
    rec2 = "Option protection renforcée si le client accepte une prime plus élevée et souhaite augmenter l'héritage financier. " + base
    pref = "Préférence client à confirmer pendant la rencontre de révision avec le conseiller. " + base
    return rec1, rec2, pref
