# Mémoire de 3ᵉ année — BUT Informatique (Maël Girardin)

Mémoire d'alternance **« D'une maquette à un produit »**, charte DevOPTIQ
(rose `#ec4899` / vert `#22c55e` / blanc).

## Fichiers

| Fichier | Rôle |
|---|---|
| `memoire_3eme_annee.html` | **La source** du mémoire (à ouvrir dans un navigateur). |
| `editeur.html` | **Petit éditeur** pour modifier le mémoire sans toucher au HTML. |
| `memoire_3eme_annee.pdf` | Aperçu PDF (régénéré ponctuellement). |

## ✏️ L'éditeur (`editeur.html`)

Ouvre `editeur.html` dans **Chrome ou Edge**, puis clique **« Ouvrir le mémoire »**
et choisis `memoire_3eme_annee.html`. Tu peux ensuite :

- **Texte** : cliquer dans le texte et écrire ; gras / italique / souligné ; alignement.
- **Taille** : sélectionner du texte puis `A−` / `A+` ou saisir une taille en pixels.
- **Couleur** : sélectionner du texte, choisir une couleur (ou la **Pipette 🎨** pour
  capturer une couleur n'importe où à l'écran), ou un des pastilles rose/vert.
- **Image / capture** : bouton **🖼 Insérer** → choisir un fichier. En **Mode objet**,
  sélectionne d'abord un cadre vert « visuel à insérer » (ex. dans la partie comparaison)
  puis insère : l'image remplace le cadre. Une image sélectionnée se redimensionne avec le curseur.
- **Déplacer un bloc** : active **✋ Mode objet**, clique un bloc (titre, paragraphe, image…),
  puis `▲`/`▼` pour le réordonner, ou glisse-le pour l'ajuster, `🗑` pour le supprimer.
- **Ajouter une page** : bouton **➕ Page** → insère une nouvelle page A4 après la page courante.
- **Aperçu A4** : bouton **📄 Aperçu A4** → affiche le document découpé en **pages A4 identiques**
  (pagination fidèle via Paged.js) ; bouton Imprimer/PDF depuis cet aperçu. La vue d'édition, elle,
  reste un flux continu (plus pratique pour écrire) — les pages égales sont l'aperçu et le PDF.
- **Enregistrer** : 💾 **écrase directement le fichier ouvert** (Chrome/Edge, via la File System
  Access API). À la 1ʳᵉ fois le navigateur demande l'autorisation d'écriture. Si l'API n'est pas
  disponible, l'éditeur propose un emplacement, puis retombe sur un téléchargement classique.
- **Imprimer / PDF** : 🖨 ouvre l'impression du navigateur → **pages A4 uniformes**.

> L'éditeur garde toute la mise en forme HTML (charte, schémas, code) — il ne fait
> qu'ajouter une couche d'édition par-dessus.

## Obtenir le PDF final

Le rendu optimal s'obtient depuis **Chrome / Edge** : bouton **🖨 Imprimer / PDF**
de l'éditeur (ou `Ctrl+P` sur le mémoire) → **Enregistrer au format PDF**, format
**A4**, marges **par défaut**, cocher **Graphiques d'arrière-plan**.

## Longueur

≈ **32 pages hors annexes** (35 au total). Les pages sont désormais **toutes au format
A4** et remplies de façon homogène (plus de pages à moitié vides).

## Plan

- **Partie I** — Environnement professionnel (A.F.D.E.C, méthode OPTIQ) et basculement maquette → produit.
- **Partie II** — Ampleur de l'app + **4 cas commentés** : ① éditeur OptiqCarto (remplace VSDX),
  ② multi-entités, ③ stockage cloud, ④ « désirable et increvable » (visuel + IA). Schémas Figures 1 & 2.
- **Partie III** — Analyse critique (arbitrage fonctionnel/visuel vs sécurité), bénéfices, évolution.
- **Annexes** — glossaire, modules, pile technique, feuille de temps, **schéma BDD (Figure 3)**.

## ⚠️ Champs à compléter (encadrés roses « ◆ à compléter »)

1. Remerciements nominatifs (tuteur IUT, Inde/investisseurs).
2. Formalisation du passage *stagiaire → associé*.
3. Dates / rythme de l'alternance + tuteur pédagogique.
4. Anecdote sur le relationnel à l'international (anglais / Inde).
5. Feuille de temps (annexe A4).
6. Captures d'écran (encadrés verts « visuel à insérer ») — à faire via l'éditeur.

## Note d'honnêteté sur le code

Le code **« APRÈS / produit »** est tiré du dépôt (réel). Le code **« AVANT / maquette »**
est une reconstitution représentative de l'approche initiale (l'historique Git complet de
cette période n'est pas dans ce dépôt). À remplacer par tes anciens extraits si tu les as.
