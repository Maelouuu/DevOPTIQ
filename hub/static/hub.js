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


/* ══ Page Tests ══════════════════════════════════════════════════════════
   La suite tourne dans GitHub Actions : on déclenche, puis on suit. Tant
   qu'une exécution n'est pas terminée, on recharge la liste toutes les 12 s
   — et seulement dans ce cas, pour ne pas taper l'API pour rien. */

const CLASSES_ETAT = {
  'succès': 'etat-en-ligne', 'échec': 'etat-injoignable', 'en cours': 'etat-degrade',
  'en attente': 'etat-degrade', 'annulé': 'etat-en-erreur', 'expiré': 'etat-en-erreur',
};

function quand(iso) {
  if (!iso) return '';
  const d = new Date(iso), m = Math.floor((Date.now() - d) / 60000);
  if (m < 1) return "à l'instant";
  if (m < 60) return 'il y a ' + m + ' min';
  if (m < 1440) return 'il y a ' + Math.floor(m / 60) + ' h';
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function _esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

let _minuterieRuns = null;

async function chargerExecutions() {
  const corps = document.getElementById('corps-runs');
  const note = document.getElementById('note-runs');
  if (!corps) return;
  try {
    const r = await fetch('/api/tests/executions', { credentials: 'same-origin' });
    const d = await r.json();

    if (d.erreur === 'workflow_absent') {
      corps.innerHTML = '<tr><td colspan="5" class="muet">Le workflow tests.yml n\'existe pas encore sur GitHub — il part au prochain push.</td></tr>';
      return;
    }
    if (d.erreur) {
      corps.innerHTML = '<tr><td colspan="5" class="muet">Exécutions illisibles (' + _esc(d.erreur) + ').</td></tr>';
      if (note) note.textContent = "Dépôt privé : posez le secret HUB_GITHUB_TOKEN pour que le hub puisse lire les exécutions.";
      return;
    }
    if (!d.runs.length) {
      corps.innerHTML = '<tr><td colspan="5" class="muet">Aucune exécution pour l\'instant.</td></tr>';
      return;
    }

    corps.innerHTML = d.runs.map(x => `
      <tr>
        <td><b>#${_esc(x.numero)}</b><span class="sous-ligne">${_esc(x.titre)}</span></td>
        <td><span class="pill mini ${CLASSES_ETAT[x.etat] || ''}"><i></i>${_esc(x.etat)}</span></td>
        <td>${_esc(x.declenche === 'workflow_dispatch' ? 'à la main' : x.declenche)}
            <span class="sous-ligne"><code>${_esc(x.branche)}</code> · ${_esc(x.commit)}</span></td>
        <td>${_esc(quand(x.fin || x.debut))}</td>
        <td class="colonne-action"><a class="btn-sec" href="${_esc(x.url)}" target="_blank" rel="noopener">Journal</a></td>
      </tr>`).join('');

    // Une exécution en cours ? On repasse dans 12 s. Sinon on s'arrête.
    const enCours = d.runs.some(x => x.statut !== 'completed');
    clearTimeout(_minuterieRuns);
    if (enCours) _minuterieRuns = setTimeout(chargerExecutions, 12000);
  } catch (_) {
    corps.innerHTML = '<tr><td colspan="5" class="muet">Chargement impossible.</td></tr>';
  }
}

document.getElementById('btn-recharger')?.addEventListener('click', chargerExecutions);

document.getElementById('btn-lancer')?.addEventListener('click', async (ev) => {
  const btn = ev.currentTarget;
  const retour = document.getElementById('retour');
  const filtre = (document.getElementById('filtre') || {}).value || '';
  btn.disabled = true;
  const libelle = btn.textContent;
  btn.textContent = 'Envoi…';
  try {
    const r = await fetch('/api/tests/lancer', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filtre }),
    });
    const d = await r.json();
    retour.hidden = false;
    retour.className = 'lanceur-retour ' + (d.ok ? 'ok' : 'ko');
    retour.textContent = d.message;
    if (d.ok) setTimeout(chargerExecutions, 3000);
  } catch (_) {
    retour.hidden = false;
    retour.className = 'lanceur-retour ko';
    retour.textContent = 'Le hub n\'a pas pu joindre GitHub.';
  } finally {
    btn.disabled = false;
    btn.textContent = libelle;
  }
});

if (document.getElementById('corps-runs')) chargerExecutions();


/* ══ Secteurs : inclinaison vers le curseur ══════════════════════════════
   La carte pivote de quelques degrés seulement — au-delà, le texte se
   déforme et devient pénible à lire. Coupé si l'utilisateur demande moins
   d'animations, et sur les écrans tactiles (aucun survol). */
(function () {
  const cartes = document.querySelectorAll('.secteur');
  if (!cartes.length) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!matchMedia('(hover: hover)').matches) return;

  const AMPLITUDE = 7;   // degrés

  cartes.forEach(carte => {
    carte.addEventListener('pointermove', ev => {
      const r = carte.getBoundingClientRect();
      const x = (ev.clientX - r.left) / r.width - .5;
      const y = (ev.clientY - r.top) / r.height - .5;
      carte.style.transform =
        'rotateY(' + (x * AMPLITUDE) + 'deg) rotateX(' + (-y * AMPLITUDE) + 'deg) translateY(-4px)';
    });
    carte.addEventListener('pointerleave', () => { carte.style.transform = ''; });
  });
})();
