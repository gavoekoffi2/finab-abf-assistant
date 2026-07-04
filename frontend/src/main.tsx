import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, CreditCard, Crown, Download, FileText, Loader2, LogOut, RefreshCw, ShieldCheck, Sparkles, Trash2, UserPlus, Users } from 'lucide-react';
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

type SubscriptionState = { plan?: string; status?: string; has_access?: boolean; in_trial?: boolean; trial_ends_at?: string | null; current_period_end?: string | null; price_usd?: number; trial_days?: number };
type Organization = { id?: string; name: string; slug: string; advisor_name: string; advisor_phone?: string; advisor_email?: string };
type User = { id: string; email: string; full_name: string; role: string; organization_id: string; organization: Organization; is_active?: boolean; subscription?: SubscriptionState };
type AuthSession = { token: string; expires_at: string; user: User };
type BillingConfig = { plan_name: string; price_usd: number; trial_days: number; subscription: SubscriptionState } & Record<string, unknown>;
type ProspectSummary = { id: string; organization_id?: string; advisor_slug?: string; client_name: string; phone: string; email: string; status: string; created_at: string; updated_at?: string };
type ProspectDetail = ProspectSummary & { payload: any; documents?: Array<{ id?: string; output_path?: string; created_at?: string; report?: any }> };
type AdminOverview = { organizations: number; users: number; active_users: number; prospects: number; documents: number; recent_prospects: ProspectSummary[] };
type AdminUser = User & { organization: Organization };

const AUTH_KEY = 'finab_abf_session';

const emptyForm: FormState = {
  legalLastName: '', firstNames: '', dateOfBirth: '', placeOfBirth: '', maritalStatus: '', dependents: '', arrivalInCanada: '', phone: '', email: '', address: '', postalCode: '', occupation: '', employerAddress: '', annualIncome: '', totalAssets: '', totalDebts: '', hasExistingInsurance: '', existingInsuranceDetails: '', noInsuranceReason: '', acceptableBudget: '', height: '', weight: '', availability: '', priorityProjects: '',
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
const roleLabel = (role: string) => ({ owner: 'Direction FINAB', admin: 'Responsable', advisor: 'Conseiller' } as Record<string, string>)[role] || 'Conseiller';

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
  async function refreshAccount() {
    try {
      const current = await api<User>('/api/me', undefined, session.token);
      const next = { ...session, user: current };
      localStorage.setItem(AUTH_KEY, JSON.stringify(next));
      onRefresh(next);
    } catch { setMessage('Impossible de rafraîchir le compte pour le moment.'); }
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
    if (params.get('checkout') === 'success') refreshAccount();
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
          <button className="text-switch" onClick={refreshAccount}>J’ai déjà payé, rafraîchir mon accès</button>
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
    try { setSelected(await api<ProspectDetail>(`/api/prospects/${id}`, undefined, token)); }
    catch { setMessage('Impossible de charger ce prospect.'); }
    finally { setLoading(false); }
  }
  async function generateAbf() {
    if (!selected || !token) return;
    setLoading(true); setMessage(''); setPdfPath('');
    try {
      const result = await api<{ output_path: string }>(`/api/prospects/${selected.id}/generate-abf`, { method: 'POST', body: '{}' }, token);
      setPdfPath(result.output_path);
      setMessage('Document ABF généré avec succès.');
      await refresh(selected.id);
    } catch { setMessage("Impossible de générer l'ABF pour ce prospect."); }
    finally { setLoading(false); }
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
    if (!token || (!session?.user.subscription?.has_access && session?.user.role !== 'owner')) return;
    refresh().catch(() => { localStorage.removeItem(AUTH_KEY); setSession(null); });
  }, [token]);
  if (!session) return <LoginScreen onLogin={setSession} initialMode={window.location.pathname.startsWith('/inscription') ? 'register' : 'login'} />;
  if (session.user.role !== 'owner' && !session.user.subscription?.has_access) return <BillingScreen session={session} onRefresh={setSession} onLogout={logout} />;

  const p = selected?.payload;
  const publicLink = `/apply/${session.user.organization.slug}`;
  return (
    <main className="advisor-page">
      <aside className="advisor-sidebar">
        <div className="brand-line"><div className="mark">F</div><span>{session.user.organization.name}</span></div>
        <div className="advisor-user"><strong>{session.user.full_name}</strong><span>{session.user.email}</span></div>
        <button className="refresh-button" onClick={() => refresh()}><RefreshCw size={16}/> Actualiser</button>
        <button className="refresh-button" onClick={logout}><LogOut size={16}/> Déconnexion</button>
        <div className="prospect-count"><Users size={18}/> {prospects.length} prospect(s)</div>
        <div className="advisor-list">{prospects.length === 0 && <p className="muted">Aucun prospect reçu pour le moment.</p>}{prospects.map((item) => <button key={item.id} className={selected?.id === item.id ? 'advisor-row selected' : 'advisor-row'} onClick={() => loadDetail(item.id)}><strong>{item.client_name}</strong><span>{item.phone || item.email || 'Sans contact'} · {statusLabel(item.status)}</span></button>)}</div>
      </aside>
      <section className="advisor-content">
        <header className="advisor-header"><div><p className="eyebrow">Espace conseiller</p><h1>{session.user.role === 'owner' ? 'Gestion des conseillers et génération ABF' : 'Prospects reçus et génération ABF'}</h1><p>{session.user.role === 'owner' ? 'Pilotez les accès conseillers, les organisations, les dossiers reçus et les documents ABF.' : 'Consultez les dossiers transmis par vos clients et partagez votre formulaire personnalisé.'}</p></div><a className="public-link" href={publicLink} target="_blank">Ouvrir mon formulaire</a></header>
        {session.user.role === 'owner' && <AdminPanel session={session} />}
        {message && <div className="notice success"><CheckCircle2 size={20}/> {message}{pdfPath && <button className="inline-link" onClick={() => downloadPdf(pdfPath)}>Télécharger le PDF ABF</button>}</div>}
        {!selected && <section className="advisor-card"><p className="muted">Aucun prospect sélectionné.</p></section>}
        {selected && p && <>
          <section className="advisor-card client-main"><div><h2>{selected.client_name}</h2><p>{safe(selected.phone)} · {safe(selected.email)}</p><p className="muted">Reçu le {new Date(selected.created_at).toLocaleString('fr-CA')}</p></div><button className="submit-button" disabled={loading} onClick={generateAbf}>{loading ? <Loader2 className="spin"/> : <Download size={18}/>} Générer ABF</button></section>
          <div className="advisor-grid">
            <InfoCard title="Identité" rows={[[ 'Nom', p.identity?.legal_last_name ], [ 'Prénoms', p.identity?.first_names ], [ 'Date naissance', p.identity?.date_of_birth ], [ 'Lieu naissance', p.identity?.place_of_birth ], [ 'Statut', p.identity?.marital_status ], [ 'Enfants', p.identity?.dependents_count ], [ 'Arrivée Canada', p.identity?.arrival_in_canada ]]}/>
            <InfoCard title="Coordonnées" rows={[[ 'Téléphone', p.contact?.phone ], [ 'Courriel', p.contact?.email ], [ 'Adresse', [p.contact?.address, p.contact?.city, p.contact?.province, p.contact?.postal_code].filter(Boolean).join(', ') ]]}/>
            <InfoCard title="Emploi / revenus" rows={[[ 'Poste', p.employment?.occupation ], [ 'Adresse emploi', p.employment?.employer_address ], [ 'Revenu annuel', `$${money(p.employment?.annual_income)}` ]]}/>
            <InfoCard title="Finances" rows={[[ 'Total biens', `$${money(p.financial?.total_assets)}` ], [ 'Total dettes', `$${money(p.financial?.total_debts)}` ]]}/>
            <InfoCard title="Assurance / budget" rows={[[ 'Assurance existante', p.insurance?.has_existing_life_insurance ? 'Oui' : 'Non' ], [ 'Détails assurance / placements', p.insurance?.existing_retirement_savings_note ], [ 'Si non : raison', p.insurance?.no_insurance_reason ], [ 'Budget possible', `$${money(p.goals?.acceptable_monthly_budget)}` ]]}/>
            <InfoCard title="Santé / disponibilité / projets" rows={[[ 'Taille', p.health?.height ], [ 'Poids', p.health?.weight ], [ 'Disponibilité', p.meeting?.availability ], [ 'Projets prioritaires', p.goals?.priority_projects ]]}/>
          </div>
          <section className="advisor-card"><h2>Documents ABF générés</h2>{(!selected.documents || selected.documents.length === 0) && <p className="muted">Aucun document généré pour ce prospect.</p>}{selected.documents?.map((doc, idx) => <button className="doc-row" key={idx} onClick={() => downloadPdf(doc.output_path || '')}><FileText size={18}/> ABF généré {doc.created_at ? new Date(doc.created_at).toLocaleString('fr-CA') : ''}</button>)}</section>
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
  const [newUser, setNewUser] = useState({ full_name: '', email: '', password: '', role: 'advisor', organization_name: '', organization_slug: '', advisor_phone: '' });
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
      await api<AdminUser>('/api/admin/users', { method: 'POST', body: JSON.stringify(newUser) }, token);
      setNewUser({ full_name: '', email: '', password: '', role: 'advisor', organization_name: '', organization_slug: '', advisor_phone: '' });
      setMessage('Utilisateur créé.'); await refreshAdmin();
    } catch { setMessage('Création utilisateur impossible.'); setLoading(false); }
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
      <div className="admin-panel-head"><div><p className="eyebrow">Administration FINAB</p><h2>Gestion des conseillers ABF</h2><p>Suivi des accès, des organisations, des dossiers clients et des documents générés.</p></div><button className="refresh-button" onClick={refreshAdmin} disabled={loading}><RefreshCw size={16}/> Rafraîchir</button></div>
      {message && <div className="notice success">{message}</div>}
      <div className="admin-stats">
        <div><strong>{overview?.organizations ?? '—'}</strong><span>Organisations</span></div>
        <div><strong>{overview?.users ?? '—'}</strong><span>Utilisateurs</span></div>
        <div><strong>{overview?.active_users ?? '—'}</strong><span>Actifs</span></div>
        <div><strong>{overview?.prospects ?? '—'}</strong><span>Prospects</span></div>
        <div><strong>{overview?.documents ?? '—'}</strong><span>PDF ABF</span></div>
      </div>
      <form className="admin-create" onSubmit={createAdminUser}>
        <h3><UserPlus size={18}/> Ajouter un utilisateur</h3>
        <input placeholder="Nom complet" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} />
        <input placeholder="Courriel" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
        <input placeholder="Mot de passe provisoire" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} type="password" />
        <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}><option value="advisor">Conseiller</option><option value="admin">Responsable</option><option value="owner">Direction FINAB</option></select>
        <input placeholder="Organisation" value={newUser.organization_name} onChange={(e) => setNewUser({ ...newUser, organization_name: e.target.value })} />
        <input placeholder="Adresse du formulaire ex: conseiller-koffi" value={newUser.organization_slug} onChange={(e) => setNewUser({ ...newUser, organization_slug: e.target.value })} />
        <input placeholder="Téléphone" value={newUser.advisor_phone} onChange={(e) => setNewUser({ ...newUser, advisor_phone: e.target.value })} />
        <button className="submit-button compact" disabled={loading || !newUser.email || !newUser.password || !newUser.full_name}>Créer</button>
      </form>
      <div className="admin-users">
        {users.map((user) => <div className="admin-user-row" key={user.id}><div><strong>{user.full_name}</strong><span>{user.email} · {roleLabel(user.role)} · {user.organization?.name}</span><small>Formulaire conseiller prêt</small></div><div className="admin-actions"><button onClick={() => toggleUser(user)}>{user.is_active ? 'Désactiver' : 'Activer'}</button><button className="danger" onClick={() => deleteUser(user)} disabled={user.id === session.user.id}><Trash2 size={15}/> Supprimer</button></div></div>)}
      </div>
    </section>
  );
}

function InfoCard({ title, rows }: { title: string; rows: Array<[string, any]> }) { return <section className="advisor-card"><h2>{title}</h2><dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{safe(value)}</dd></div>)}</dl></section>; }
function App() { return (window.location.pathname.startsWith('/conseiller') || window.location.pathname.startsWith('/inscription')) ? <AdvisorDashboard /> : <PublicForm />; }

createRoot(document.getElementById('root')!).render(<App />);
