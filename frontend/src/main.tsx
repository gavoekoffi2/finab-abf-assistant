import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, Download, FileText, Loader2, ShieldCheck, Users, Wand2 } from 'lucide-react';
import './styles.css';

type ProspectSummary = {
  id: string;
  client_name: string;
  phone: string;
  email: string;
  status: string;
  created_at: string;
};

type FormState = {
  legalLastName: string;
  firstNames: string;
  dateOfBirth: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  province: string;
  postalCode: string;
  occupation: string;
  employerName: string;
  annualIncome: string;
  monthlyNetIncome: string;
  totalAssets: string;
  totalDebts: string;
  monthlyExpenses: string;
  acceptableBudget: string;
  dependents: string;
  maritalStatus: string;
  residencyStatus: string;
  placeOfBirth: string;
  priorityProjects: string;
  familyNeed: string;
};

const initialForm: FormState = {
  legalLastName: '',
  firstNames: '',
  dateOfBirth: '',
  phone: '',
  email: '',
  address: '',
  city: '',
  province: 'QC',
  postalCode: '',
  occupation: '',
  employerName: '',
  annualIncome: '',
  monthlyNetIncome: '',
  totalAssets: '',
  totalDebts: '',
  monthlyExpenses: '',
  acceptableBudget: '',
  dependents: '0',
  maritalStatus: 'célibataire',
  residencyStatus: '',
  placeOfBirth: '',
  priorityProjects: '',
  familyNeed: '',
};

const api = async <T,>(url: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

function payloadFromForm(form: FormState) {
  const n = (value: string) => Number(value || 0);
  return {
    identity: {
      legal_last_name: form.legalLastName,
      first_names: form.firstNames,
      date_of_birth: form.dateOfBirth,
      sex: 'Femme',
      place_of_birth: form.placeOfBirth,
      arrival_in_canada: '2022-01-01',
      residency_status: form.residencyStatus,
      marital_status: form.maritalStatus,
      dependents_count: n(form.dependents),
    },
    contact: {
      phone: form.phone,
      email: form.email,
      address: form.address,
      city: form.city,
      province: form.province,
      postal_code: form.postalCode,
    },
    employment: {
      occupation: form.occupation,
      employer_name: form.employerName,
      employer_address: '',
      annual_income: n(form.annualIncome),
      monthly_net_income: n(form.monthlyNetIncome),
    },
    financial: {
      total_assets: n(form.totalAssets),
      cash_savings: 0,
      personal_property: n(form.totalAssets),
      total_debts: n(form.totalDebts),
      credit_cards: 0,
      car_loan: 0,
      student_loan: 0,
      personal_loan: 0,
      mortgage: 0,
      monthly_expenses: n(form.monthlyExpenses),
      monthly_debt_repayment: 100,
      monthly_savings: 0,
    },
    insurance: {
      has_existing_life_insurance: false,
      existing_life_coverage: 0,
      existing_monthly_premium: 0,
      no_insurance_reason: 'À confirmer avec le conseiller',
    },
    goals: {
      short_term_goals: 'Achat de maison',
      long_term_goals: 'Investir au pays',
      family_need_if_death: form.familyNeed,
      priority_projects: form.priorityProjects,
      acceptable_monthly_budget: n(form.acceptableBudget),
      client_preference: 'Commencer avec un budget réaliste',
    },
    health: { height: '', weight: '', smoker: false, health_notes: '' },
    meeting: { availability: 'À confirmer', preferred_mode: 'Zoom', consent_acknowledged: true },
  };
}

function App() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [prospects, setProspects] = useState<ProspectSummary[]>([]);
  const [selected, setSelected] = useState<ProspectSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [pdfUrl, setPdfUrl] = useState('');

  const completed = useMemo(() => Boolean(form.legalLastName && form.firstNames && form.dateOfBirth && form.phone), [form]);

  async function refresh() {
    const rows = await api<ProspectSummary[]>('/api/prospects');
    setProspects(rows);
    if (!selected && rows.length) setSelected(rows[0]);
  }

  useEffect(() => { refresh().catch(() => undefined); }, []);

  async function saveProspect() {
    setLoading(true); setMessage(''); setPdfUrl('');
    try {
      const created = await api<ProspectSummary>('/api/prospects?advisor_slug=finab', {
        method: 'POST',
        body: JSON.stringify(payloadFromForm(form)),
      });
      await refresh();
      setSelected(created);
      setMessage(`Prospect sauvegardé : ${created.client_name}`);
    } catch (e) {
      setMessage(`Erreur sauvegarde : ${String(e).slice(0, 180)}`);
    } finally { setLoading(false); }
  }

  async function generateAbf() {
    if (!selected) return;
    setLoading(true); setMessage(''); setPdfUrl('');
    try {
      const result = await api<{ output_path: string; pages_after: number; filled_widget_updates: number; layout_preserved: boolean }>(`/api/prospects/${selected.id}/generate-abf`, { method: 'POST', body: '{}' });
      setPdfUrl(`/abf/download?path=${encodeURIComponent(result.output_path)}`);
      setMessage(`ABF généré : ${result.pages_after} pages, ${result.filled_widget_updates} champs, mise en page préservée=${result.layout_preserved}`);
      await refresh();
    } catch (e) {
      setMessage(`Erreur génération ABF : ${String(e).slice(0, 180)}`);
    } finally { setLoading(false); }
  }

  const set = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });

  return (
    <main className="page">
      <aside className="sidebar">
        <div className="brand"><div className="mark">F</div><div><strong>FINAB</strong><span>ABF Assistant</span></div></div>
        <nav>
          <a className="active"><Users size={18}/> Prospects</a>
          <a><FileText size={18}/> Dossiers ABF</a>
          <a><Wand2 size={18}/> Brouillon IA</a>
          <a><ShieldCheck size={18}/> Révision conseiller</a>
        </nav>
      </aside>
      <section className="content">
        <header className="hero">
          <div>
            <p className="eyebrow">FINAB / Greatway — MVP</p>
            <h1>Formulaire prospect → ABF officiel prérempli</h1>
            <p>L’utilisateur remplit le formulaire. Le conseiller révise. Le système génère une copie du vrai PDF ABF sans casser la mise en page.</p>
          </div>
          <div className="status"><CheckCircle2/> Mise en page protégée<br/><span>16 pages, AcroForm, couleurs originales</span></div>
        </header>

        {message && <div className="notice">{message}{pdfUrl && <a href={pdfUrl} target="_blank">Télécharger le PDF ABF</a>}</div>}

        <div className="grid">
          <section className="card wide">
            <div className="section-title"><span>01</span><h2>Formulaire prospect public</h2></div>
            <div className="form-grid">
              <label>Nom légal<input value={form.legalLastName} onChange={set('legalLastName')} /></label>
              <label>Prénoms<input value={form.firstNames} onChange={set('firstNames')} /></label>
              <label>Date naissance<input type="date" value={form.dateOfBirth} onChange={set('dateOfBirth')} /></label>
              <label>Téléphone<input value={form.phone} onChange={set('phone')} /></label>
              <label>Courriel<input value={form.email} onChange={set('email')} /></label>
              <label>Adresse<input value={form.address} onChange={set('address')} /></label>
              <label>Ville<input value={form.city} onChange={set('city')} /></label>
              <label>Province<input value={form.province} onChange={set('province')} /></label>
              <label>Code postal<input value={form.postalCode} onChange={set('postalCode')} /></label>
              <label>Lieu naissance<input value={form.placeOfBirth} onChange={set('placeOfBirth')} /></label>
              <label>Statut résidence<input value={form.residencyStatus} onChange={set('residencyStatus')} /></label>
              <label>État civil<select value={form.maritalStatus} onChange={set('maritalStatus')}><option>célibataire</option><option>marié</option><option>conjoint de fait</option><option>monoparental</option><option>autre</option></select></label>
              <label>Nombre enfants<input value={form.dependents} onChange={set('dependents')} /></label>
              <label>Profession<input value={form.occupation} onChange={set('occupation')} /></label>
              <label>Revenu annuel<input value={form.annualIncome} onChange={set('annualIncome')} /></label>
              <label>Revenu net mensuel<input value={form.monthlyNetIncome} onChange={set('monthlyNetIncome')} /></label>
              <label>Total biens<input value={form.totalAssets} onChange={set('totalAssets')} /></label>
              <label>Total dettes<input value={form.totalDebts} onChange={set('totalDebts')} /></label>
              <label>Dépenses mensuelles<input value={form.monthlyExpenses} onChange={set('monthlyExpenses')} /></label>
              <label>Budget mensuel<input value={form.acceptableBudget} onChange={set('acceptableBudget')} /></label>
            </div>
            <label>Projets prioritaires<textarea value={form.priorityProjects} onChange={set('priorityProjects')} /></label>
            <label>Besoin famille si décès<textarea value={form.familyNeed} onChange={set('familyNeed')} /></label>
            <button disabled={!completed || loading} onClick={saveProspect}>{loading ? <Loader2 className="spin"/> : null} Sauvegarder le prospect</button>
          </section>

          <section className="card">
            <div className="section-title"><span>02</span><h2>Prospects reçus</h2></div>
            <div className="list">
              {prospects.length === 0 && <p className="muted">Aucun prospect pour le moment.</p>}
              {prospects.map((p) => <button className={selected?.id === p.id ? 'row selected' : 'row'} key={p.id} onClick={() => setSelected(p)}><strong>{p.client_name}</strong><span>{p.phone || p.email} · {p.status}</span></button>)}
            </div>
          </section>

          <section className="card">
            <div className="section-title"><span>03</span><h2>Révision conseiller</h2></div>
            <p className="warning">Le PDF final doit être généré après révision du conseiller. Pour le MVP, le bouton génère un brouillon contrôlé à partir du prospect sélectionné.</p>
            <button className="secondary" disabled={!selected || loading} onClick={generateAbf}>{loading ? <Loader2 className="spin"/> : <Download size={18}/>} Générer ABF officiel</button>
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
