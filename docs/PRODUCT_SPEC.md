# FINAB ABF Assistant — Cahier des charges MVP

## Objectif

Créer une application SaaS privée qui aide un conseiller financier à préparer un ABF Greatway à partir des informations fournies par un prospect/client via un formulaire intégré.

## Positionnement conformité

L'application est un assistant de préremplissage. Elle ne remplace pas le conseiller financier.

Flux obligatoire :

1. Prospect remplit le formulaire public du conseiller.
2. Les réponses arrivent dans le tableau de bord du conseiller.
3. L'IA prépare un brouillon ABF + notes + recommandations.
4. Le conseiller révise et finalise les calculs.
5. Le conseiller valide.
6. Le PDF ABF est généré.
7. Le client signe / confirme.
8. La proposition ivari vient après validation/signature.

## Exigence critique : préservation du PDF ABF

Le PDF final doit conserver exactement :

- la mise en page officielle Greatway ;
- les couleurs ;
- les polices et dimensions existantes autant que possible ;
- les 16 pages ;
- les textes légaux ;
- l'ordre des sections ;
- les champs et signatures.

Interdiction MVP :

- ne pas reconstruire l'ABF en HTML ;
- ne pas générer un PDF ressemblant ;
- ne pas modifier les pages officielles ;
- ne pas remplacer le document par un template maison.

Méthode retenue : remplir les champs AcroForm du fichier `ABF_VIERGE.pdf` officiel avec PyMuPDF/pypdf, puis sauvegarder une copie remplie.

## Modules MVP

### 1. Formulaire prospect intégré

Remplace Google Form pour rendre le produit vendable à d'autres conseillers.
Chaque conseiller aura un lien unique :

```text
/apply/{advisor_slug}
```

### 2. Tableau de bord conseiller

- Liste prospects
- Dossier client
- Données financières
- Préremplissage ABF
- Écran de révision conseiller
- Génération PDF

### 3. Moteur de mapping ABF

Convertit les réponses du formulaire vers les champs du PDF ABF.

### 4. Moteur IA contrôlé

Produit uniquement des brouillons :

- notes agent ;
- résumé client ;
- recommandations suggérées ;
- informations manquantes.

Le conseiller doit valider avant export final.

## Sources analysées

- ABF vierge Greatway : 16 pages, formulaire PDF remplissable, 360 champs détectés.
- ABF rempli Jocelina : exemple de style conformité.
- Proposition ivari : document post-ABF, non source principale au départ.
- Google Form actuel : base pour le nouveau formulaire intégré.
