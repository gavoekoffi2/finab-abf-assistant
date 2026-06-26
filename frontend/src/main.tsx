import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';
import './styles.css';

type FormState = {
  legalLastName: string;
  firstNames: string;
  dateOfBirth: string;
  placeOfBirth: string;
  maritalStatus: string;
  dependents: string;
  arrivalInCanada: string;
  phone: string;
  email: string;
  address: string;
  postalCode: string;
  occupation: string;
  employerAddress: string;
  annualIncome: string;
  totalAssets: string;
  totalDebts: string;
  hasExistingInsurance: string;
  existingInsuranceDetails: string;
  noInsuranceReason: string;
  acceptableBudget: string;
  height: string;
  weight: string;
  availability: string;
  priorityProjects: string;
};

const initialForm: FormState = {
  legalLastName: '',
  firstNames: '',
  dateOfBirth: '',
  placeOfBirth: '',
  maritalStatus: '',
  dependents: '',
  arrivalInCanada: '',
  phone: '',
  email: '',
  address: '',
  postalCode: '',
  occupation: '',
  employerAddress: '',
  annualIncome: '',
  totalAssets: '',
  totalDebts: '',
  hasExistingInsurance: '',
  existingInsuranceDetails: '',
  noInsuranceReason: '',
  acceptableBudget: '',
  height: '',
  weight: '',
  availability: '',
  priorityProjects: '',
};

const api = async <T,>(url: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

const numberValue = (value: string) => Number(String(value || '').replace(/[^0-9.,]/g, '').replace(',', '.')) || 0;
const parseAddress = (value: string) => {
  const parts = value.split(',').map((part) => part.trim()).filter(Boolean);
  return {
    address: parts[0] || value,
    city: parts[1] || '',
    province: parts[2] || 'QC',
  };
};

function payloadFromForm(form: FormState) {
  const parsedAddress = parseAddress(form.address);
  const hasInsurance = form.hasExistingInsurance === 'oui';
  return {
    identity: {
      legal_last_name: form.legalLastName,
      first_names: form.firstNames,
      date_of_birth: form.dateOfBirth,
      sex: 'Non précisé',
      place_of_birth: form.placeOfBirth,
      arrival_in_canada: form.arrivalInCanada || null,
      residency_status: '',
      marital_status: form.maritalStatus || 'autre',
      dependents_count: numberValue(form.dependents),
    },
    contact: {
      phone: form.phone,
      email: form.email,
      address: parsedAddress.address,
      city: parsedAddress.city,
      province: parsedAddress.province,
      postal_code: form.postalCode,
    },
    employment: {
      occupation: form.occupation,
      employer_name: '',
      employer_address: form.employerAddress,
      annual_income: numberValue(form.annualIncome),
      monthly_net_income: 0,
    },
    financial: {
      total_assets: numberValue(form.totalAssets),
      cash_savings: 0,
      personal_property: numberValue(form.totalAssets),
      total_debts: numberValue(form.totalDebts),
      credit_cards: 0,
      car_loan: 0,
      student_loan: 0,
      personal_loan: 0,
      mortgage: 0,
      monthly_expenses: 0,
      monthly_debt_repayment: 0,
      monthly_savings: 0,
    },
    insurance: {
      has_existing_life_insurance: hasInsurance,
      existing_life_coverage: 0,
      existing_monthly_premium: 0,
      existing_retirement_savings_note: form.existingInsuranceDetails,
      no_insurance_reason: form.noInsuranceReason,
    },
    goals: {
      short_term_goals: form.priorityProjects,
      long_term_goals: form.priorityProjects,
      family_need_if_death: form.priorityProjects,
      priority_projects: form.priorityProjects,
      acceptable_monthly_budget: numberValue(form.acceptableBudget),
      client_preference: form.acceptableBudget,
    },
    health: {
      height: form.height,
      weight: form.weight,
      smoker: null,
      health_notes: '',
    },
    meeting: {
      availability: form.availability,
      preferred_mode: '',
      consent_acknowledged: true,
    },
  };
}

function App() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const completed = useMemo(
    () => Boolean(form.legalLastName && form.firstNames && form.dateOfBirth && form.phone && form.email),
    [form],
  );

  async function saveProspect() {
    setLoading(true);
    setMessage('');
    try {
      await api('/api/prospects?advisor_slug=finab', {
        method: 'POST',
        body: JSON.stringify(payloadFromForm(form)),
      });
      setSubmitted(true);
      setMessage('Merci. Vos informations ont bien été envoyées. Votre conseiller vous contactera pour la suite.');
      setForm(initialForm);
    } catch (e) {
      setMessage("Une erreur est survenue pendant l'envoi. Veuillez réessayer ou contacter votre conseiller.");
    } finally {
      setLoading(false);
    }
  }

  const set = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });

  return (
    <main className="public-page">
      <section className="public-hero">
        <div className="brand-line"><div className="mark">F</div><span>FINAB Solution</span></div>
        <h1>COLLECTE D'INFORMATION POUR ABF</h1>
        <p>
          Veuillez remplir ce formulaire avec des informations exactes. Ces renseignements permettront à votre conseiller de préparer votre analyse de besoins financiers.
        </p>
        <div className="privacy-note"><ShieldCheck size={18}/> Vos informations sont transmises à votre conseiller de façon confidentielle.</div>
      </section>

      {message && <div className={submitted ? 'notice success' : 'notice'}>{submitted && <CheckCircle2 size={20}/>} {message}</div>}

      <section className="form-card">
        <div className="form-section">
          <h2>Informations personnelles</h2>
          <div className="form-grid">
            <label>Nom<input value={form.legalLastName} onChange={set('legalLastName')} autoComplete="family-name" /></label>
            <label>Prénoms<input value={form.firstNames} onChange={set('firstNames')} autoComplete="given-name" /></label>
            <label>Date de naissance<input type="date" value={form.dateOfBirth} onChange={set('dateOfBirth')} /></label>
            <label>Lieu de naissance<input value={form.placeOfBirth} onChange={set('placeOfBirth')} /></label>
            <label>Statut au Canada / état civil : marié, célibataire, monoparental avec enfants, conjoint de fait
              <select value={form.maritalStatus} onChange={set('maritalStatus')}>
                <option value="">Sélectionner</option>
                <option value="marié">Marié</option>
                <option value="célibataire">Célibataire</option>
                <option value="monoparental">Monoparental avec enfants</option>
                <option value="conjoint de fait">Conjoint de fait</option>
                <option value="autre">Autre</option>
              </select>
            </label>
            <label>Nombre d'enfants<input value={form.dependents} onChange={set('dependents')} inputMode="numeric" /></label>
            <label>Date d'arrivée au Canada<input type="date" value={form.arrivalInCanada} onChange={set('arrivalInCanada')} /></label>
          </div>
        </div>

        <div className="form-section">
          <h2>Coordonnées</h2>
          <div className="form-grid">
            <label>Téléphone<input value={form.phone} onChange={set('phone')} autoComplete="tel" /></label>
            <label>Courriel<input value={form.email} onChange={set('email')} autoComplete="email" /></label>
            <label className="span-2">Adresse domicile : rue, appartement, ville<input value={form.address} onChange={set('address')} autoComplete="street-address" /></label>
            <label>Code postal<input value={form.postalCode} onChange={set('postalCode')} autoComplete="postal-code" /></label>
          </div>
        </div>

        <div className="form-section">
          <h2>Emploi et revenu</h2>
          <div className="form-grid">
            <label className="span-2">Emploi actuel, titre et poste<input value={form.occupation} onChange={set('occupation')} /></label>
            <label className="span-2">Adresse emploi actuel<input value={form.employerAddress} onChange={set('employerAddress')} /></label>
            <label>Revenu annuel<input value={form.annualIncome} onChange={set('annualIncome')} inputMode="decimal" /></label>
          </div>
        </div>

        <div className="form-section">
          <h2>Situation financière</h2>
          <div className="form-grid">
            <label>Total des biens<input value={form.totalAssets} onChange={set('totalAssets')} inputMode="decimal" /></label>
            <label>Total des dettes<input value={form.totalDebts} onChange={set('totalDebts')} inputMode="decimal" /></label>
          </div>
        </div>

        <div className="form-section">
          <h2>Assurance et budget</h2>
          <div className="form-grid">
            <label>Assurance vie individuelle existante : oui/non
              <select value={form.hasExistingInsurance} onChange={set('hasExistingInsurance')}>
                <option value="">Sélectionner</option>
                <option value="oui">Oui</option>
                <option value="non">Non</option>
              </select>
            </label>
            <label className="span-2">Si oui : capital assuré + cotisations assurance / REER / CELI / REEE<textarea value={form.existingInsuranceDetails} onChange={set('existingInsuranceDetails')} /></label>
            <label className="span-2">Si non : raison<textarea value={form.noInsuranceReason} onChange={set('noInsuranceReason')} /></label>
            <label className="span-2">Budget possible pour assurance + retraite + maladies graves + hypothèque<input value={form.acceptableBudget} onChange={set('acceptableBudget')} inputMode="decimal" /></label>
          </div>
        </div>

        <div className="form-section">
          <h2>Santé et disponibilité</h2>
          <div className="form-grid">
            <label>Taille<input value={form.height} onChange={set('height')} /></label>
            <label>Poids<input value={form.weight} onChange={set('weight')} /></label>
            <label className="span-2">Disponibilité pour rencontre<textarea value={form.availability} onChange={set('availability')} /></label>
            <label className="span-2">Projets prioritaires et besoin d'aide<textarea value={form.priorityProjects} onChange={set('priorityProjects')} /></label>
          </div>
        </div>

        <button className="submit-button" disabled={!completed || loading} onClick={saveProspect}>
          {loading ? <Loader2 className="spin"/> : null} Envoyer mes informations
        </button>
        <p className="required-note">Champs minimum requis : nom, prénoms, date de naissance, téléphone et courriel.</p>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
