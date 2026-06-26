import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, Download, FileText, Loader2, RefreshCw, ShieldCheck, Users } from 'lucide-react';
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

type ProspectSummary = {
  id: string;
  client_name: string;
  phone: string;
  email: string;
  status: string;
  created_at: string;
  updated_at?: string;
};

type ProspectDetail = ProspectSummary & {
  payload: any;
  documents?: Array<{ id?: string; output_path?: string; created_at?: string; result?: any }>;
};

const emptyForm: FormState = {
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

const demoForm: FormState = {
  legalLastName: 'KOUASSI TEST',
  firstNames: 'Amina',
  dateOfBirth: '1988-04-12',
  placeOfBirth: 'Lomé, Togo',
  maritalStatus: 'marié',
  dependents: '2',
  arrivalInCanada: '2021-09-15',
  phone: '5145550198',
  email: 'amina.test@example.com',
  address: '245 Rue Saint-Denis, Montréal',
  postalCode: 'H2X 3K8',
  occupation: "Je suis PAB à l'hôpital CIUSSS du Nord de Montréal",
  employerAddress: '1200 Boulevard René-Lévesque, Montréal, H3B 4W8',
  annualIncome: '48 000$',
  totalAssets: '18 000$',
  totalDebts: '9 500$',
  hasExistingInsurance: 'non',
  existingInsuranceDetails: '',
  noInsuranceReason: "Je n'ai jamais pris le temps de comparer les options.",
  acceptableBudget: '150$ par mois',
  height: '1m68',
  weight: '72 kg',
  availability: 'Soirs après 18h ou samedi matin via Zoom',
  priorityProjects: "Protection familiale, épargne pour les enfants, maladies graves et préparation achat maison.",
};

const api = async <T,>(url: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

const numberValue = (value: string) => Number(String(value || '').replace(/[^0-9.,]/g, '').replace(',', '.')) || 0;
const parseAddress = (value: string) => {
  const parts = value.split(',').map((part) => part.trim()).filter(Boolean);
  return { address: parts[0] || value, city: parts[1] || '', province: parts[2] || 'QC' };
};
const safe = (value: any) => value === null || value === undefined || value === '' ? '—' : String(value);
const money = (value: any) => Number(value || 0).toLocaleString('fr-CA', { maximumFractionDigits: 0 });

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
    health: { height: form.height, weight: form.weight, smoker: null, health_notes: '' },
    meeting: { availability: form.availability, preferred_mode: '', consent_acknowledged: true },
  };
}

function PublicForm() {
  const isDemo = new URLSearchParams(window.location.search).get('demo') === '1';
  const [form, setForm] = useState<FormState>(isDemo ? demoForm : emptyForm);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const completed = useMemo(() => Boolean(form.legalLastName && form.firstNames && form.dateOfBirth && form.phone && form.email), [form]);

  async function saveProspect() {
    setLoading(true);
    setMessage('');
    try {
      await api('/api/prospects?advisor_slug=finab', { method: 'POST', body: JSON.stringify(payloadFromForm(form)) });
      setSubmitted(true);
      setMessage('Merci. Vos informations ont bien été envoyées. Votre conseiller vous contactera pour la suite.');
      setForm(isDemo ? demoForm : emptyForm);
    } catch {
      setMessage("Une erreur est survenue pendant l'envoi. Veuillez réessayer ou contacter votre conseiller.");
    } finally { setLoading(false); }
  }

  const set = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });

  return (
    <main className="public-page">
      <section className="public-hero">
        <div className="brand-line"><div className="mark">F</div><span>FINAB Solution</span></div>
        <h1>COLLECTE D'INFORMATION POUR ABF</h1>
        <p>Veuillez remplir ce formulaire avec des informations exactes. Ces renseignements permettront à votre conseiller de préparer votre analyse de besoins financiers.</p>
        <div className="privacy-note"><ShieldCheck size={18}/> Vos informations sont transmises à votre conseiller de façon confidentielle.</div>
      </section>
      {message && <div className={submitted ? 'notice success' : 'notice'}>{submitted && <CheckCircle2 size={20}/>} {message}</div>}
      <section className="form-card">
        <div className="form-section"><h2>Informations personnelles</h2><div className="form-grid">
          <label>NOM<input value={form.legalLastName} onChange={set('legalLastName')} autoComplete="family-name" /></label>
          <label>PRÉNOMS<input value={form.firstNames} onChange={set('firstNames')} autoComplete="given-name" /></label>
          <label>Date de naissance<input type="date" value={form.dateOfBirth} onChange={set('dateOfBirth')} /></label>
          <label>Lieu de Naissance<input value={form.placeOfBirth} onChange={set('placeOfBirth')} /></label>
          <label>VOTRE STATUT AU CANADA ( Marié, Célibataire, Monoparental avec Enfants, Conjoint de fait )<select value={form.maritalStatus} onChange={set('maritalStatus')}><option value="">Sélectionner</option><option value="marié">Marié</option><option value="célibataire">Célibataire</option><option value="monoparental">Monoparental avec Enfants</option><option value="conjoint de fait">Conjoint de fait</option><option value="autre">Autre</option></select></label>
          <label>Si vous Marié, Monoparental ou Conjoint de fait, combien d'enfants avez vous?<input value={form.dependents} onChange={set('dependents')} inputMode="numeric" /></label>
          <label>Date d'arrivée au Canada<input type="date" value={form.arrivalInCanada} onChange={set('arrivalInCanada')} /></label>
        </div></div>
        <div className="form-section"><h2>Coordonnées</h2><div className="form-grid">
          <label>TÉLÉPHONE<input value={form.phone} onChange={set('phone')} autoComplete="tel" /></label>
          <label>COURRIEL<input value={form.email} onChange={set('email')} autoComplete="email" /></label>
          <label className="span-2">ADRESSE DE DOMICILE (Rue, App, Ville)<input value={form.address} onChange={set('address')} autoComplete="street-address" /></label>
          <label>CODE POSTALE<input value={form.postalCode} onChange={set('postalCode')} autoComplete="postal-code" /></label>
        </div></div>
        <div className="form-section"><h2>Emploi et revenu</h2><div className="form-grid">
          <label className="span-2">EMPLOI ACTUEL, TITRE ET POSTE ( EX: Je suis PAB à l'hopital CISSSS nord de Montreal )<input value={form.occupation} onChange={set('occupation')} /></label>
          <label className="span-2">ADRESSE DE VOTRE EMPLOI ACTUEL (Rue, Ville et Code Postal)<input value={form.employerAddress} onChange={set('employerAddress')} /></label>
          <label className="span-2">VOTRE REVENU ANNUEL (ex: 40 000$ ou 25$/ l'heure ) pendant 40h par semaine<input value={form.annualIncome} onChange={set('annualIncome')} inputMode="decimal" /></label>
        </div></div>
        <div className="form-section"><h2>Situation financière</h2><div className="form-grid">
          <label className="span-2">TOTAL DE VOS BIENS ( y compris auto, habits et tout ce que vous avez à la maison )<input value={form.totalAssets} onChange={set('totalAssets')} inputMode="decimal" /></label>
          <label className="span-2">TOTAL DE VOS DETTES ( carte et marge de crédit, auto, etc )<input value={form.totalDebts} onChange={set('totalDebts')} inputMode="decimal" /></label>
        </div></div>
        <div className="form-section"><h2>Assurance et budget</h2><div className="form-grid">
          <label>Possédez vous déjà une assurance vie individuelle?<select value={form.hasExistingInsurance} onChange={set('hasExistingInsurance')}><option value="">Sélectionner</option><option value="oui">OUI</option><option value="non">NON</option></select></label>
          <label className="span-2">Si oui quel est le montant du capital assuré et combien vous cotisez pour le tout à savoir prime d'assurance+ les investissements (REER+ CELI+ REEE) ( ex: j'ai temporaire de 500 000 avec IA et je paie 50$ / mois + paie REER100$ +CELI 50$ et REEE pour 4 enfants je paie 200$ )<textarea value={form.existingInsuranceDetails} onChange={set('existingInsuranceDetails')} /></label>
          <label className="span-2">Si Non et pourquoi?<textarea value={form.noInsuranceReason} onChange={set('noInsuranceReason')} /></label>
          <label className="span-2">Si vous deviez avoir une assurance combinée avec votre cotisation pour votre retraire (REER et CELI), votre 25 maladies graves, votre hypothèque, combien seriez vous capable de payer actuellement ?<input value={form.acceptableBudget} onChange={set('acceptableBudget')} inputMode="decimal" /></label>
        </div></div>
        <div className="form-section"><h2>Santé et disponibilité</h2><div className="form-grid">
          <label>Quelle est votre taille ?<input value={form.height} onChange={set('height')} /></label>
          <label>Quel est votre poids ?<input value={form.weight} onChange={set('weight')} /></label>
          <label className="span-2">Quel jour seriez vous disponible pour une rencontre afin de vous expliquer votre situation? ( veuillez préciser l'heure, soit physiquement chez vous à la maison, dans mon bureau, soit via zoom ) ?<textarea value={form.availability} onChange={set('availability')} /></label>
          <label className="span-2">Quels sont vos projets les plus prioritaires actuellement et comment pourrais-je vous être utile ?<textarea value={form.priorityProjects} onChange={set('priorityProjects')} /></label>
        </div></div>
        <button className="submit-button" disabled={!completed || loading} onClick={saveProspect}>{loading ? <Loader2 className="spin"/> : null} Envoyer mes informations</button>
        <p className="required-note">Champs minimum requis : nom, prénoms, date de naissance, téléphone et courriel.</p>
      </section>
    </main>
  );
}

function AdvisorDashboard() {
  const [prospects, setProspects] = useState<ProspectSummary[]>([]);
  const [selected, setSelected] = useState<ProspectDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [pdfUrl, setPdfUrl] = useState('');

  async function refresh(selectId?: string) {
    const rows = await api<ProspectSummary[]>('/api/prospects?advisor_slug=finab');
    setProspects(rows);
    const id = selectId || selected?.id || rows[0]?.id;
    if (id) await loadDetail(id);
  }
  async function loadDetail(id: string) {
    setLoading(true);
    setMessage('');
    setPdfUrl('');
    try {
      const detail = await api<ProspectDetail>(`/api/prospects/${id}`);
      setSelected(detail);
    } catch {
      setMessage('Impossible de charger ce prospect.');
    } finally { setLoading(false); }
  }
  async function generateAbf() {
    if (!selected) return;
    setLoading(true);
    setMessage('');
    setPdfUrl('');
    try {
      const result = await api<{ output_path: string; pages_after: number; filled_widget_updates: number; layout_preserved: boolean }>(`/api/prospects/${selected.id}/generate-abf`, { method: 'POST', body: '{}' });
      setPdfUrl(`/abf/download?path=${encodeURIComponent(result.output_path)}`);
      setMessage(`ABF généré : ${result.pages_after} pages, ${result.filled_widget_updates} champs remplis.`);
      await refresh(selected.id);
    } catch {
      setMessage("Impossible de générer l'ABF pour ce prospect.");
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh().catch(() => setMessage('Impossible de charger les prospects.')); }, []);

  const p = selected?.payload;
  return (
    <main className="advisor-page">
      <aside className="advisor-sidebar">
        <div className="brand-line"><div className="mark">F</div><span>FINAB Conseiller</span></div>
        <button className="refresh-button" onClick={() => refresh()}><RefreshCw size={16}/> Actualiser</button>
        <div className="prospect-count"><Users size={18}/> {prospects.length} prospect(s)</div>
        <div className="advisor-list">
          {prospects.length === 0 && <p className="muted">Aucun prospect reçu pour le moment.</p>}
          {prospects.map((item) => <button key={item.id} className={selected?.id === item.id ? 'advisor-row selected' : 'advisor-row'} onClick={() => loadDetail(item.id)}><strong>{item.client_name}</strong><span>{item.phone || item.email || 'Sans contact'} · {item.status}</span></button>)}
        </div>
      </aside>
      <section className="advisor-content">
        <header className="advisor-header">
          <div><p className="eyebrow">Espace conseiller</p><h1>Prospects reçus et génération ABF</h1><p>Les informations envoyées par le formulaire prospect apparaissent ici. Sélectionne un prospect puis clique sur “Générer ABF”.</p></div>
          <a className="public-link" href="/" target="_blank">Voir formulaire public</a>
        </header>
        {message && <div className="notice success"><CheckCircle2 size={20}/> {message}{pdfUrl && <a href={pdfUrl} target="_blank" rel="noreferrer">Télécharger le PDF ABF</a>}</div>}
        {!selected && <section className="advisor-card"><p className="muted">Aucun prospect sélectionné.</p></section>}
        {selected && p && <>
          <section className="advisor-card client-main">
            <div><h2>{selected.client_name}</h2><p>{safe(selected.phone)} · {safe(selected.email)}</p><p className="muted">Reçu le {new Date(selected.created_at).toLocaleString('fr-CA')}</p></div>
            <button className="submit-button" disabled={loading} onClick={generateAbf}>{loading ? <Loader2 className="spin"/> : <Download size={18}/>} Générer ABF</button>
          </section>
          <div className="advisor-grid">
            <InfoCard title="Identité" rows={[
              ['Nom', p.identity?.legal_last_name], ['Prénoms', p.identity?.first_names], ['Date naissance', p.identity?.date_of_birth], ['Lieu naissance', p.identity?.place_of_birth], ['Statut', p.identity?.marital_status], ['Enfants', p.identity?.dependents_count], ['Arrivée Canada', p.identity?.arrival_in_canada]
            ]}/>
            <InfoCard title="Coordonnées" rows={[
              ['Téléphone', p.contact?.phone], ['Courriel', p.contact?.email], ['Adresse', [p.contact?.address, p.contact?.city, p.contact?.province, p.contact?.postal_code].filter(Boolean).join(', ')]
            ]}/>
            <InfoCard title="Emploi / revenus" rows={[
              ['Poste', p.employment?.occupation], ['Adresse emploi', p.employment?.employer_address], ['Revenu annuel', `$${money(p.employment?.annual_income)}`]
            ]}/>
            <InfoCard title="Finances" rows={[
              ['Total biens', `$${money(p.financial?.total_assets)}`], ['Total dettes', `$${money(p.financial?.total_debts)}`]
            ]}/>
            <InfoCard title="Assurance / budget" rows={[
              ['Assurance existante', p.insurance?.has_existing_life_insurance ? 'Oui' : 'Non'], ['Détails assurance / placements', p.insurance?.existing_retirement_savings_note], ['Si non : raison', p.insurance?.no_insurance_reason], ['Budget possible', `$${money(p.goals?.acceptable_monthly_budget)}`]
            ]}/>
            <InfoCard title="Santé / disponibilité / projets" rows={[
              ['Taille', p.health?.height], ['Poids', p.health?.weight], ['Disponibilité', p.meeting?.availability], ['Projets prioritaires', p.goals?.priority_projects]
            ]}/>
          </div>
          <section className="advisor-card">
            <h2>Documents ABF générés</h2>
            {(!selected.documents || selected.documents.length === 0) && <p className="muted">Aucun document généré pour ce prospect.</p>}
            {selected.documents?.map((doc, idx) => <a className="doc-row" key={idx} href={`/abf/download?path=${encodeURIComponent(doc.output_path || doc.result?.output_path || '')}`} target="_blank" rel="noreferrer"><FileText size={18}/> ABF généré {doc.created_at ? new Date(doc.created_at).toLocaleString('fr-CA') : ''}</a>)}
          </section>
        </>}
      </section>
    </main>
  );
}

function InfoCard({ title, rows }: { title: string; rows: Array<[string, any]> }) {
  return <section className="advisor-card"><h2>{title}</h2><dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{safe(value)}</dd></div>)}</dl></section>;
}

function App() {
  return window.location.pathname.startsWith('/conseiller') ? <AdvisorDashboard /> : <PublicForm />;
}

createRoot(document.getElementById('root')!).render(<App />);
