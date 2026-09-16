/* Optiq Hub — état des instances en direct et copie des commandes. */

/* Même normalisation que le gabarit : « en ligne » → etat-en-ligne,
   « dégradé » → etat-degrade. Sans ça, une classe posée par le JS ne
   correspondrait pas à celle du rendu serveur. */
function classeEtat(libelle) {
  return 'etat-' + (libelle || 'inconnu')
    .replace(/\s+/g, '-')
    .replace(/é/g, 'e');
}

function peindre(etats) {
  let enLigne = 0;
  document.querySelectorAll('.carte-instance').forEach(carte => {
    const e = etats[carte.dataset.cle];
    if (!e) return;
    if (e.etat === 'en ligne') enLigne++;

    const pastille = carte.querySelector('[data-role="pastille"]');
    pastille.className = 'pastille ' + classeEtat(e.etat);
    pastille.querySelector('[data-role="libelle"]').textContent = e.etat;

    const latence = carte.querySelector('[data-role="latence"]');
    latence.textContent = e.ms ? e.ms + ' ms' : (e.code ? 'HTTP ' + e.code : '');
    latence.title = e.code ? 'Réponse HTTP ' + e.code : 'Aucune réponse';
  });
  const c = document.getElementById('c-ligne');
  if (c) c.textContent = enLigne;
}

async function rafraichir(force) {
  const btn = document.getElementById('btn-refresh');
  if (btn) btn.classList.add('tourne');
  try {
    const r = await fetch('/api/etat' + (force ? '?force=1' : ''), { credentials: 'same-origin' });
    if (r.ok) peindre(await r.json());
  } catch (_) {
    /* Le hub reste lisible même si la sonde échoue : on garde l'affichage. */
  } finally {
    if (btn) btn.classList.remove('tourne');
  }
}

document.getElementById('btn-refresh')?.addEventListener('click', () => rafraichir(true));

/* Premier rendu : le serveur a déjà sondé. On ne repasse qu'ensuite, et
   uniquement quand l'onglet est visible — inutile de sonder en arrière-plan. */
peindre(window.__ETATS__ || {});
setInterval(() => { if (document.visibilityState === 'visible') rafraichir(false); }, 60000);

/* ── Copie d'une commande ───────────────────────────────────────── */
document.querySelectorAll('.btn-copie').forEach(btn => {
  btn.addEventListener('click', async () => {
    const texte = btn.dataset.cmd || '';
    try {
      await navigator.clipboard.writeText(texte);
    } catch (_) {
      // Contexte sans presse-papiers (http, permission refusée) : on
      // sélectionne le texte pour que Ctrl+C reste possible.
      const code = btn.closest('.co-cmd').querySelector('code');
      const sel = window.getSelection();
      const plage = document.createRange();
      plage.selectNodeContents(code);
      sel.removeAllRanges();
      sel.addRange(plage);
      return;
    }
    btn.classList.add('fait');
    btn.title = 'Copié';
    setTimeout(() => { btn.classList.remove('fait'); btn.title = 'Copier la commande'; }, 1600);
  });
});

/* Ancres : défilement doux sans casser l'historique. */
document.querySelectorAll('.nav-ancres a').forEach(a => {
  a.addEventListener('click', ev => {
    const cible = document.querySelector(a.getAttribute('href'));
    if (!cible) return;
    ev.preventDefault();
    cible.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history.replaceState(null, '', a.getAttribute('href'));
  });
});


/* ══ L'arbre : la branche du nœud survolé s'allume ═══════════════════════
   Le lien entre un nœud et le tronc doit se voir : on marque la branche
   correspondante et on estompe les autres. La couleur vive vient du nœud
   lui-même, pour rester cohérent avec sa section. */
(function () {
  const arbre = document.querySelector('.arbre');
  if (!arbre) return;

  arbre.querySelectorAll('.noeud[data-br]').forEach(noeud => {
    const branche = arbre.querySelector('.br-' + noeud.dataset.br);
    if (!branche) return;

    const allumer = () => {
      arbre.dataset.actif = noeud.dataset.br;
      arbre.style.setProperty('--acc-vif', getComputedStyle(noeud).getPropertyValue('--a').trim());
      branche.classList.add('vive');
    };
    const eteindre = () => {
      delete arbre.dataset.actif;
      branche.classList.remove('vive');
    };
    noeud.addEventListener('pointerenter', allumer);
    noeud.addEventListener('pointerleave', eteindre);
    noeud.addEventListener('focus', allumer);
    noeud.addEventListener('blur', eteindre);
  });
})();
