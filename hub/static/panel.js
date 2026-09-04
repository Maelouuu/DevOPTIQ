/* ══════════════════════════════════════════════════════════════════════════
   MODULE — PANEL DE TESTS

   Trois choses : le carrousel circulaire des pages, les jauges de fiabilité,
   et le lancement d'une exécution avec son suivi.
   ══════════════════════════════════════════════════════════════════════════ */

const CIRC = 314;                 // 2πr pour r=50, la circonférence des jauges
const VISIBLES = 3;               // voisines rendues de chaque côté
const DOUX = matchMedia('(prefers-reduced-motion: reduce)').matches;

let pages = [];                   // catalogue reçu de l'instance
let ordre = 'fichier';
let filtre = '';
let actif = 0;

/* ── Utilitaires ────────────────────────────────────────────────────────── */
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v == null ? '' : v)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* Vert au-dessus de 90, ambre au-dessus de 70, rouge en dessous : on ne
   parle pas d'une note mais d'un niveau de confiance. */
function teinte(pct) {
  if (pct === null || pct === undefined) return '#a8a091';
  if (pct >= 90) return '#588b2f';
  if (pct >= 70) return '#c98a12';
  return '#c2452f';
}

function jauge(pct) {
  const p = (pct === null || pct === undefined) ? 0 : pct;
  return CIRC - (CIRC * p) / 100;
}

/* ── Carrousel ──────────────────────────────────────────────────────────── */
function trier() {
  const q = filtre.trim().toLowerCase();
  const copie = q
    ? pages.filter((p) => (p.titre + ' ' + (p.fichier || '') + ' ' +
                           (p.marqueur || '')).toLowerCase().includes(q))
    : pages.slice();
  if (ordre === 'fiabilite') {
    // Jamais joué en dernier : ce n'est pas une fragilité, c'est une absence.
    copie.sort((a, b) => {
      if (a.fiabilite === null) return 1;
      if (b.fiabilite === null) return -1;
      return a.fiabilite - b.fiabilite;
    });
  } else if (ordre === 'taille') {
    copie.sort((a, b) => b.total - a.total);
  }
  return copie;
}

let triees = [];

function dessiner() {
  const scene = $('#car-scene');
  triees = trier();
  scene.innerHTML = '';

  if (!triees.length) {
    scene.innerHTML = '<p class="car-vide">Aucune page ne porte ce mot.</p>';
    $('#car-compteur').textContent = '';
    return;
  }

  triees.forEach((p, i) => {
    const a = document.createElement('a');
    a.className = 'car-carte';
    a.href = '/panel/' + encodeURIComponent(p.slug);
    a.setAttribute('role', 'option');
    a.dataset.i = i;

    const pct = p.fiabilite;
    const couleur = teinte(pct);
    a.innerHTML = `
      <span class="cc-rang">${String(i + 1).padStart(2, '0')} / ${triees.length}</span>
      <h3 class="cc-titre">${esc(p.titre)}</h3>
      <code class="cc-fichier">${esc(p.fichier || '')}</code>
      <div class="cc-jauge">
        <svg viewBox="0 0 120 120">
          <circle class="j-fond" cx="60" cy="60" r="50"></circle>
          <circle class="j-arc" cx="60" cy="60" r="50"
                  style="stroke:${couleur}" data-off="${jauge(pct)}"></circle>
        </svg>
        <div class="cc-val">
          ${pct === null
            ? '<i>jamais joué</i>'
            : '<b>' + pct + '<span>%</span></b><span>fiabilité</span>'}
        </div>
      </div>
      <div class="cc-chiffres">
        <span class="cc-p ${p.verts ? 'ok' : 'neutre'}"><i></i>${p.verts} vert${p.verts > 1 ? 's' : ''}</span>
        <span class="cc-p ${p.rouges ? 'ko' : 'neutre'}"><i></i>${p.rouges} rouge${p.rouges > 1 ? 's' : ''}</span>
        <span class="cc-p neutre">${p.total} cas</span>
      </div>
      <span class="cc-ouvrir">Voir le détail →</span>`;
    scene.appendChild(a);
  });

  /* Les arcs partent tous à zéro et se remplissent à la frame suivante :
     posés directement à leur valeur, ils apparaîtraient sans transition. */
  requestAnimationFrame(() => {
    scene.querySelectorAll('.j-arc[data-off]').forEach((arc) => {
      arc.style.strokeDashoffset = arc.dataset.off;
    });
  });

  placer();
}

/* Chaque carte est posée sur l'anneau selon son écart à la carte active. */
function placer() {
  const cartes = [...document.querySelectorAll('.car-carte')];
  cartes.forEach((c) => {
    const d = Number(c.dataset.i) - actif;
    const abs = Math.abs(d);
    if (abs > VISIBLES) { c.hidden = true; return; }
    c.hidden = false;
    const t = `translateX(${d * 172}px) translateZ(${-abs * 132}px)`
            + ` rotateY(${-d * 31}deg) scale(${1 - abs * 0.05})`;
    c.style.transform = t;
    c.style.opacity = abs === 0 ? 1 : Math.max(0, 0.8 - abs * 0.22);
    c.style.zIndex = String(20 - abs);
    if (abs === 0) c.setAttribute('data-actif', '');
    else c.removeAttribute('data-actif');
    c.tabIndex = abs === 0 ? 0 : -1;
  });

  const p = triees[actif];
  const compteur = $('#car-compteur');
  if (compteur && p) {
    compteur.textContent = `${actif + 1} / ${triees.length} · ${p.joues} cas déjà exécutés sur ${p.total}`;
  }
}

function aller(delta) {
  if (!triees.length) return;
  actif = Math.min(triees.length - 1, Math.max(0, actif + delta));
  placer();
}

/* ── Jauge globale ──────────────────────────────────────────────────────── */
function majGlobale() {
  const joues = pages.reduce((s, p) => s + p.joues, 0);
  const verts = pages.reduce((s, p) => s + p.verts, 0);
  const pct = joues ? Math.round((100 * verts) / joues) : null;
  const arc = $('#jauge-globale-arc');
  const val = $('#jauge-globale-val');
  const leg = $('#serre-leg');
  if (!arc) return;
  arc.style.stroke = teinte(pct);
  arc.style.strokeDashoffset = jauge(pct);
  val.textContent = pct === null ? '—' : pct + '%';
  leg.textContent = joues
    ? `${verts} verts sur ${joues} cas exécutés`
    : "Aucun cas exécuté pour l'instant — lancez la suite";
}

/* ── Chargement du catalogue ────────────────────────────────────────────── */
async function charger() {
  const vide = $('#car-vide');
  try {
    const r = await fetch('/api/panel/pages', { credentials: 'same-origin' });
    const d = await r.json();
    if (d.erreur) {
      if (vide) vide.textContent = "L'instance ne répond pas — réessayez dans un instant.";
      return;
    }
    pages = d.pages || [];
    if (!pages.length) {
      if (vide) vide.textContent = 'Aucune page de tests trouvée sur l’instance.';
      return;
    }
    actif = 0;
    dessiner();
    majGlobale();
  } catch (_) {
    if (vide) vide.textContent = 'Chargement impossible.';
  }
}

/* ── Lancement et suivi ─────────────────────────────────────────────────── */
let suivi = null;
let suiviFin = 0;      // au-delà, on cesse d'interroger

function afficherCourse(txt, pct) {
  const bloc = $('#course');
  bloc.hidden = false;
  $('#course-txt').textContent = txt;
  $('#course-jauge').style.width = (pct === null ? 8 : pct) + '%';
}

async function suivre(runId) {
  clearTimeout(suivi);
  try {
    const r = await fetch('/api/panel/run/' + runId, { credentials: 'same-origin' });
    const d = await r.json();
    if (d.status === 'running' || d.status === 'unknown') {
      /* Une instance recyclée en pleine exécution laisse le run « running »
         pour toujours : on cesse d'interroger plutôt que de tourner sans fin. */
      if (Date.now() > suiviFin) {
        afficherCourse("Toujours en cours après 25 min — voyez le panel d'origine.", null);
        return;
      }
      afficherCourse(
        d.total ? `Exécution en cours — ${d.passed} / ${d.total} au vert` : 'Exécution en cours…',
        d.total ? Math.round((100 * d.passed) / d.total) : null);
      suivi = setTimeout(() => suivre(runId), 2500);
      return;
    }
    afficherCourse(
      `Terminé — ${d.passed} / ${d.total} au vert (${d.pct}%)`,
      d.pct);
    // Les scores viennent de changer : le carrousel se redessine, la page de
    // détail se recharge (ses cas sont rendus côté serveur).
    if (scene) charger();
    else setTimeout(() => location.reload(), 1200);
  } catch (_) {
    afficherCourse('Suivi interrompu — rechargez pour voir le résultat.', null);
  }
}

async function lancer(portee, bouton) {
  const libelle = bouton ? bouton.innerHTML : '';
  if (bouton) { bouton.disabled = true; bouton.textContent = 'Démarrage…'; }
  afficherCourse('Demande envoyée à l’instance…', null);
  try {
    const r = await fetch('/api/panel/lancer', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portee }),
    });
    const d = await r.json();
    if (!d.ok) { afficherCourse(d.message || 'Lancement refusé.', null); return; }
    suiviFin = Date.now() + 25 * 60 * 1000;
    suivre(d.run_id);
  } catch (_) {
    afficherCourse('Le hub n’a pas pu joindre l’instance.', null);
  } finally {
    if (bouton) { bouton.disabled = false; bouton.innerHTML = libelle; }
  }
}

/* ── Câblage ────────────────────────────────────────────────────────────── */
$('#btn-tout')?.addEventListener('click', (e) => lancer('all', e.currentTarget));
$('#btn-recharger')?.addEventListener('click', charger);
$('#car-prec')?.addEventListener('click', () => aller(-1));
$('#car-suiv')?.addEventListener('click', () => aller(1));

$('#tri-q')?.addEventListener('input', (e) => {
  filtre = e.target.value;
  actif = 0;
  dessiner();
});

document.querySelectorAll('.tri-b').forEach((b) => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.tri-b').forEach((x) => x.classList.remove('actif'));
    b.classList.add('actif');
    ordre = b.dataset.tri;
    actif = 0;
    dessiner();
  });
});

const scene = $('#car-scene');
if (scene) {
  scene.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); aller(-1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); aller(1); }
    if (e.key === 'Enter' && triees[actif]) {
      location.href = '/panel/' + encodeURIComponent(triees[actif].slug);
    }
  });

  /* On ne capte QUE le geste horizontal. Confisquer la molette verticale
     empêcherait de faire défiler la page dès que le pointeur passe sur
     l'anneau — et un cran par geste, sinon soixante-dix cartes défilent d'un
     coup et on perd le fil. */
  let verrou = false;
  scene.addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return;
    e.preventDefault();
    if (verrou) return;
    verrou = true;
    aller(e.deltaX > 0 ? 1 : -1);
    setTimeout(() => { verrou = false; }, DOUX ? 60 : 260);
  }, { passive: false });

  /* Glisser : un cran tous les 90 px parcourus. */
  let depart = null, dernier = 0;
  scene.addEventListener('pointerdown', (e) => { depart = e.clientX; dernier = 0; });
  scene.addEventListener('pointermove', (e) => {
    if (depart === null) return;
    const d = e.clientX - depart;
    const crans = Math.trunc(d / 90);
    if (crans !== dernier) { aller(dernier - crans); dernier = crans; }
  });
  const relacher = () => { depart = null; };
  scene.addEventListener('pointerup', relacher);
  scene.addEventListener('pointercancel', relacher);
  scene.addEventListener('pointerleave', relacher);

  /* Cliquer une voisine la ramène au centre plutôt que d'ouvrir sa page. */
  scene.addEventListener('click', (e) => {
    const carte = e.target.closest('.car-carte');
    if (!carte) return;
    const i = Number(carte.dataset.i);
    if (i !== actif) { e.preventDefault(); actif = i; placer(); }
  });
}

/* ── Page de détail ─────────────────────────────────────────────────────── */
const btnPage = $('#btn-page');
if (btnPage) {
  btnPage.addEventListener('click', (e) =>
    lancer('page:' + btnPage.dataset.slug, e.currentTarget));
  const arc = $('#detail-arc');
  if (arc) {
    const pct = window.PAGE_FIABILITE;
    arc.style.stroke = teinte(pct);
    requestAnimationFrame(() => { arc.style.strokeDashoffset = jauge(pct); });
  }
}

if (scene) charger();
