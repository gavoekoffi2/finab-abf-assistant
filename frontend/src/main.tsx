import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, CreditCard, Crown, Download, FileText, Loader2, LogOut, Pencil, RefreshCw, ShieldCheck, Sparkles, Trash2, UserPlus, Users, X } from 'lucide-react';
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

type SubscriptionState = { plan?: string; status?: string; effective_status?: string; access_label?: string; has_access?: boolean; in_trial?: boolean; trial_ends_at?: string | null; current_period_end?: string | null; price_usd?: number; trial_days?: number };
type Organization = { id?: string; name: string; slug: string; advisor_name: string; advisor_phone?: string; advisor_email?: string };
type User = { id: string; email: string; full_name: string; role: string; organization_id: string; organization: Organization; is_active?: boolean; subscription?: SubscriptionState };
type AuthSession = { token: string; expires_at: string; user: User };
type BillingConfig = { plan_name: string; price_usd: number; trial_days: number; subscription: SubscriptionState } & Record<string, unknown>;
type CheckoutStatus = { user: User; subscription: SubscriptionState; has_access: boolean };
type ProspectSummary = { id: string; organization_id?: string; advisor_slug?: string; client_name: string; phone: string; email: string; status: string; created_at: string; updated_at?: string };
type ReviewState = {
  reviewed_by_advisor: boolean;
  advisor_name: string;
  advisor_phone: string;
  advisor_email: string;
  signed_date: string;
  replacement_years: string;
  final_recommended_coverage: string;
  recommendation_1_budget: string;
  recommendation_2_budget: string;
  client_preference_budget: string;
  recommendation_1_notes: string;
  recommendation_2_notes: string;
  preference_notes: string;
  agent_notes: string;
};
type ProspectDetail = ProspectSummary & { payload: any; advisor_review?: any; documents?: Array<{ id?: string; output_path?: string; created_at?: string; report?: any }> };
type PdfField = { name: string; value: string; type: string; page: number; rect: [number, number, number, number]; multiline: boolean; max_length: number; options: string[] };
type AdminOverview = { organizations: number; users: number; active_users: number; admins?: number; unlimited_users?: number; prospects: number; documents: number; recent_prospects: ProspectSummary[]; plan_distribution?: Array<{ plan: string; subscription_status: string; c: number }> };
type AdminUser = User & { organization: Organization };

const AUTH_KEY = 'finab_abf_session';

const emptyForm: FormState = {
  legalLastName: '', firstNames: '', dateOfBirth: '', placeOfBirth: '', maritalStatus: '', dependents: '', arrivalInCanada: '', phone: '', email: '', address: '', postalCode: '', occupation: '', employerAddress: '', annualIncome: '', totalAssets: '', totalDebts: '', hasExistingInsurance: '', existingInsuranceDetails: '', noInsuranceReason: '', acceptableBudget: '', height: '', weight: '', availability: '', priorityProjects: '',
};
const todayIso = () => new Date().toISOString().slice(0, 10);
const emptyReview: ReviewState = {
  reviewed_by_advisor: true,
  advisor_name: '',
  advisor_phone: '',
  advisor_email: '',
  signed_date: todayIso(),
  replacement_years: '10',
  final_recommended_coverage: '',
  recommendation_1_budget: '',
  recommendation_2_budget: '',
  client_preference_budget: '',
  recommendation_1_notes: '',
  recommendation_2_notes: '',
  preference_notes: '',
  agent_notes: '',
};

const api = async <T,>(url: string, options?: RequestInit, token?: string): Promise<T> => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, { ...options, headers: { ...headers, ...(options?.headers || {}) } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

const storedSession = (): AuthSession | null => {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY) || 'null'); } catch { return null; }
};
const numberValue = (value: string) => Number(String(value || '').replace(/[^0-9.,]/g, '').replace(',', '.')) || 0;
const parseAddress = (value: string) => { const parts = value.split(',').map((part) => part.trim()).filter(Boolean); return { address: parts[0] || value, city: parts[1] || '', province: parts[2] || 'QC' }; };
const safe = (value: any) => value === null || value === undefined || value === '' ? '—' : String(value);
const money = (value: any) => Number(value || 0).toLocaleString('fr-CA', { maximumFractionDigits: 0 });
const advisorSlugFromPath = () => window.location.pathname.startsWith('/apply/') ? window.location.pathname.split('/')[2] || 'finab' : 'finab';
const statusLabel = (status: string) => ({ new: 'Reçu', abf_generated: 'ABF généré' } as Record<string, string>)[status] || 'En traitement';
const roleLabel = (role: string) => ({ owner: 'Super administrateur', admin: 'Directeur FINAB', advisor: 'Conseiller' } as Record<string, string>)[role] || 'Conseiller';
const planLabel = (plan?: string) => ({ free: 'Sans accès', finab_pro: 'Pro ABF', enterprise: 'Illimité' } as Record<string, string>)[plan || 'finab_pro'] || 'Pro ABF';
const accessLabel = (subscription?: SubscriptionState) => subscription?.access_label || (subscription?.has_access ? 'Accès actif' : 'Accès inactif');
const isoDaysFromNow = (days: number) => { const date = new Date(); date.setDate(date.getDate() + days); return date.toISOString(); };

function payloadFromForm(form: FormState) {
  const parsedAddress = parseAddress(form.address);
  const hasInsurance = form.hasExistingInsurance === 'oui';
  return {
    identity: { legal_last_name: form.legalLastName, first_names: form.firstNames, date_of_birth: form.dateOfBirth, sex: 'Non précisé', place_of_birth: form.placeOfBirth, arrival_in_canada: form.arrivalInCanada || null, residency_status: '', marital_status: form.maritalStatus || 'autre', dependents_count: numberValue(form.dependents) },
    contact: { phone: form.phone, email: form.email, address: parsedAddress.address, city: parsedAddress.city, province: parsedAddress.province, postal_code: form.postalCode },
    employment: { occupation: form.occupation, employer_name: '', employer_address: form.employerAddress, annual_income: numberValue(form.annualIncome), monthly_net_income: 0 },
    financial: { total_assets: numberValue(form.totalAssets), cash_savings: 0, personal_property: numberValue(form.totalAssets), total_debts: numberValue(form.totalDebts), credit_cards: 0, car_loan: 0, student_loan: 0, personal_loan: 0, mortgage: 0, monthly_expenses: 0, monthly_debt_repayment: 0, monthly_savings: 0 },
    insurance: { has_existing_life_insurance: hasInsurance, existing_life_coverage: 0, existing_monthly_premium: 0, existing_retirement_savings_note: form.existingInsuranceDetails, no_insurance_reason: form.noInsuranceReason },
    goals: { short_term_goals: form.priorityProjects, long_term_goals: form.priorityProjects, family_need_if_death: form.priorityProjects, priority_projects: form.priorityProjects, acceptable_monthly_budget: numberValue(form.acceptableBudget), client_preference: form.acceptableBudget },
    health: { height: form.height, weight: form.weight, smoker: null, health_notes: '' },
    meeting: { availability: form.availability, preferred_mode: '', consent_acknowledged: true },
  };
}


function formFromPayload(payload: any): FormState {
  const contact = payload?.contact || {};
  const address = [contact.address, contact.city, contact.province].filter(Boolean).join(', ');
  return {
    legalLastName: payload?.identity?.legal_last_name || '',
    firstNames: payload?.identity?.first_names || '',
    dateOfBirth: payload?.identity?.date_of_birth || '',
    placeOfBirth: payload?.identity?.place_of_birth || '',
    maritalStatus: payload?.identity?.marital_status || '',
    dependents: String(payload?.identity?.dependents_count ?? ''),
    arrivalInCanada: payload?.identity?.arrival_in_canada || '',
    phone: contact.phone || '',
    email: contact.email || '',
    address,
    postalCode: contact.postal_code || '',
    occupation: payload?.employment?.occupation || '',
    employerAddress: payload?.employment?.employer_address || '',
    annualIncome: String(payload?.employment?.annual_income || ''),
    totalAssets: String(payload?.financial?.total_assets || ''),
    totalDebts: String(payload?.financial?.total_debts || ''),
    hasExistingInsurance: payload?.insurance?.has_existing_life_insurance ? 'oui' : 'non',
    existingInsuranceDetails: payload?.insurance?.existing_retirement_savings_note || '',
    noInsuranceReason: payload?.insurance?.no_insurance_reason || '',
    acceptableBudget: String(payload?.goals?.acceptable_monthly_budget || ''),
    height: payload?.health?.height || '',
    weight: payload?.health?.weight || '',
    availability: payload?.meeting?.availability || '',
    priorityProjects: payload?.goals?.priority_projects || '',
  };
}

function reviewFromDetail(detail: ProspectDetail | null, session?: AuthSession | null): ReviewState {
  const review = detail?.advisor_review || {};
  const org = (session?.user.organization || {}) as Partial<Organization>;
  const budget = detail?.payload?.goals?.acceptable_monthly_budget || '';
  return {
    ...emptyReview,
    reviewed_by_advisor: review.reviewed_by_advisor ?? true,
    advisor_name: review.advisor_name || org.advisor_name || session?.user.full_name || '',
    advisor_phone: review.advisor_phone || org.advisor_phone || '',
    advisor_email: review.advisor_email || org.advisor_email || session?.user.email || '',
    signed_date: review.signed_date || todayIso(),
    replacement_years: String(review.replacement_years ?? 10),
    final_recommended_coverage: String(review.final_recommended_coverage || ''),
    recommendation_1_budget: String(review.recommendation_1_budget || budget || ''),
    recommendation_2_budget: String(review.recommendation_2_budget || (Number(budget) ? Number(budget) * 1.5 : '') || ''),
    client_preference_budget: String(review.client_preference_budget || budget || ''),
    recommendation_1_notes: review.recommendation_1_notes || '',
    recommendation_2_notes: review.recommendation_2_notes || '',
    preference_notes: review.preference_notes || '',
    agent_notes: review.agent_notes || '',
  };
}

function reviewPayload(form: ReviewState) {
  return {
    reviewed_by_advisor: true,
    advisor_name: form.advisor_name,
    advisor_phone: form.advisor_phone,
    advisor_email: form.advisor_email,
    signed_date: form.signed_date || todayIso(),
    replacement_years: numberValue(form.replacement_years),
    final_recommended_coverage: numberValue(form.final_recommended_coverage),
    recommendation_1_budget: numberValue(form.recommendation_1_budget),
    recommendation_2_budget: numberValue(form.recommendation_2_budget),
    client_preference_budget: numberValue(form.client_preference_budget),
    recommendation_1_notes: form.recommendation_1_notes,
    recommendation_2_notes: form.recommendation_2_notes,
    preference_notes: form.preference_notes,
    agent_notes: form.agent_notes,
  };
}

function PublicForm() {
  const advisorSlug = advisorSlugFromPath();
  const [organization, setOrganization] = useState<Organization>({ name: 'FINAB Solution', slug: advisorSlug, advisor_name: 'Votre conseiller' });
  const [form, setForm] = useState<FormState>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const completed = useMemo(() => Boolean(form.legalLastName && form.firstNames && form.dateOfBirth && form.phone && form.email), [form]);

  useEffect(() => { api<Organization>(`/api/organizations/${advisorSlug}/public`).then(setOrganization).catch(() => undefined); }, [advisorSlug]);

  async function saveProspect() {
    setLoading(true); setMessage('');
    try {
      await api(`/api/prospects?advisor_slug=${encodeURIComponent(advisorSlug)}`, { method: 'POST', body: JSON.stringify(payloadFromForm(form)) });
      setSubmitted(true);
      setMessage('Merci. Vos informations ont bien été envoyées. Votre conseiller vous contactera pour la suite.');
      setForm(emptyForm);
    } catch { setMessage("Une erreur est survenue pendant l'envoi. Veuillez réessayer ou contacter votre conseiller."); }
    finally { setLoading(false); }
  }

  const set = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });

  return (
    <main className="public-page">
      <section className="public-hero">
        <div className="brand-line"><div className="mark">F</div><span>{organization.name}</span></div>
        <h1>Analyse de besoins financiers</h1>
        <p>Complétez vos informations en quelques minutes. Votre conseiller pourra préparer une recommandation claire, structurée et adaptée à votre situation.</p>
        <div className="privacy-note"><ShieldCheck size={18}/> Transmission confidentielle à votre conseiller FINAB.</div>
      </section>
      {message && <div className={submitted ? 'notice success' : 'notice'}>{submitted && <CheckCircle2 size={20}/>} {message}</div>}
      <section className="form-card">
        <div className="form-section"><h2>Informations personnelles</h2><div className="form-grid">
          <label>Nom de famille<input value={form.legalLastName} onChange={set('legalLastName')} autoComplete="family-name" /></label>
          <label>Prénoms<input value={form.firstNames} onChange={set('firstNames')} autoComplete="given-name" /></label>
          <label>Date de naissance<input type="date" value={form.dateOfBirth} onChange={set('dateOfBirth')} /></label>
          <label>Lieu de naissance<input value={form.placeOfBirth} onChange={set('placeOfBirth')} /></label>
          <label>Situation familiale<select value={form.maritalStatus} onChange={set('maritalStatus')}><option value="">Sélectionner</option><option value="marié">Marié</option><option value="célibataire">Célibataire</option><option value="monoparental">Monoparental avec Enfants</option><option value="conjoint de fait">Conjoint de fait</option><option value="autre">Autre</option></select></label>
          <label>Nombre d’enfants à charge<input value={form.dependents} onChange={set('dependents')} inputMode="numeric" /></label>
          <label>Date d'arrivée au Canada<input type="date" value={form.arrivalInCanada} onChange={set('arrivalInCanada')} /></label>
        </div></div>
        <div className="form-section"><h2>Coordonnées</h2><div className="form-grid">
          <label>Téléphone<input value={form.phone} onChange={set('phone')} autoComplete="tel" /></label>
          <label>Courriel<input value={form.email} onChange={set('email')} autoComplete="email" /></label>
          <label className="span-2">Adresse de domicile<input value={form.address} onChange={set('address')} autoComplete="street-address" placeholder="Rue, appartement, ville" /></label>
          <label>Code postal<input value={form.postalCode} onChange={set('postalCode')} autoComplete="postal-code" /></label>
        </div></div>
        <div className="form-section"><h2>Emploi et revenu</h2><div className="form-grid">
          <label className="span-2">Emploi actuel, titre et poste<input value={form.occupation} onChange={set('occupation')} placeholder="Ex: Préposé aux bénéficiaires, infirmier, entrepreneur…" /></label>
          <label className="span-2">Adresse de votre emploi actuel<input value={form.employerAddress} onChange={set('employerAddress')} placeholder="Rue, ville et code postal" /></label>
          <label className="span-2">Revenu annuel estimé<input value={form.annualIncome} onChange={set('annualIncome')} inputMode="decimal" placeholder="Ex: 40 000 $" /></label>
        </div></div>
        <div className="form-section"><h2>Situation financière</h2><div className="form-grid">
          <label className="span-2">Valeur totale approximative de vos biens<input value={form.totalAssets} onChange={set('totalAssets')} inputMode="decimal" placeholder="Auto, épargne, biens personnels…" /></label>
          <label className="span-2">Total approximatif de vos dettes<input value={form.totalDebts} onChange={set('totalDebts')} inputMode="decimal" placeholder="Cartes, marges, auto, prêts…" /></label>
        </div></div>
        <div className="form-section"><h2>Assurance et budget</h2><div className="form-grid">
          <label>Possédez-vous déjà une assurance vie individuelle ?<select value={form.hasExistingInsurance} onChange={set('hasExistingInsurance')}><option value="">Sélectionner</option><option value="oui">Oui</option><option value="non">Non</option></select></label>
          <label className="span-2">Détails de vos protections et cotisations actuelles<textarea value={form.existingInsuranceDetails} onChange={set('existingInsuranceDetails')} placeholder="Capital assuré, prime mensuelle, REER, CELI, REEE…" /></label>
          <label className="span-2">Si vous n’avez pas d’assurance, quelle en est la raison ?<textarea value={form.noInsuranceReason} onChange={set('noInsuranceReason')} /></label>
          <label className="span-2">Budget mensuel confortable pour vos protections et votre épargne<input value={form.acceptableBudget} onChange={set('acceptableBudget')} inputMode="decimal" placeholder="Ex: 150 $ / mois" /></label>
        </div></div>
        <div className="form-section"><h2>Santé et disponibilité</h2><div className="form-grid">
          <label>Quelle est votre taille ?<input value={form.height} onChange={set('height')} /></label>
          <label>Quel est votre poids ?<input value={form.weight} onChange={set('weight')} /></label>
          <label className="span-2">Disponibilités pour une rencontre<textarea value={form.availability} onChange={set('availability')} placeholder="Jour, heure et préférence: bureau, domicile ou visioconférence" /></label>
          <label className="span-2">Quels sont vos projets les plus prioritaires actuellement et comment pourrais-je vous être utile ?<textarea value={form.priorityProjects} onChange={set('priorityProjects')} /></label>
        </div></div>
        <button className="submit-button" disabled={!completed || loading} onClick={saveProspect}>{loading ? <Loader2 className="spin"/> : null} Envoyer mes informations</button>
        <p className="required-note">Champs minimum requis : nom, prénoms, date de naissance, téléphone et courriel.</p>
      </section>
    </main>
  );
}

function LoginScreen({ onLogin, initialMode = 'login' }: { onLogin: (session: AuthSession) => void; initialMode?: 'login' | 'register' }) {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [advisorPhone, setAdvisorPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setMessage('');
    try {
      const body = mode === 'login'
        ? { email, password }
        : { email, password, full_name: fullName, organization_name: organizationName, advisor_phone: advisorPhone };
      const session = await api<AuthSession>(mode === 'login' ? '/api/auth/login' : '/api/auth/register', { method: 'POST', body: JSON.stringify(body) });
      localStorage.setItem(AUTH_KEY, JSON.stringify(session));
      onLogin(session);
    } catch { setMessage(mode === 'login' ? 'Connexion impossible. Vérifie le courriel et le mot de passe.' : 'Création impossible. Vérifie les informations ou utilise un autre courriel.'); }
    finally { setLoading(false); }
  }
  const canSubmit = mode === 'login' ? Boolean(email && password) : Boolean(email && password.length >= 8 && fullName);
  function switchMode(nextMode: 'login' | 'register') {
    setMode(nextMode);
    setMessage('');
  }
  return (
    <main className="login-page">
      <section className="auth-shell">
        <div className="auth-intro">
          <div className="brand-line"><div className="mark">F</div><span>FINAB Solution</span></div>
          <p className="eyebrow">Espace conseiller ABF</p>
          <h1>Votre espace conseiller FINAB, élégant et prêt à convertir.</h1>
          <p>Un environnement professionnel pour recevoir les demandes clients, suivre les dossiers et préparer rapidement les analyses ABF.</p>
          <div className="auth-benefits">
            <span>Essai gratuit de 3 jours avec carte</span>
            <span>Abonnement Pro à 199 $/mois</span>
            <span>Espace conseiller sécurisé</span>
          </div>
        </div>
      <form className="login-card flow-auth-card" onSubmit={submit}>
        <div className="brand-line mobile-auth-brand"><div className="mark">F</div><span>FINAB Solution</span></div>
        <div className="auth-tabs"><button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>Connexion</button><button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>Inscription</button></div>
        <h1>{mode === 'login' ? 'Accéder à mon espace conseiller' : 'Créer mon compte conseiller'}</h1>
        <p>{mode === 'login' ? 'Connectez-vous pour voir vos prospects, générer les PDF ABF et gérer les comptes autorisés.' : 'Créez votre accès professionnel. Votre espace conseiller sera préparé immédiatement.'}</p>
        {message && <div className="notice">{message}</div>}
        {mode === 'register' && <label>Nom complet<input value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" /></label>}
        {mode === 'register' && <label>Cabinet ou organisation<input value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} placeholder="Ex: Cabinet Montréal" /></label>}
        {mode === 'register' && <label>Téléphone conseiller<input value={advisorPhone} onChange={(e) => setAdvisorPhone(e.target.value)} autoComplete="tel" /></label>}
        <label>Courriel<input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
        <label>Mot de passe<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
        <button className="submit-button" disabled={loading || !canSubmit}>{loading ? <Loader2 className="spin"/> : null} {mode === 'login' ? 'Se connecter' : 'Créer mon compte'}</button>
        <button type="button" className="text-switch" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? "Nouveau conseiller ? Créer un compte" : 'J’ai déjà un compte conseiller'}</button>
      </form>
      </section>
    </main>
  );
}

function BillingScreen({ session, onRefresh, onLogout }: { session: AuthSession; onRefresh: (session: AuthSession) => void; onLogout: () => void }) {
  const [config, setConfig] = useState<BillingConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const configured = true;
  async function refreshAccount(sessionId?: string) {
    try {
      setMessage(sessionId ? 'Paiement confirmé. Ouverture de votre espace…' : '');
      const current = sessionId
        ? (await api<CheckoutStatus>(`/api/billing/checkout-status?session_id=${encodeURIComponent(sessionId)}`, undefined, session.token)).user
        : await api<User>('/api/me', undefined, session.token);
      const next = { ...session, user: current };
      localStorage.setItem(AUTH_KEY, JSON.stringify(next));
      if (current.subscription?.has_access) window.history.replaceState({}, '', '/conseiller');
      onRefresh(next);
    } catch { setMessage('Paiement reçu. Votre accès se prépare, cliquez sur rafraîchir dans quelques secondes.'); }
  }
  async function startCheckout() {
    setLoading(true); setMessage('');
    try {
      const result = await api<{ url: string; message?: string }>('/api/billing/checkout', { method: 'POST', body: '{}' }, session.token);
      window.location.href = result.url;
    } catch {
      setMessage("L’activation en ligne est momentanément indisponible. Merci de réessayer plus tard.");
    } finally { setLoading(false); }
  }
  useEffect(() => {
    api<BillingConfig>('/api/billing/config', undefined, session.token).then(setConfig).catch(() => setMessage('Activation momentanément indisponible.'));
    const params = new URLSearchParams(window.location.search);
    if (params.get('checkout') === 'success') refreshAccount(params.get('session_id') || undefined);
  }, []);
  return (
    <main className="billing-page">
      <section className="billing-shell">
        <div className="billing-hero">
          <div className="brand-line"><div className="mark">F</div><span>FINAB ABF Flow</span></div>
          <p className="eyebrow">Activation Pro</p>
          <h1>Activez votre espace conseiller Pro.</h1>
          <p>Profitez de 3 jours d’essai gratuit, puis conservez l’accès complet au logiciel professionnel FINAB ABF.</p>
          <div className="billing-badges"><span><ShieldCheck size={16}/> Carte requise</span><span><Sparkles size={16}/> 3 jours gratuits</span><span><Crown size={16}/> 199 $/mois</span></div>
        </div>
        <div className="pricing-card">
          <div className="pricing-top"><div><p className="eyebrow">Plan unique</p><h2>{config?.plan_name || 'FINAB ABF Flow Pro'}</h2></div><Crown size={30}/></div>
          <div className="price-line"><strong>199 $</strong><span>/ mois</span></div>
          <p className="trial-copy">Essai gratuit de 3 jours. Paiement sécurisé, accès complet au tableau de bord et aux documents ABF.</p>
          <ul>
            <li><CheckCircle2 size={18}/> Formulaire public conseiller personnalisé</li>
            <li><CheckCircle2 size={18}/> Suivi des prospects et dossiers clients</li>
            <li><CheckCircle2 size={18}/> Génération et téléchargement des PDF ABF</li>
            <li><CheckCircle2 size={18}/> Tableau de bord premium et espace sécurisé</li>
          </ul>
          {message && <div className="notice">{message}</div>}
          <button className="submit-button billing-cta" onClick={startCheckout} disabled={loading || !configured}>{loading ? <Loader2 className="spin"/> : <CreditCard size={19}/>} {configured ? 'Démarrer l’essai gratuit' : 'Activation bientôt disponible'}</button>
          <button className="text-switch" onClick={() => refreshAccount()}>J’ai déjà payé, rafraîchir mon accès</button>
          <button className="text-switch muted-switch" onClick={onLogout}>Changer de compte</button>
        </div>
      </section>
    </main>
  );
}

function AdvisorDashboard() {
  const [session, setSession] = useState<AuthSession | null>(storedSession());
  const [prospects, setProspects] = useState<ProspectSummary[]>([]);
  const [selected, setSelected] = useState<ProspectDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [pdfPath, setPdfPath] = useState('');
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<FormState>(emptyForm);
  const [reviewForm, setReviewForm] = useState<ReviewState>(emptyReview);
  const token = session?.token;

  async function refresh(selectId?: string) {
    if (!token) return;
    const rows = await api<ProspectSummary[]>('/api/prospects', undefined, token);
    setProspects(rows);
    const id = selectId || selected?.id || rows[0]?.id;
    if (id) await loadDetail(id);
    if (!id) setSelected(null);
  }
  async function loadDetail(id: string) {
    if (!token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      const detail = await api<ProspectDetail>(`/api/prospects/${id}`, undefined, token);
      setSelected(detail);
      setEditForm(formFromPayload(detail.payload));
      setReviewForm(reviewFromDetail(detail, session));
      setEditing(false);
    }
    catch { setMessage('Impossible de charger ce prospect.'); }
    finally { setLoading(false); }
  }
  async function generateAbf() {
    if (!selected || !token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      await api<ProspectDetail>(`/api/prospects/${selected.id}`, { method: 'PATCH', body: JSON.stringify(payloadFromForm(editForm)) }, token);
      await api<ProspectDetail>(`/api/prospects/${selected.id}/review`, { method: 'PATCH', body: JSON.stringify(reviewPayload(reviewForm)) }, token);
      const result = await api<{ output_path: string }>(`/api/prospects/${selected.id}/generate-abf`, { method: 'POST', body: JSON.stringify(reviewPayload(reviewForm)) }, token);
      await refresh(selected.id);
      setPdfPath(result.output_path);
      setMessage('ABF enregistré et PDF final généré. Vous pouvez maintenant corriger visuellement le PDF dans l’éditeur intégré, puis exporter la version modifiée.');
    } catch { setMessage("Impossible de générer l'ABF pour ce prospect. Vérifiez les champs ABF modifiables."); }
    finally { setLoading(false); }
  }

  async function updatePdfFields(path: string, fields: Record<string, string>) {
    if (!selected || !token || !path || Object.keys(fields).length === 0) return;
    setLoading(true); setMessage('');
    try {
      const result = await api<{ output_path: string }>(`/api/prospects/${selected.id}/pdf-fields`, { method: 'PATCH', body: JSON.stringify({ path, fields }) }, token);
      await refresh(selected.id);
      setPdfPath(result.output_path);
      setMessage('Champs du PDF mis à jour. Les modifications sont enregistrées et rechargées ci-dessous.');
    } catch { setMessage('Impossible d’enregistrer les modifications du PDF. Vérifiez les champs puis réessayez.'); }
    finally { setLoading(false); }
  }

  async function saveAbfPageEdits() {
    if (!selected || !token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      const updatedProspect = await api<ProspectDetail>(`/api/prospects/${selected.id}`, { method: 'PATCH', body: JSON.stringify(payloadFromForm(editForm)) }, token);
      const updatedReview = await api<ProspectDetail>(`/api/prospects/${selected.id}/review`, { method: 'PATCH', body: JSON.stringify(reviewPayload(reviewForm)) }, token);
      const merged = { ...updatedProspect, advisor_review: updatedReview.advisor_review, documents: updatedReview.documents || updatedProspect.documents };
      setSelected(merged);
      setEditForm(formFromPayload(merged.payload));
      setReviewForm(reviewFromDetail(merged, session));
      setEditing(false);
      setMessage('Corrections enregistrées. Le prochain PDF ABF reprendra exactement ces champs.');
      await refresh(merged.id);
    } catch { setMessage('Enregistrement impossible. Vérifiez les champs obligatoires.'); }
    finally { setLoading(false); }
  }

  async function saveAdvisorReview() {
    if (!selected || !token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      const updated = await api<ProspectDetail>(`/api/prospects/${selected.id}/review`, { method: 'PATCH', body: JSON.stringify(reviewPayload(reviewForm)) }, token);
      setSelected(updated);
      setReviewForm(reviewFromDetail(updated, session));
      setMessage('Préparation ABF enregistrée. Le prochain export utilisera ces corrections.');
      await refresh(updated.id);
    } catch { setMessage('Enregistrement de la préparation ABF impossible.'); }
    finally { setLoading(false); }
  }

  async function saveProspectEdits() {
    if (!selected || !token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      const updated = await api<ProspectDetail>(`/api/prospects/${selected.id}`, { method: 'PATCH', body: JSON.stringify(payloadFromForm(editForm)) }, token);
      setSelected(updated);
      setEditForm(formFromPayload(updated.payload));
      setEditing(false);
      setMessage('Corrections enregistrées. Le prochain PDF ABF utilisera ces informations.');
      await refresh(updated.id);
    } catch { setMessage('Enregistrement impossible. Vérifiez les champs obligatoires.'); }
    finally { setLoading(false); }
  }

  function startEditing() {
    if (!selected?.payload) return;
    setEditForm(formFromPayload(selected.payload));
    setEditing(true);
    setMessage('');
  }
  async function downloadPdf(path: string) {
    if (!token || !path) return;
    const res = await fetch(`/abf/download?path=${encodeURIComponent(path)}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) { setMessage('Téléchargement impossible.'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = path.split('/').pop() || 'ABF.pdf'; a.click();
    URL.revokeObjectURL(url);
  }
  function logout() { localStorage.removeItem(AUTH_KEY); setSession(null); setProspects([]); setSelected(null); }

  useEffect(() => {
    if (!token || (!session?.user.subscription?.has_access && !['owner', 'admin'].includes(session?.user.role || ''))) return;
    refresh().catch(() => { localStorage.removeItem(AUTH_KEY); setSession(null); });
  }, [token]);
  if (!session) return <LoginScreen onLogin={setSession} initialMode={window.location.pathname.startsWith('/inscription') ? 'register' : 'login'} />;
  const canAdminister = ['owner', 'admin'].includes(session.user.role);
  if (!canAdminister && !session.user.subscription?.has_access) return <BillingScreen session={session} onRefresh={setSession} onLogout={logout} />;

  const p = selected?.payload;
  const publicLink = `${window.location.origin}/apply/${session.user.organization.slug}`;
  const normalizedQuery = query.trim().toLowerCase();
  const filteredProspects = prospects.filter((item) => !normalizedQuery || `${item.client_name} ${item.phone} ${item.email} ${statusLabel(item.status)}`.toLowerCase().includes(normalizedQuery));
  const generatedCount = prospects.filter((item) => item.status === 'abf_generated').length;
  const pendingCount = Math.max(prospects.length - generatedCount, 0);
  const selectedStatus = selected ? statusLabel(selected.status) : 'Aucun dossier';
  const selectedInitials = (selected?.client_name || 'ABF').split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'ABF';
  const latestPdfPath = pdfPath || selected?.documents?.[0]?.output_path || '';
  const pdfPreviewUrl = pdfViewerUrl(latestPdfPath, token);
  return (
    <main className="advisor-page">
      <aside className="advisor-sidebar">
        <div className="sidebar-brand-card">
          <div className="brand-line"><div className="mark">F</div><span>{session.user.organization.name}</span></div>
          <p>Console ABF professionnelle</p>
        </div>
        <div className="advisor-user"><strong>{session.user.full_name}</strong><span>{session.user.email}</span><small>{roleLabel(session.user.role)}</small></div>
        <div className="sidebar-actions">
          <button className="refresh-button" onClick={() => refresh()}><RefreshCw size={16}/> Actualiser</button>
          <button className="refresh-button" onClick={logout}><LogOut size={16}/> Déconnexion</button>
        </div>
        <a className="sidebar-public-link" href={publicLink} target="_blank"><span>Formulaire client</span><strong>{session.user.organization.slug}</strong></a>
        <label className="sidebar-search">Rechercher un dossier<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nom, téléphone, courriel…" /></label>
        <div className="prospect-count"><Users size={18}/> {filteredProspects.length} dossier(s)</div>
        <div className="advisor-list">{filteredProspects.length === 0 && <p className="muted">Aucun dossier ne correspond à votre recherche.</p>}{filteredProspects.map((item) => <button key={item.id} className={selected?.id === item.id ? 'advisor-row selected' : 'advisor-row'} onClick={() => loadDetail(item.id)}><strong>{item.client_name}</strong><span>{item.phone || item.email || 'Contact à compléter'} · {statusLabel(item.status)}</span></button>)}</div>
      </aside>
      <section className="advisor-content">
        <header className="advisor-header advisor-command-center"><div><p className="eyebrow">Espace conseiller FINAB</p><h1>{canAdminister ? 'Pilotage des conseillers et dossiers ABF' : 'Dossiers clients et génération ABF'}</h1><p>Un tableau de bord clair pour suivre les demandes reçues, ouvrir le formulaire client et produire les documents ABF validés.</p></div><a className="public-link" href={publicLink} target="_blank">Ouvrir le formulaire client</a></header>
        <section className="advisor-kpis">
          <div><span>Dossiers reçus</span><strong>{prospects.length}</strong><small>Total disponible</small></div>
          <div><span>À traiter</span><strong>{pendingCount}</strong><small>Demandes en attente</small></div>
          <div><span>PDF ABF</span><strong>{generatedCount}</strong><small>Documents générés</small></div>
          <div><span>Dossier ouvert</span><strong>{selectedStatus}</strong><small>{selected?.client_name || 'Sélectionnez un client'}</small></div>
        </section>
        <section className="advisor-workflow-strip">
          <div><CheckCircle2 size={18}/><span>1. Recevoir le formulaire</span></div>
          <div><Pencil size={18}/><span>2. Corriger dans l’espace, même sur téléphone</span></div>
          <div><Download size={18}/><span>3. Générer le PDF final</span></div>
        </section>
        {canAdminister && <AdminPanel session={session} />}
        {message && <div className="notice success"><CheckCircle2 size={20}/> {message}{latestPdfPath && <button className="inline-link" onClick={() => downloadPdf(latestPdfPath)}>Télécharger le PDF ABF</button>}</div>}
        {!selected && <section className="advisor-card"><p className="muted">Aucun prospect sélectionné.</p></section>}
        {selected && p && <>
          <section className="advisor-card client-main client-spotlight"><div className="client-avatar">{selectedInitials}</div><div><div className="client-title-line"><h2>{selected.client_name}</h2><span>{selectedStatus}</span></div><p>{safe(selected.phone)} · {safe(selected.email)}</p><p className="muted">Dossier reçu le {new Date(selected.created_at).toLocaleString('fr-CA')}</p></div><div className="client-actions"><button className="refresh-button" disabled={loading} onClick={saveAbfPageEdits}><CheckCircle2 size={16}/> Enregistrer les corrections</button>{pdfPreviewUrl && <a className="refresh-button" href={pdfPreviewUrl} target="_blank" rel="noreferrer"><FileText size={16}/> Voir le PDF final</a>}<button className="submit-button" disabled={loading} onClick={generateAbf}>{loading ? <Loader2 className="spin"/> : <Download size={18}/>} Générer le PDF final</button></div></section>
          <PdfFormEditor previewUrl={pdfPreviewUrl} pdfPath={latestPdfPath} token={token || ''} loading={loading} onGenerate={generateAbf} onUpdateFields={updatePdfFields} onDownload={() => downloadPdf(latestPdfPath)} />
          <EditableAbfPreview form={editForm} setForm={setEditForm} review={reviewForm} setReview={setReviewForm} loading={loading} onSave={saveAbfPageEdits} onExport={generateAbf} />
          <section className="advisor-card"><h2>Documents ABF générés</h2>{(!selected.documents || selected.documents.length === 0) && <p className="muted">Aucun document généré pour ce prospect.</p>}{selected.documents?.map((doc, idx) => <button className="doc-row" key={idx} onClick={() => downloadPdf(doc.output_path || '')}><FileText size={18}/> Télécharger l’ABF généré {doc.created_at ? new Date(doc.created_at).toLocaleString('fr-CA') : ''}</button>)}</section>
        </>}
      </section>
    </main>
  );
}

function AdminPanel({ session }: { session: AuthSession }) {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [newUser, setNewUser] = useState({ full_name: '', email: '', password: '', role: 'advisor', organization_name: '', organization_slug: '', advisor_phone: '', plan: 'finab_pro', subscription_status: 'active', duration: 'unlimited' });
  const token = session.token;
  async function refreshAdmin() {
    setLoading(true); setMessage('');
    try {
      const [stats, rows] = await Promise.all([
        api<AdminOverview>('/api/admin/overview', undefined, token),
        api<AdminUser[]>('/api/admin/users', undefined, token),
      ]);
      setOverview(stats); setUsers(rows);
    } catch { setMessage('Impossible de charger le tableau super administrateur.'); }
    finally { setLoading(false); }
  }
  async function createAdminUser(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setMessage('');
    try {
      const current_period_end = newUser.subscription_status === 'active' && newUser.duration !== 'unlimited' ? isoDaysFromNow(Number(newUser.duration)) : null;
      const plan = newUser.duration === 'off' ? 'free' : newUser.plan;
      await api<AdminUser>('/api/admin/users', { method: 'POST', body: JSON.stringify({ ...newUser, plan, current_period_end }) }, token);
      setNewUser({ full_name: '', email: '', password: '', role: 'advisor', organization_name: '', organization_slug: '', advisor_phone: '', plan: 'finab_pro', subscription_status: 'active', duration: 'unlimited' });
      setMessage('Accès créé et abonnement appliqué.'); await refreshAdmin();
    } catch (error) {
      let detail = 'Création utilisateur impossible.';
      try {
        const parsed = JSON.parse(error instanceof Error ? error.message : String(error));
        if (Array.isArray(parsed.detail)) detail = parsed.detail.map((item: any) => item.msg || item.message || String(item)).join(' ');
        else if (parsed.detail) detail = String(parsed.detail);
      } catch { /* keep default message */ }
      setMessage(detail);
      setLoading(false);
    }
  }
  async function grantAccess(user: AdminUser, duration: 'unlimited' | '30' | '90' | '365' | 'off', plan: 'finab_pro' | 'enterprise' = 'finab_pro') {
    setLoading(true); setMessage('');
    const body = duration === 'off'
      ? { plan: 'free', subscription_status: 'incomplete', current_period_end: null, last_payment_status: 'admin_revoked' }
      : { plan, subscription_status: 'active', current_period_end: duration === 'unlimited' ? null : isoDaysFromNow(Number(duration)), last_payment_status: 'admin_grant' };
    try { await api<AdminUser>(`/api/admin/users/${user.id}`, { method: 'PATCH', body: JSON.stringify(body) }, token); setMessage(`Accès mis à jour pour ${user.full_name}.`); await refreshAdmin(); }
    catch { setMessage('Mise à jour abonnement impossible.'); setLoading(false); }
  }
  async function changeRole(user: AdminUser, role: string) {
    setLoading(true); setMessage('');
    try { await api<AdminUser>(`/api/admin/users/${user.id}`, { method: 'PATCH', body: JSON.stringify({ role }) }, token); await refreshAdmin(); }
    catch { setMessage('Modification du rôle impossible.'); setLoading(false); }
  }
  async function toggleUser(user: AdminUser) {
    setLoading(true); setMessage('');
    try { await api<AdminUser>(`/api/admin/users/${user.id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !user.is_active }) }, token); await refreshAdmin(); }
    catch { setMessage('Modification impossible.'); setLoading(false); }
  }
  async function deleteUser(user: AdminUser) {
    if (!confirm(`Supprimer ${user.full_name} ?`)) return;
    setLoading(true); setMessage('');
    try { await api<{ ok: boolean }>(`/api/admin/users/${user.id}`, { method: 'DELETE' }, token); await refreshAdmin(); }
    catch { setMessage('Suppression impossible.'); setLoading(false); }
  }
  useEffect(() => { refreshAdmin(); }, []);
  return (
    <section className="admin-panel">
      <div className="admin-panel-head"><div><p className="eyebrow">Super administration FINAB</p><h2>Commandes générales de la plateforme</h2><p>Créez des administrateurs, activez des abonnements illimités ou limités, bloquez les comptes et surveillez toute l’activité ABF.</p></div><button className="refresh-button" onClick={refreshAdmin} disabled={loading}><RefreshCw size={16}/> Rafraîchir</button></div>
      {message && <div className="notice success">{message}</div>}
      <div className="admin-stats">
        <div><strong>{overview?.organizations ?? '—'}</strong><span>Organisations</span></div>
        <div><strong>{overview?.users ?? '—'}</strong><span>Utilisateurs</span></div>
        <div><strong>{overview?.active_users ?? '—'}</strong><span>Actifs</span></div>
        <div><strong>{overview?.admins ?? '—'}</strong><span>Administrateurs</span></div>
        <div><strong>{overview?.unlimited_users ?? '—'}</strong><span>Illimités</span></div>
        <div><strong>{overview?.prospects ?? '—'}</strong><span>Dossiers clients</span></div>
        <div><strong>{overview?.documents ?? '—'}</strong><span>PDF ABF</span></div>
      </div>
      <form className="admin-create" onSubmit={createAdminUser}>
        <h3><UserPlus size={18}/> Ajouter un administrateur ou un abonné</h3>
        <input placeholder="Nom complet" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} />
        <input placeholder="Courriel" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
        <input placeholder="Mot de passe provisoire" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} type="password" />
        <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}><option value="advisor">Conseiller</option><option value="admin">Directeur FINAB</option><option value="owner">Super administrateur</option></select>
        <select value={newUser.plan} onChange={(e) => setNewUser({ ...newUser, plan: e.target.value })}><option value="finab_pro">Pro ABF</option><option value="enterprise">Illimité</option><option value="free">Sans accès</option></select>
        <select value={newUser.duration} onChange={(e) => setNewUser({ ...newUser, duration: e.target.value, subscription_status: e.target.value === 'off' ? 'incomplete' : 'active' })}><option value="unlimited">Illimité</option><option value="30">1 mois</option><option value="90">90 jours</option><option value="365">1 an</option><option value="off">Accès non activé</option></select>
        <input placeholder="Organisation" value={newUser.organization_name} onChange={(e) => setNewUser({ ...newUser, organization_name: e.target.value })} />
        <input placeholder="Lien personnalisé du formulaire" value={newUser.organization_slug} onChange={(e) => setNewUser({ ...newUser, organization_slug: e.target.value })} />
        <input placeholder="Téléphone" value={newUser.advisor_phone} onChange={(e) => setNewUser({ ...newUser, advisor_phone: e.target.value })} />
        <button className="submit-button compact" disabled={loading || !newUser.email || !newUser.password || !newUser.full_name}>Créer</button>
      </form>
      <div className="admin-users">
        {users.map((user) => <div className="admin-user-row" key={user.id}><div><strong>{user.full_name}</strong><span>{user.email} · {roleLabel(user.role)} · {user.organization?.name}</span><small>{planLabel(user.subscription?.plan)} · {accessLabel(user.subscription)} · {user.is_active ? 'Compte actif' : 'Compte bloqué'}</small></div><div className="admin-actions admin-actions-wrap"><select value={user.role} onChange={(event) => changeRole(user, event.target.value)} disabled={user.id === session.user.id}><option value="advisor">Conseiller</option><option value="admin">Directeur FINAB</option><option value="owner">Super administrateur</option></select><button onClick={() => grantAccess(user, 'unlimited', 'enterprise')}>Illimité</button><button onClick={() => grantAccess(user, '30')}>1 mois</button><button onClick={() => grantAccess(user, '90')}>90 jours</button><button onClick={() => grantAccess(user, '365')}>1 an</button><button onClick={() => grantAccess(user, 'off')}>Couper accès</button><button onClick={() => toggleUser(user)}>{user.is_active ? 'Bloquer' : 'Réactiver'}</button><button className="danger" onClick={() => deleteUser(user)} disabled={user.id === session.user.id}><Trash2 size={15}/> Supprimer</button></div></div>)}
      </div>
    </section>
  );
}


function pdfViewerUrl(path: string, token?: string) {
  return path && token ? `/abf/view?path=${encodeURIComponent(path)}&token=${encodeURIComponent(token)}#zoom=page-width` : '';
}

function PdfFormEditor({ previewUrl, pdfPath, token, loading, onGenerate, onUpdateFields, onDownload }: { previewUrl: string; pdfPath: string; token: string; loading: boolean; onGenerate: () => void; onUpdateFields: (path: string, fields: Record<string, string>) => void; onDownload: () => void }) {
  const [pageCount, setPageCount] = useState(1);
  const [page, setPage] = useState(0);
  const [fields, setFields] = useState<PdfField[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    setPage(0); setFields([]); setValues({}); setLoadError('');
    if (!pdfPath || !token) return;
    setFieldsLoading(true);
    Promise.all([
      api<{ page_count: number }>(`/api/pdf/info?path=${encodeURIComponent(pdfPath)}`, undefined, token),
      api<{ fields: PdfField[] }>(`/api/pdf/fields?path=${encodeURIComponent(pdfPath)}`, undefined, token),
    ])
      .then(([info, data]) => {
        setPageCount(Math.max(info.page_count || 1, 1));
        setFields(data.fields || []);
        setValues(Object.fromEntries((data.fields || []).map((field) => [field.name, field.value || ''])));
      })
      .catch(() => setLoadError('Impossible de charger les champs du PDF pour ce dossier.'))
      .finally(() => setFieldsLoading(false));
  }, [pdfPath, token]);

  const pageIndexes = Array.from({ length: pageCount }, (_, index) => index);
  const imageUrlForPage = (pageIndex: number) => pdfPath && token ? `/api/pdf/page-image?path=${encodeURIComponent(pdfPath)}&page=${pageIndex}&token=${encodeURIComponent(token)}&v=${encodeURIComponent(pdfPath)}` : '';
  const originalByName = useMemo(() => Object.fromEntries(fields.map((field) => [field.name, field.value || ''])), [fields]);
  const changedFields = useMemo(() => {
    const diff: Record<string, string> = {};
    for (const field of fields) {
      if ((values[field.name] ?? '') !== (originalByName[field.name] ?? '')) diff[field.name] = values[field.name] ?? '';
    }
    return diff;
  }, [fields, values, originalByName]);
  const changedCount = Object.keys(changedFields).length;
  function setFieldValue(name: string, value: string) { setValues((current) => ({ ...current, [name]: value })); }
  function resetChanges() { setValues(Object.fromEntries(fields.map((field) => [field.name, field.value || '']))); }

  return <section className="advisor-card pdf-editor-card">
    <div className="pdf-editor-head">
      <div><p className="eyebrow">Éditeur PDF intégré</p><h2>Modifier directement les champs du PDF</h2><p>Cliquez dans n’importe quel champ affiché sur le PDF, corrigez la valeur, puis enregistrez. Les modifications sont écrites dans les vrais champs du formulaire ABF, sans repasser par le formulaire client.</p></div>
      <div className="edit-actions"><button className="submit-button compact" type="button" disabled={loading} onClick={onGenerate}>{loading ? <Loader2 className="spin"/> : <Download size={16}/>} Régénérer depuis le formulaire</button>{previewUrl && <a className="refresh-button" href={previewUrl} target="_blank" rel="noreferrer"><FileText size={16}/> Voir le PDF</a>}{pdfPath && <button className="refresh-button" type="button" onClick={onDownload}><FileText size={16}/> Télécharger</button>}</div>
    </div>
    {!previewUrl && <div className="pdf-empty-state"><FileText size={34}/><strong>Aucun PDF final généré pour ce dossier.</strong><span>Remplissez ou corrigez les champs ABF ci-dessous, puis cliquez sur “Générer le PDF final”.</span></div>}
    {previewUrl && <>
      <div className="pdf-editor-toolbar">
        <button type="button" onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>Page précédente</button>
        <strong>Page {page + 1} / {pageCount}</strong>
        <button type="button" onClick={() => setPage(Math.min(pageCount - 1, page + 1))} disabled={page + 1 >= pageCount}>Page suivante</button>
        <div className="pdf-page-jump" aria-label="Accès rapide aux pages PDF">{pageIndexes.map((pageIndex) => <button key={pageIndex} type="button" className={pageIndex === page ? 'active' : ''} onClick={() => setPage(pageIndex)}>P{pageIndex + 1}</button>)}</div>
        <button type="button" onClick={resetChanges} disabled={changedCount === 0}>Annuler les modifications</button>
        <button className="submit-button compact" type="button" disabled={loading || changedCount === 0} onClick={() => onUpdateFields(pdfPath, changedFields)}>{loading ? <Loader2 className="spin"/> : <CheckCircle2 size={16}/>} Enregistrer les modifications</button>
      </div>
      <p className="pdf-helper">{fieldsLoading ? 'Chargement des champs du PDF…' : loadError || `Les ${fields.length} champs éditables du PDF sont superposés à l’aperçu ci-dessous. Modifiez-les directement, même sur téléphone, puis enregistrez. Champs modifiés : ${changedCount}.`}</p>
      <div className="pdf-canvas-shell all-pages">
        {pageIndexes.map((pageIndex) => {
          const pageFields = fields.filter((field) => field.page === pageIndex);
          const pageImageUrl = imageUrlForPage(pageIndex);
          return <div className={pageIndex === page ? 'pdf-page-block selected' : 'pdf-page-block'} key={pageIndex}>
            <div className="pdf-page-label"><strong>Page {pageIndex + 1}</strong><span>{pageFields.length} champ(s)</span><button type="button" onClick={() => setPage(pageIndex)}>Sélectionner cette page</button></div>
            <div className="pdf-page-canvas pdf-form-canvas">
              {pageImageUrl && <img src={pageImageUrl} alt={`Page ${pageIndex + 1} du PDF ABF`} loading="lazy" />}
              {pageFields.map((field) => {
                const [x0, y0, x1, y1] = field.rect;
                const style: React.CSSProperties = { left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` };
                const changed = (values[field.name] ?? '') !== (originalByName[field.name] ?? '');
                const common = { value: values[field.name] ?? '', title: field.name, onFocus: () => setPage(pageIndex), 'aria-label': field.name };
                return <div className={changed ? 'pdf-field-overlay changed' : 'pdf-field-overlay'} key={`${field.name}-${x0}-${y0}`} style={style}>
                  {field.multiline
                    ? <textarea {...common} onChange={(event) => setFieldValue(field.name, event.target.value)} />
                    : field.options && field.options.length > 0
                      ? <select {...common} onChange={(event) => setFieldValue(field.name, event.target.value)}><option value="">—</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}</select>
                      : <input {...common} maxLength={field.max_length || undefined} onChange={(event) => setFieldValue(field.name, event.target.value)} />}
                </div>;
              })}
            </div>
          </div>;
        })}
      </div>
    </>}
  </section>;
}


function EditableAbfPreview({ form, setForm, review, setReview, loading, onSave, onExport }: { form: FormState; setForm: (form: FormState) => void; review: ReviewState; setReview: (form: ReviewState) => void; loading: boolean; onSave: () => void; onExport: () => void }) {
  const setClient = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });
  const setAdvisor = (key: keyof ReviewState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setReview({ ...review, [key]: event.target.value });
  const automaticCoverage = Math.max((numberValue(form.annualIncome) * numberValue(review.replacement_years)) - numberValue(form.totalAssets) + numberValue(form.totalDebts), 0);
  const displayedCoverage = numberValue(review.final_recommended_coverage) || automaticCoverage;
  return <section className="advisor-card abf-editor-card">
    <div className="abf-editor-head">
      <div><p className="eyebrow">ABF visible et modifiable dans l’espace</p><h2>Formulaire ABF à corriger ici</h2><p>Tapez directement dans les champs ci-dessous, même sur téléphone. Aucun clic sur un lien PDF n’est nécessaire pour modifier le dossier.</p></div>
      <div className="edit-actions"><button className="refresh-button" type="button" disabled={loading} onClick={onSave}><CheckCircle2 size={16}/> Enregistrer</button><button className="submit-button compact" type="button" disabled={loading} onClick={onExport}>{loading ? <Loader2 className="spin"/> : <Download size={16}/>} Générer PDF final</button></div>
    </div>
    <div className="abf-paper">
      <div className="abf-paper-title"><div><span>FINAB Solution</span><strong>ABF — Dossier client</strong></div><small>Document de travail conseiller</small></div>
      <div className="abf-band">1. Identification du client</div>
      <div className="abf-fields three">
        <AbfField label="Nom" value={form.legalLastName} onChange={setClient('legalLastName')} />
        <AbfField label="Prénoms" value={form.firstNames} onChange={setClient('firstNames')} />
        <AbfField label="Date de naissance" value={form.dateOfBirth} onChange={setClient('dateOfBirth')} type="date" />
        <AbfField label="Lieu de naissance" value={form.placeOfBirth} onChange={setClient('placeOfBirth')} />
        <label className="abf-field"><span>Situation familiale</span><select value={form.maritalStatus} onChange={setClient('maritalStatus')}><option value="">Sélectionner</option><option value="marié">Marié</option><option value="célibataire">Célibataire</option><option value="monoparental">Monoparental avec Enfants</option><option value="conjoint de fait">Conjoint de fait</option><option value="autre">Autre</option></select></label>
        <AbfField label="Enfants à charge" value={form.dependents} onChange={setClient('dependents')} inputMode="numeric" />
        <AbfField label="Arrivée au Canada" value={form.arrivalInCanada} onChange={setClient('arrivalInCanada')} type="date" />
        <AbfField label="Téléphone" value={form.phone} onChange={setClient('phone')} />
        <AbfField label="Courriel" value={form.email} onChange={setClient('email')} />
      </div>
      <AbfArea label="Adresse complète" value={form.address} onChange={setClient('address')} />
      <div className="abf-band">2. Emploi, revenus et situation financière</div>
      <div className="abf-fields two">
        <AbfField label="Emploi / titre / poste" value={form.occupation} onChange={setClient('occupation')} />
        <AbfField label="Adresse emploi" value={form.employerAddress} onChange={setClient('employerAddress')} />
        <AbfField label="Revenu annuel" value={form.annualIncome} onChange={setClient('annualIncome')} inputMode="decimal" />
        <AbfField label="Valeur totale des biens" value={form.totalAssets} onChange={setClient('totalAssets')} inputMode="decimal" />
        <AbfField label="Total des dettes" value={form.totalDebts} onChange={setClient('totalDebts')} inputMode="decimal" />
        <AbfField label="Budget mensuel confortable" value={form.acceptableBudget} onChange={setClient('acceptableBudget')} inputMode="decimal" />
      </div>
      <div className="abf-band">3. Assurance, santé et objectifs</div>
      <div className="abf-fields two">
        <label className="abf-field"><span>Assurance vie existante</span><select value={form.hasExistingInsurance} onChange={setClient('hasExistingInsurance')}><option value="">Sélectionner</option><option value="oui">Oui</option><option value="non">Non</option></select></label>
        <AbfField label="Taille" value={form.height} onChange={setClient('height')} />
        <AbfField label="Poids" value={form.weight} onChange={setClient('weight')} />
        <AbfField label="Code postal" value={form.postalCode} onChange={setClient('postalCode')} />
      </div>
      <AbfArea label="Détails assurances / placements actuels" value={form.existingInsuranceDetails} onChange={setClient('existingInsuranceDetails')} />
      <AbfArea label="Si aucune assurance : raison" value={form.noInsuranceReason} onChange={setClient('noInsuranceReason')} />
      <AbfArea label="Disponibilités" value={form.availability} onChange={setClient('availability')} />
      <AbfArea label="Projets prioritaires / besoins familiaux" value={form.priorityProjects} onChange={setClient('priorityProjects')} />
      <div className="abf-band">4. Recommandation du conseiller</div>
      <div className="abf-calculation-strip"><div><span>Couverture calculée</span><strong>{money(displayedCoverage)} $</strong></div><div><span>Années de revenu</span><strong>{review.replacement_years || '0'}</strong></div><div><span>Budget client</span><strong>{money(form.acceptableBudget)} $/mois</strong></div></div>
      <div className="abf-fields three">
        <AbfField label="Conseiller" value={review.advisor_name} onChange={setAdvisor('advisor_name')} />
        <AbfField label="Téléphone conseiller" value={review.advisor_phone} onChange={setAdvisor('advisor_phone')} />
        <AbfField label="Courriel conseiller" value={review.advisor_email} onChange={setAdvisor('advisor_email')} />
        <AbfField label="Date validation" value={review.signed_date} onChange={setAdvisor('signed_date')} type="date" />
        <AbfField label="Années remplacement revenu" value={review.replacement_years} onChange={setAdvisor('replacement_years')} inputMode="numeric" />
        <AbfField label="Couverture finale recommandée" value={review.final_recommended_coverage} onChange={setAdvisor('final_recommended_coverage')} inputMode="decimal" placeholder={`${money(automaticCoverage)} $ automatique`} />
        <AbfField label="Budget recommandation 1" value={review.recommendation_1_budget} onChange={setAdvisor('recommendation_1_budget')} inputMode="decimal" />
        <AbfField label="Budget recommandation 2" value={review.recommendation_2_budget} onChange={setAdvisor('recommendation_2_budget')} inputMode="decimal" />
        <AbfField label="Budget préféré client" value={review.client_preference_budget} onChange={setAdvisor('client_preference_budget')} inputMode="decimal" />
      </div>
      <AbfArea label="Notes recommandation 1" value={review.recommendation_1_notes} onChange={setAdvisor('recommendation_1_notes')} />
      <AbfArea label="Notes recommandation 2" value={review.recommendation_2_notes} onChange={setAdvisor('recommendation_2_notes')} />
      <AbfArea label="Préférence client / justification" value={review.preference_notes} onChange={setAdvisor('preference_notes')} />
      <AbfArea label="Notes finales du conseiller" value={review.agent_notes} onChange={setAdvisor('agent_notes')} />
    </div>
  </section>;
}

function AbfField({ label, value, onChange, type = 'text', inputMode, placeholder }: { label: string; value: string; onChange: (event: React.ChangeEvent<HTMLInputElement>) => void; type?: string; inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode']; placeholder?: string }) {
  return <label className="abf-field"><span>{label}</span><input type={type} value={value} onChange={onChange} inputMode={inputMode} placeholder={placeholder} /></label>;
}

function AbfArea({ label, value, onChange }: { label: string; value: string; onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void }) {
  return <label className="abf-field abf-area"><span>{label}</span><textarea value={value} onChange={onChange} /></label>;
}

function AdvisorReviewForm({ form, setForm, loading, onSave }: { form: ReviewState; setForm: (form: ReviewState) => void; loading: boolean; onSave: () => void }) {
  const set = (key: keyof ReviewState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [key]: event.target.value });
  return <section className="advisor-card edit-prospect-card advisor-review-card">
    <div className="edit-prospect-head"><div><h2>Préparation ABF modifiable avant export</h2><p className="muted">Le conseiller peut corriger ici les calculs, budgets, recommandations et notes qui seront injectés dans le PDF exporté.</p></div><div className="edit-actions"><button className="submit-button compact" type="button" onClick={onSave} disabled={loading}>{loading ? <Loader2 className="spin"/> : <CheckCircle2 size={16}/>} Enregistrer la préparation</button></div></div>
    <div className="form-grid edit-form-grid">
      <label>Nom du conseiller<input value={form.advisor_name} onChange={set('advisor_name')} /></label>
      <label>Téléphone conseiller<input value={form.advisor_phone} onChange={set('advisor_phone')} /></label>
      <label>Courriel conseiller<input value={form.advisor_email} onChange={set('advisor_email')} /></label>
      <label>Date de signature / validation<input type="date" value={form.signed_date} onChange={set('signed_date')} /></label>
      <label>Années de remplacement de revenu<input value={form.replacement_years} onChange={set('replacement_years')} inputMode="numeric" /></label>
      <label>Couverture finale recommandée<input value={form.final_recommended_coverage} onChange={set('final_recommended_coverage')} inputMode="decimal" placeholder="Laisser vide pour utiliser le calcul automatique" /></label>
      <label>Budget recommandation 1<input value={form.recommendation_1_budget} onChange={set('recommendation_1_budget')} inputMode="decimal" /></label>
      <label>Budget recommandation 2<input value={form.recommendation_2_budget} onChange={set('recommendation_2_budget')} inputMode="decimal" /></label>
      <label>Budget préféré du client<input value={form.client_preference_budget} onChange={set('client_preference_budget')} inputMode="decimal" /></label>
      <label className="span-2">Notes recommandation 1<textarea value={form.recommendation_1_notes} onChange={set('recommendation_1_notes')} placeholder="Texte qui remplace la recommandation automatique dans le PDF" /></label>
      <label className="span-2">Notes recommandation 2<textarea value={form.recommendation_2_notes} onChange={set('recommendation_2_notes')} /></label>
      <label className="span-2">Préférence client / justification<textarea value={form.preference_notes} onChange={set('preference_notes')} /></label>
      <label className="span-2">Notes agent à exporter<textarea value={form.agent_notes} onChange={set('agent_notes')} placeholder="Notes finales du conseiller dans le document ABF" /></label>
    </div>
  </section>;
}


function EditableProspectForm({ form, setForm, loading, onSave, onCancel }: { form: FormState; setForm: (form: FormState) => void; loading: boolean; onSave: () => void; onCancel: () => void }) {
  const set = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: event.target.value });
  const canSave = Boolean(form.legalLastName && form.firstNames && form.dateOfBirth && form.phone && form.email);
  return <section className="advisor-card edit-prospect-card">
    <div className="edit-prospect-head"><div><h2>Corriger le formulaire client</h2><p className="muted">Modifiez ici les informations avant de générer ou régénérer le PDF ABF.</p></div><div className="edit-actions"><button className="refresh-button" type="button" onClick={onCancel} disabled={loading}><X size={16}/> Annuler</button><button className="submit-button compact" type="button" onClick={onSave} disabled={loading || !canSave}>{loading ? <Loader2 className="spin"/> : <CheckCircle2 size={16}/>} Enregistrer les corrections</button></div></div>
    <div className="form-grid edit-form-grid">
      <label>Nom de famille<input value={form.legalLastName} onChange={set('legalLastName')} /></label>
      <label>Prénoms<input value={form.firstNames} onChange={set('firstNames')} /></label>
      <label>Date de naissance<input type="date" value={form.dateOfBirth} onChange={set('dateOfBirth')} /></label>
      <label>Lieu de naissance<input value={form.placeOfBirth} onChange={set('placeOfBirth')} /></label>
      <label>Situation familiale<select value={form.maritalStatus} onChange={set('maritalStatus')}><option value="">Sélectionner</option><option value="marié">Marié</option><option value="célibataire">Célibataire</option><option value="monoparental">Monoparental avec Enfants</option><option value="conjoint de fait">Conjoint de fait</option><option value="autre">Autre</option></select></label>
      <label>Enfants à charge<input value={form.dependents} onChange={set('dependents')} inputMode="numeric" /></label>
      <label>Date d'arrivée au Canada<input type="date" value={form.arrivalInCanada} onChange={set('arrivalInCanada')} /></label>
      <label>Téléphone<input value={form.phone} onChange={set('phone')} /></label>
      <label>Courriel<input value={form.email} onChange={set('email')} /></label>
      <label className="span-2">Adresse de domicile<input value={form.address} onChange={set('address')} placeholder="Rue, ville, province" /></label>
      <label>Code postal<input value={form.postalCode} onChange={set('postalCode')} /></label>
      <label className="span-2">Emploi actuel, titre et poste<input value={form.occupation} onChange={set('occupation')} /></label>
      <label className="span-2">Adresse emploi<input value={form.employerAddress} onChange={set('employerAddress')} /></label>
      <label>Revenu annuel<input value={form.annualIncome} onChange={set('annualIncome')} inputMode="decimal" /></label>
      <label>Total des biens<input value={form.totalAssets} onChange={set('totalAssets')} inputMode="decimal" /></label>
      <label>Total des dettes<input value={form.totalDebts} onChange={set('totalDebts')} inputMode="decimal" /></label>
      <label>Assurance vie existante<select value={form.hasExistingInsurance} onChange={set('hasExistingInsurance')}><option value="">Sélectionner</option><option value="oui">Oui</option><option value="non">Non</option></select></label>
      <label className="span-2">Détails assurance / placements<textarea value={form.existingInsuranceDetails} onChange={set('existingInsuranceDetails')} /></label>
      <label className="span-2">Si non : raison<textarea value={form.noInsuranceReason} onChange={set('noInsuranceReason')} /></label>
      <label>Budget mensuel confortable<input value={form.acceptableBudget} onChange={set('acceptableBudget')} inputMode="decimal" /></label>
      <label>Taille<input value={form.height} onChange={set('height')} /></label>
      <label>Poids<input value={form.weight} onChange={set('weight')} /></label>
      <label className="span-2">Disponibilités<textarea value={form.availability} onChange={set('availability')} /></label>
      <label className="span-2">Projets prioritaires<textarea value={form.priorityProjects} onChange={set('priorityProjects')} /></label>
    </div>
  </section>;
}

function InfoCard({ title, rows }: { title: string; rows: Array<[string, any]> }) { return <section className="advisor-card"><h2>{title}</h2><dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{safe(value)}</dd></div>)}</dl></section>; }
function App() { return (window.location.pathname.startsWith('/conseiller') || window.location.pathname.startsWith('/inscription')) ? <AdvisorDashboard /> : <PublicForm />; }

createRoot(document.getElementById('root')!).render(<App />);
