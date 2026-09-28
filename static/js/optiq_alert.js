/* OptiqFluent — pop-up in-app unifiée (remplace les alert() navigateur).
   Inclure AVANT les autres scripts de la page :
   <script src="/static/js/optiq_alert.js"></script>

   - optiqAlert(message, {title})   : modal dans la DA de l'app
   - optiqConfirm(message, {title, ok, cancel, danger}) : idem, avec deux
     issues ; rend une PROMESSE de booléen (`await optiqConfirm(...)`)
   - optiqAiCheck(data)             : détecte une réponse « IA indisponible »
     (clé absente, prompts non chargés…) → pop-up explicite, renvoie true
   - window.alert est redirigé vers optiqAlert (toutes les pages incluses). */
(function () {
  'use strict';

  function ensureStyles() {
    if (document.getElementById('optiq-alert-css')) return;
    const css = document.createElement('style');
    css.id = 'optiq-alert-css';
    css.textContent = `
      .oq-alert-overlay { position:fixed; inset:0; z-index:99999; display:flex;
        align-items:center; justify-content:center; background:rgba(15,23,42,.45);
        backdrop-filter:blur(4px); animation:oqFade .15s ease; }
      @keyframes oqFade { from { opacity:0 } to { opacity:1 } }
      .oq-alert-card { background:#fff; border-radius:18px; padding:26px 28px 22px;
        max-width:440px; width:calc(100% - 48px);
        box-shadow:0 0 0 1px rgba(0,0,0,.06), 0 24px 64px rgba(0,0,0,.30);
        font-family:'Segoe UI',system-ui,sans-serif; }
      .oq-alert-head { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
      .oq-alert-ico { width:40px; height:40px; border-radius:12px; flex-shrink:0;
        background:linear-gradient(145deg,#ec4899,#be185d); color:#fff;
        display:flex; align-items:center; justify-content:center; font-size:17px;
        box-shadow:0 4px 14px rgba(236,72,153,.35); }
      .oq-alert-title { font-size:1.02rem; font-weight:800; color:#0f172a; letter-spacing:-.2px; }
      .oq-alert-msg { color:#475569; font-size:.9rem; line-height:1.55; white-space:pre-wrap;
        word-break:break-word; max-height:40vh; overflow-y:auto; }
      .oq-alert-actions { display:flex; justify-content:flex-end; margin-top:18px; }
      .oq-alert-btn { border:none; border-radius:10px; padding:10px 24px; cursor:pointer;
        background:linear-gradient(135deg,#ec4899,#be185d); color:#fff; font-weight:700;
        font-size:.88rem; font-family:inherit; box-shadow:0 4px 14px rgba(236,72,153,.3); }
      .oq-alert-btn:hover { background:linear-gradient(135deg,#db2777,#9d174d); }
      .oq-alert-actions--2 { gap:10px; }
      .oq-alert-btn--ghost { background:#fff; color:#475569; box-shadow:none;
        border:1px solid #cbd5e1; }
      .oq-alert-btn--ghost:hover { background:#f1f5f9; color:#0f172a; }
      .oq-alert-ico--danger { background:linear-gradient(145deg,#f43f5e,#be123c);
        box-shadow:0 4px 14px rgba(244,63,94,.35); }
      .oq-alert-btn--danger { background:linear-gradient(135deg,#f43f5e,#be123c);
        box-shadow:0 4px 14px rgba(244,63,94,.3); }
      .oq-alert-btn--danger:hover { background:linear-gradient(135deg,#e11d48,#9f1239); }
    `;
    document.head.appendChild(css);
  }

  function optiqAlert(message, opts) {
    opts = opts || {};
    ensureStyles();
    const overlay = document.createElement('div');
    overlay.className = 'oq-alert-overlay';
    const card = document.createElement('div');
    card.className = 'oq-alert-card';
    const head = document.createElement('div');
    head.className = 'oq-alert-head';
    const ico = document.createElement('div');
    ico.className = 'oq-alert-ico';
    ico.innerHTML = opts.icon || '<i class="fa-solid fa-circle-info"></i>';
    const title = document.createElement('div');
    title.className = 'oq-alert-title';
    title.textContent = opts.title || 'OptiqFluent';
    head.appendChild(ico); head.appendChild(title);
    const msg = document.createElement('div');
    msg.className = 'oq-alert-msg';
    msg.textContent = String(message == null ? '' : message);
    const actions = document.createElement('div');
    actions.className = 'oq-alert-actions';
    const btn = document.createElement('button');
    btn.className = 'oq-alert-btn';
    btn.type = 'button';
    btn.textContent = 'OK';
    const close = () => overlay.remove();
    btn.addEventListener('click', close);
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
    });
    actions.appendChild(btn);
    card.appendChild(head); card.appendChild(msg); card.appendChild(actions);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    btn.focus();
  }

  /* Une CONFIRMATION, pas une alerte : deux issues, et l'appelant attend la
     réponse. `window.confirm` faisait sortir l'utilisateur de l'application —
     fenêtre du navigateur, styles du système, et un texte que rien ne traduit.

     ⚠️ Rend une PROMESSE : les appelants doivent l'attendre
     (`if (!(await optiqConfirm(...))) return;`). */
  function optiqConfirm(message, opts) {
    opts = opts || {};
    ensureStyles();
    const en = String(document.documentElement.lang || 'fr').toLowerCase().startsWith('en');
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'oq-alert-overlay';
      const card = document.createElement('div');
      card.className = 'oq-alert-card';

      const head = document.createElement('div');
      head.className = 'oq-alert-head';
      const ico = document.createElement('div');
      ico.className = 'oq-alert-ico' + (opts.danger ? ' oq-alert-ico--danger' : '');
      ico.innerHTML = opts.icon
        || (opts.danger ? '<i class="fa-solid fa-trash"></i>'
                        : '<i class="fa-solid fa-circle-question"></i>');
      const title = document.createElement('div');
      title.className = 'oq-alert-title';
      title.textContent = opts.title || (en ? 'Confirm' : 'Confirmer');
      head.appendChild(ico); head.appendChild(title);

      const msg = document.createElement('div');
      msg.className = 'oq-alert-msg';
      msg.textContent = String(message == null ? '' : message);

      const actions = document.createElement('div');
      actions.className = 'oq-alert-actions oq-alert-actions--2';
      const non = document.createElement('button');
      non.type = 'button';
      non.className = 'oq-alert-btn oq-alert-btn--ghost';
      non.textContent = opts.cancel || (en ? 'Cancel' : 'Annuler');
      const oui = document.createElement('button');
      oui.type = 'button';
      oui.className = 'oq-alert-btn' + (opts.danger ? ' oq-alert-btn--danger' : '');
      oui.textContent = opts.ok || (en ? 'Delete' : 'Supprimer');

      let fini = false;
      const clore = (reponse) => {
        if (fini) return;
        fini = true;
        document.removeEventListener('keydown', auClavier);
        overlay.remove();
        resolve(reponse);
      };
      function auClavier(e) {
        if (e.key === 'Escape') clore(false);
        if (e.key === 'Enter') clore(true);
      }
      non.addEventListener('click', () => clore(false));
      oui.addEventListener('click', () => clore(true));
      // Cliquer à côté ANNULE : sur une suppression, le geste ambigu ne vaut
      // jamais un oui.
      overlay.addEventListener('click', (e) => { if (e.target === overlay) clore(false); });
      document.addEventListener('keydown', auClavier);

      actions.appendChild(non); actions.appendChild(oui);
      card.appendChild(head); card.appendChild(msg); card.appendChild(actions);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
      // Le focus part sur ANNULER : une frappe distraite n'efface rien.
      non.focus();
    });
  }

  const NO_KEY_MARKERS = /clé ia non renseignée|clé openai manquante|no_openai_key|ai key not configured/i;
  const NO_AI_MARKERS = /prompts-unavailable|prompts non chargés|prompts not loaded|^no_ai$/i;

  /* Détecte une réponse d'endpoint IA en mode dégradé → pop-up explicite.
     Renvoie true si l'IA était indisponible (l'appelant peut alors décider
     d'afficher ou non le contenu de repli). */
  function optiqAiCheck(data) {
    if (!data || typeof data !== 'object') return false;
    const marker = String(data.source || data.error || '');
    const lang = (document.documentElement.lang || 'fr').toLowerCase();
    const en = lang.startsWith('en');
    if (data.ai_unavailable || NO_KEY_MARKERS.test(marker)) {
      optiqAlert(
        en ? 'The AI key (OpenAI) is not configured on this instance, so AI features are limited.\nAn administrator can add it in Settings → AI key.'
           : "La clé IA (OpenAI) n'est pas renseignée sur cette instance : les fonctions IA sont limitées.\nUn administrateur peut l'ajouter dans Paramètres → Clé IA.",
        { title: en ? 'AI unavailable' : 'IA indisponible',
          icon: '<i class="fa-solid fa-wand-magic-sparkles"></i>' });
      return true;
    }
    if (NO_AI_MARKERS.test(marker)) {
      optiqAlert(
        en ? 'AI features are unavailable on this instance (AI configuration missing). Contact your administrator.'
           : "Les fonctions IA sont indisponibles sur cette instance (configuration IA manquante). Contactez votre administrateur.",
        { title: en ? 'AI unavailable' : 'IA indisponible',
          icon: '<i class="fa-solid fa-wand-magic-sparkles"></i>' });
      return true;
    }
    return false;
  }

  window.optiqAlert = optiqAlert;
  window.optiqConfirm = optiqConfirm;
  window.optiqAiCheck = optiqAiCheck;
  window.alert = function (m) { optiqAlert(m); };
})();

/* ── Libellés des listes de la fiche activité ───────────────────────────
   window.CRUD_I18N est injecté par display_list.html ; softskills.js,
   aptitudes.js, savoirs.js, savoir_faires.js et constraints.js alertaient
   en dur, donc en français quelle que soit la langue. Un seul point de
   définition : ces fichiers partagent la portée globale, un `const` répété
   dans chacun lèverait une SyntaxError. */
window._CRUD_FR = {
  err: 'Erreur', need_description: 'Veuillez saisir une description.',
  need_hsc_fields: "Veuillez renseigner l'habileté et son niveau.",
  err_add: "Erreur lors de l'ajout.", err_update: 'Erreur lors de la modification.',
  err_delete: 'Erreur lors de la suppression.',
  err_refresh: 'Erreur lors du rafraîchissement de la liste.',
};
function _CR(cle) {
  return (window.CRUD_I18N && window.CRUD_I18N[cle]) || window._CRUD_FR[cle] || cle;
}
