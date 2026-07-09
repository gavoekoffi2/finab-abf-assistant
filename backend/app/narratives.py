from __future__ import annotations

from datetime import date

from .calculations import age_on
from .schemas import AdvisorReview, ProspectSubmission


def _fr_amount(value: float | int | None) -> str:
    """French-style money used inside the narratives: '1 200 000 $'."""
    return f"{float(value or 0):,.0f}".replace(",", " ") + " $"


def _sentence(text: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text[0].upper() + text[1:]


def draft_agent_notes(prospect: ProspectSubmission, fna: dict | None = None, review: AdvisorReview | None = None) -> str:
    """Rich 'Notes de l'agent' narrative describing how well the client is known.

    The goal is a substantial multi-paragraph text (the advisor only retouches
    it) covering arrival in Canada, residency status, family, employment,
    income, goals, the needs analysis result and the recommendation.
    """
    i = prospect.identity
    c = prospect.contact
    e = prospect.employment
    g = prospect.goals
    ins = prospect.insurance
    age = age_on(i.date_of_birth)
    parts: list[str] = []

    # --- Who the client is ---
    intro = f"{i.full_name}"
    if age is not None:
        intro += f" est âgé(e) de {age} ans"
    where = ", ".join(x for x in (c.city, c.province) if x)
    if where:
        intro += f" et réside à {where}"
    parts.append(_sentence(intro))

    if i.place_of_birth:
        parts.append(_sentence(f"Il/elle est originaire de {i.place_of_birth}"))
    if i.arrival_in_canada:
        arrival_year = i.arrival_in_canada.year if isinstance(i.arrival_in_canada, date) else str(i.arrival_in_canada)
        parts.append(_sentence(
            f"Arrivé(e) au Canada en {arrival_year}, il/elle s'établit progressivement et cherche à bâtir une stabilité financière durable"
        ))
    if i.residency_status:
        parts.append(_sentence(f"Son statut de résidence actuel est : {i.residency_status}"))

    # --- Family situation ---
    family = f"Sur le plan familial, {i.full_name} est {i.marital_status.value}"
    if i.dependents_count:
        family += f" et a {i.dependents_count} personne(s) à charge"
    parts.append(_sentence(family))

    # --- Employment & income ---
    if e.occupation:
        job = f"Sur le plan professionnel, il/elle occupe le poste de {e.occupation}"
        if e.employer_name:
            job += f" chez {e.employer_name}"
        parts.append(_sentence(job))
    income = (fna or {}).get("annual_income")
    if income:
        parts.append(_sentence(f"Son revenu net annuel est estimé à {_fr_amount(income)}"))

    # --- Goals ---
    if g.short_term_goals:
        parts.append(_sentence(f"À court terme, ses objectifs sont : {g.short_term_goals}"))
    if g.medium_term_goals:
        parts.append(_sentence(f"À moyen terme : {g.medium_term_goals}"))
    if g.long_term_goals:
        parts.append(_sentence(f"À long terme, il/elle souhaite : {g.long_term_goals}"))
    if g.current_financial_situation:
        parts.append(_sentence(f"Sa situation financière actuelle est décrite comme : {g.current_financial_situation}"))
    if g.family_need_if_death:
        parts.append(_sentence(f"En cas de décès prématuré, le besoin immédiat exprimé pour sa famille est : {g.family_need_if_death}"))

    # --- Existing coverage ---
    if ins.has_existing_life_insurance:
        parts.append(_sentence(f"Une assurance vie existante a été déclarée (capital d'environ {_fr_amount(ins.existing_life_coverage)})"))
    else:
        parts.append(_sentence("Aucune assurance vie individuelle active n'a été déclarée à ce jour"))

    # --- Needs analysis outcome & recommendation ---
    if fna:
        parts.append(_sentence(
            f"Une analyse complète de sa situation a été réalisée. Elle établit un besoin global de protection de "
            f"{_fr_amount(fna.get('total_need'))}, correspondant au remplacement de son revenu sur "
            f"{int(fna.get('replacement_years', 0))} ans, afin de protéger ses revenus futurs, de faire face aux "
            f"imprévus et de préparer son avenir financier"
        ))
    parts.append(_sentence(
        f"{i.full_name} a participé activement à la rencontre, a répondu avec transparence aux questions posées et "
        f"a démontré une bonne compréhension des caractéristiques, des avantages et des limites des solutions présentées"
    ))
    if review and review.agent_notes:
        parts.append(_sentence(review.agent_notes))
    parts.append(_sentence("Cette décision a été prise librement après avoir reçu toutes les explications nécessaires"))

    return " ".join(p for p in parts if p)


def draft_recommendations(
    prospect: ProspectSubmission,
    fna: dict | None = None,
    review: AdvisorReview | None = None,
) -> tuple[str, str, str]:
    i = prospect.identity
    total = (fna or {}).get("total_need") or 0
    years = int((fna or {}).get("replacement_years", 0) or 0)
    critical = review.critical_illness_amount if review else 30000
    half = round(total / 2) if total else 0
    pref_total = (review.final_recommended_coverage if review and review.final_recommended_coverage else total)
    pref_half = round(pref_total / 2) if pref_total else 0
    pref_budget = review.client_preference_budget if review else 0

    rec1 = _sentence(
        f"Nous recommandons une assurance vie universelle de {_fr_amount(half)}, combinée à une assurance "
        f"temporaire {years or 20} ans de {_fr_amount(half)} et une protection maladies graves de "
        f"{_fr_amount(critical)}. Cette stratégie procure une couverture totale de {_fr_amount(total)} tout en "
        f"permettant l'accumulation d'une valeur de rachat à long terme. Les {_fr_amount(total)} correspondent au "
        f"remplacement de son revenu sur {years or 20} ans"
    )
    rec2 = _sentence(
        f"Avec l'option 2, le client peut obtenir la même couverture de {_fr_amount(total)} pour une cotisation "
        f"comparable, avec une option de prestation de décès croissante. Le coût de l'assurance y est plus élevé "
        f"que celui de l'option uniforme ; voilà pourquoi cette variante est présentée à titre de comparaison"
    )
    pref = _sentence(
        f"Après avoir pris connaissance des deux recommandations, {i.full_name} a choisi une solution correspondant "
        f"davantage à son budget actuel. Étant nouvellement établi(e) au Canada, il/elle préfère commencer avec une "
        f"couverture de {_fr_amount(pref_total)} pour une cotisation de {_fr_amount(pref_budget)} par mois "
        f"({_fr_amount(pref_half)} universelle + {_fr_amount(pref_half)} temporaire + {_fr_amount(critical)} maladies "
        f"graves), et prévoit réévaluer sa protection progressivement lorsque sa situation financière le permettra"
    )
    return rec1, rec2, pref
