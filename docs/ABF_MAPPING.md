# Mapping formulaire prospect → ABF Greatway

## Règle critique

Le mapping remplit uniquement les champs AcroForm existants du PDF officiel `ABF_VIERGE.pdf`.
Aucune page n'est reconstruite. La mise en page officielle est préservée.

## Champs ABF déjà mappés dans le MVP

| Formulaire intégré | Champ ABF PDF | Section ABF |
|---|---|---|
| Prénoms + Nom légal | `Insured Name` | pages répétées / identité |
| Prénoms + Nom légal | `Owner Name` | propriétaire si même personne |
| Nom conseiller | `Advisor Name` | pages répétées |
| Téléphone conseiller | `Advisor Phone` | contact conseiller |
| Email conseiller | `Advisor Email` | contact conseiller |
| Date de validation | `Date Signed-1/2/3` | signatures |
| Sexe | `Gender` | CSC page 5 |
| Date naissance | `DOB` | CSC page 5 |
| État civil | `Marital Status` | CSC page 5 |
| Lieu naissance | `Place of Birth` | CSC page 5 |
| Statut résidence | `Residency Status` | CSC page 5 |
| Adresse | `Home Address` | CSC page 5 |
| Ville | `City` | CSC page 5 |
| Province | `Province` | CSC page 5 |
| Code postal | `Postal Code` | CSC page 5 |
| Courriel | `Email Insured` | CSC page 5 |
| Téléphone | `Phone Number Insured` | CSC page 5 |
| Profession | `Employment/Occupation` | CSC page 5 |
| Employeur | `Employer's Name` | CSC page 5 |
| Total dettes | `DebtsFuneral`, `OtherDebts` | analyse besoins page 6 |
| Revenu annuel | `AnnualIncome` | analyse besoins page 6 |
| Années remplacement validées | `Yearsofincome` | analyse besoins page 6 |
| Couverture actuelle | `CurrentLife` | analyse besoins page 6 |
| Couverture finale validée | `TotalFNA`, `FaceAmount*` | besoins + adéquation produit |
| Actifs | `AS14` | actifs/passifs page 7 |
| Valeur nette | `AS15` | actifs/passifs page 7 |
| Revenu net mensuel | `MonthlyNetIncome` | adéquation produit page 8 |
| Dépenses mensuelles | `Expenses` | adéquation produit page 8 |
| Remboursement dette | `DebtRepayment` | adéquation produit page 8 |
| Épargne mensuelle | `Savings` | adéquation produit page 8 |
| Budgets validés | `Budget.0`, `Budget.1`, `Budget.2` | adéquation produit page 8 |
| Notes/recommandations | `Rationale1`, `Rationale2`, `Rationale3` | adéquation produit page 8 |
| Notes agent | `AgentNotes.0...35` | notes page 10 |

## Étapes non automatiques

Ces éléments doivent rester sous contrôle du conseiller :

- calcul officiel final ;
- produit recommandé exact ;
- avenants ;
- prime réelle ;
- remplacement ou non d'une assurance existante ;
- signatures ;
- validation conformité.

## Preuve technique actuelle

Test automatisé : `backend/tests/test_abf_generation.py`

Vérifie :

- 16 pages avant/après ;
- PDF reste formulaire ;
- champs remplis ;
- aucun champ mappé manquant ;
- le nom client apparaît dans le PDF généré ;
- mise en page préservée par non-reconstruction.
