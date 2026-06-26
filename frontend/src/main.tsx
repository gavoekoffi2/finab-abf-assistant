import React from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle2, FileText, ShieldCheck, Users, Wand2 } from 'lucide-react';
import './styles.css';

const fields = [
  'Nom légal', 'Prénoms', 'Date de naissance', 'Téléphone', 'Courriel', 'Adresse',
  'Profession', 'Revenu annuel', 'Total des biens', 'Total des dettes', 'Budget mensuel',
  'Objectifs prioritaires'
];

function App() {
  return (
    <main className="page">
      <aside className="sidebar">
        <div className="brand"><div className="mark">F</div><div><strong>FINAB</strong><span>ABF Assistant</span></div></div>
        <nav>
          <a className="active"><Users size={18}/> Prospects</a>
          <a><FileText size={18}/> Dossiers ABF</a>
          <a><Wand2 size={18}/> Préremplissage IA</a>
          <a><ShieldCheck size={18}/> Révision conseiller</a>
        </nav>
      </aside>
      <section className="content">
        <header className="hero">
          <div>
            <p className="eyebrow">MVP vendable à plusieurs conseillers</p>
            <h1>Formulaire prospect intégré → ABF Greatway prérempli</h1>
            <p>L’IA prépare le brouillon, mais le conseiller financier finalise les calculs avant export PDF.</p>
          </div>
          <div className="status"><CheckCircle2/> PDF officiel préservé<br/><span>16 pages, formulaire AcroForm, mise en page intacte</span></div>
        </header>

        <div className="grid">
          <section className="card wide">
            <div className="section-title"><span>01</span><h2>Formulaire prospect public</h2></div>
            <p className="muted">Chaque conseiller aura un lien unique à envoyer au prospect. Les réponses remplacent Google Form et alimentent directement le dossier ABF.</p>
            <div className="form-grid">
              {fields.map((f) => <label key={f}>{f}<input placeholder={f}/></label>)}
            </div>
            <button>Simuler la sauvegarde du prospect</button>
          </section>

          <section className="card">
            <div className="section-title"><span>02</span><h2>Brouillon IA</h2></div>
            <ul className="checks">
              <li>Résumé client</li>
              <li>Notes agent style FINAB</li>
              <li>3 recommandations brouillon</li>
              <li>Infos manquantes</li>
            </ul>
          </section>

          <section className="card">
            <div className="section-title"><span>03</span><h2>Révision conseiller</h2></div>
            <p className="warning">Export final bloqué tant que le conseiller n’a pas validé les calculs, budgets et recommandations.</p>
            <label>Couverture finale validée<input placeholder="ex: 858 000 $"/></label>
            <label>Budget client validé<input placeholder="ex: 100 $ / mois"/></label>
            <button className="secondary">Valider comme conseiller</button>
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
