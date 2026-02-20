/* ============================================================
   OPTIQ CHATBOT — Frontend JS
   Gestion de la session, conversation, et brouillon OPTIQ
   ============================================================ */

(function () {
  'use strict';

  // ── État global ────────────────────────────────────────────
  let currentActId        = null;
  let storedContext       = null;   // contexte de l'activité en cours
  let conversationHistory = [];     // [{role, content}, ...]
  let isWaiting           = false;
  let lastDraftTasks      = [];
  let _fetchController    = null;   // AbortController pour annuler les fetches en vol

  // ── Références DOM ─────────────────────────────────────────
  const overlay      = () => document.getElementById('chatbot-overlay');
  const msgContainer = () => document.getElementById('chatbot-messages');
  const inputEl      = () => document.getElementById('chatbot-input');
  const sendBtn      = () => document.getElementById('chatbot-send-btn');
  const headerTitle  = () => document.getElementById('chatbot-header-title');
  const headerSub    = () => document.getElementById('chatbot-header-subtitle');
  const injectBtn    = () => document.getElementById('chatbot-inject-btn');
  const injectCount  = () => document.getElementById('chatbot-inject-count');

  // ── Ouverture du chatbot ───────────────────────────────────
  window.openChatbotFromBtn = function (btn) {
    const actId   = btn.dataset.activityId;
    const actName = btn.dataset.activityName;

    // Annuler tout fetch en cours (race condition si on change d'activité rapidement)
    if (_fetchController) _fetchController.abort();
    _fetchController = new AbortController();
    const signal = _fetchController.signal;

    currentActId        = actId;
    storedContext       = null;
    conversationHistory = [];

    // Mettre à jour le header immédiatement
    headerTitle().textContent = `Assistant OPTIQ — ${actName}`;
    headerSub().textContent   = 'Chargement du contexte…';

    // Réinitialiser l'UI
    _clearMessages();
    _clearDraft();

    // Ouvrir l'overlay
    overlay().classList.add('active');
    document.body.style.overflow = 'hidden';

    // Afficher un indicateur de chargement dans la conversation
    const loadingEl = _showTyping();

    // Récupérer le contexte complet depuis la DB
    fetch(`/api/chatbot/activity/${actId}/context`, { signal })
      .then(r => {
        if (!r.ok) throw new Error(`Erreur ${r.status}`);
        return r.json();
      })
      .then(activityContext => {
        // Vérifier que l'activité n'a pas changé entre temps
        if (currentActId !== actId) return;

        _removeTyping(loadingEl);
        storedContext = activityContext;

        // Mettre à jour le sous-titre
        const nbTasks   = activityContext.tasks   ? activityContext.tasks.length   : 0;
        const nbSavoirs = activityContext.savoirs  ? activityContext.savoirs.length  : 0;
        const nbHSC     = activityContext.hsc      ? activityContext.hsc.length      : 0;
        headerSub().textContent =
          `${nbTasks} tâche(s) existante(s) · ${nbSavoirs} savoir(s) · ${nbHSC} HSC chargé(s)`;

        // Message d'amorce automatique
        _sendToBot('Bonjour, je veux définir les tâches de cette activité.');
      })
      .catch(err => {
        if (err.name === 'AbortError') return; // fetch annulé volontairement
        _removeTyping(loadingEl);
        _appendBotMessage('❌ Impossible de charger le contexte de l\'activité : ' + err.message);
        headerSub().textContent = 'Erreur de chargement';
      });
  };

  // ── Fermeture ──────────────────────────────────────────────
  window.closeChatbot = function () {
    overlay().classList.remove('active');
    document.body.style.overflow = '';
  };

  // Fermer en cliquant sur l'overlay
  document.addEventListener('DOMContentLoaded', function () {
    const ov = overlay();
    if (!ov) return;
    ov.addEventListener('click', function (e) {
      if (e.target === ov) closeChatbot();
    });

    // Envoi avec Entrée (Shift+Entrée = nouvelle ligne)
    const inp = inputEl();
    if (inp) {
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }
  });

  // ── Envoi du message utilisateur ──────────────────────────
  window.sendMessage = function () {
    const inp = inputEl();
    if (!inp || isWaiting) return;
    const text = inp.value.trim();
    if (!text) return;

    inp.value = '';
    inp.style.height = 'auto';
    _appendUserMessage(text);
    _sendToBot(text);
  };

  // ── Clic sur une suggestion de question ───────────────────
  window.clickSuggestedQuestion = function (text) {
    const inp = inputEl();
    if (inp) inp.value = text;
    sendMessage();
  };

  // ── Injection des tâches dans la DB ───────────────────────
  window.injectTasks = function () {
    if (!currentActId || lastDraftTasks.length === 0) return;

    const btn = injectBtn();
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Injection en cours…';

    const validTasks = lastDraftTasks
      .filter(t => !t.flags?.out_of_scope)
      .map(t => ({
        label: t.label,
        tools: t.tools || [],
        outgoing_link: (t.outgoing_link && t.outgoing_link.data_name)
          ? t.outgoing_link
          : undefined,
      }));

    fetch('/api/chatbot/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        activity_id: parseInt(currentActId),
        tasks: validTasks,
      }),
    })
      .then(r => r.json().then(data => ({ ok: r.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          throw new Error(data.error || 'Échec de l\'injection');
        }
        btn.innerHTML = `<i class="fa-solid fa-check"></i> ${data.count} tâche(s) ajoutée(s) !`;
        btn.style.background = 'linear-gradient(135deg, #667eea, #8b5cf6)';

        // Rafraîchir la section tâches de l'activité
        setTimeout(() => {
          if (typeof loadTasksForActivity === 'function') {
            loadTasksForActivity(currentActId);
          } else {
            location.reload();
          }
        }, 800);

        setTimeout(() => closeChatbot(), 1600);
      })
      .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Erreur — réessayer';
        console.error('Inject error:', err);
      });
  };

  // ── Appel API chat (stateless) ────────────────────────────
  function _sendToBot(message) {
    if (!storedContext) return;
    isWaiting = true;
    _setInputEnabled(false);
    const typingEl = _showTyping();

    fetch('/api/chatbot/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        activity: storedContext,
        history:  conversationHistory.slice(-14),
        message:  message,
      }),
    })
      .then(r => r.json())
      .then(data => {
        _removeTyping(typingEl);
        if (data.error) {
          _appendBotMessage('❌ ' + data.error);
        } else {
          // Mettre à jour l'historique local
          conversationHistory.push({ role: 'user',      content: message });
          conversationHistory.push({ role: 'assistant', content: data.assistant_message || '' });
          _appendBotMessage(data.assistant_message);
          _renderDraft(data);
        }
      })
      .catch(err => {
        _removeTyping(typingEl);
        _appendBotMessage('❌ Erreur réseau : ' + err.message);
      })
      .finally(() => {
        isWaiting = false;
        _setInputEnabled(true);
        inputEl()?.focus();
      });
  }

  // ── Rendu des messages ─────────────────────────────────────
  function _appendBotMessage(text) {
    const el = document.createElement('div');
    el.className = 'cb-msg bot';
    el.innerHTML = _mdToHtml(text);
    msgContainer().appendChild(el);
    _scrollToBottom();
  }

  function _appendUserMessage(text) {
    const el = document.createElement('div');
    el.className = 'cb-msg user';
    el.textContent = text;
    msgContainer().appendChild(el);
    _scrollToBottom();
  }

  function _showTyping() {
    const el = document.createElement('div');
    el.className = 'cb-typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    msgContainer().appendChild(el);
    _scrollToBottom();
    return el;
  }

  function _removeTyping(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function _clearMessages() {
    const mc = msgContainer();
    if (mc) mc.innerHTML = '';
  }

  function _scrollToBottom() {
    const mc = msgContainer();
    if (mc) mc.scrollTop = mc.scrollHeight;
  }

  // ── Rendu du brouillon OPTIQ (panneau droit) ───────────────
  function _renderDraft(data) {
    const tasks   = data.tasks          || [];
    const checks  = data.quality_checks || [];
    const qsts    = data.next_questions  || [];
    const branches= data.branches        || [];
    const status  = data.status          || 'need_more_info';

    lastDraftTasks = tasks;

    _renderTasks(tasks);
    _renderChecks(checks);
    _renderQuestions(qsts);
    _renderBranches(branches);
    _updateInjectBtn(tasks, status);
  }

  function _renderTasks(tasks) {
    const container = document.getElementById('cb-draft-tasks-body');
    if (!container) return;

    if (!tasks || tasks.length === 0) {
      container.innerHTML = '<p class="cb-empty-hint">Aucune tâche encore définie.</p>';
      return;
    }

    const ul = document.createElement('ul');
    ul.className = 'cb-tasks-list';

    tasks.forEach((task, i) => {
      const flags = task.flags || {};
      const hasIssue = flags.too_detailed || flags.contains_how || flags.contains_two_tasks;
      const isOut    = flags.out_of_scope;

      const li = document.createElement('li');
      li.className = 'cb-task-item' + (isOut ? ' out-of-scope' : hasIssue ? ' has-issue' : '');

      const iconCls = isOut ? 'error' : hasIssue ? 'warn' : 'ok';
      const iconSymbol = isOut
        ? 'fa-ban'
        : hasIssue
          ? 'fa-triangle-exclamation'
          : 'fa-check';

      let toolsHtml = '';
      if (task.tools && task.tools.length > 0) {
        toolsHtml = `<div class="cb-task-tools"><i class="fa-solid fa-wrench"></i> ${_esc(task.tools.join(', '))}</div>`;
      }

      let linkHtml = '';
      const ol = task.outgoing_link;
      if (ol && ol.data_name) {
        const target = ol.target_activity_name ? ` → ${_esc(ol.target_activity_name)}` : '';
        linkHtml = `<div class="cb-task-link"><i class="fa-solid fa-arrow-right"></i> ${_esc(ol.data_name)}${target} <span class="cb-link-type">${_esc(ol.data_type || '')}</span></div>`;
      }

      let hintHtml = '';
      if (task.rewrite_suggestion) {
        hintHtml = `<div class="cb-task-hint">💡 ${_esc(task.rewrite_suggestion)}</div>`;
      }

      li.innerHTML = `
        <i class="fa-solid ${iconSymbol} cb-task-icon ${iconCls}"></i>
        <div style="flex:1; min-width:0;">
          <div class="cb-task-label">T${i + 1}. ${_esc(task.label)}</div>
          ${toolsHtml}
          ${linkHtml}
          ${hintHtml}
        </div>
      `;
      ul.appendChild(li);
    });

    container.innerHTML = '';
    container.appendChild(ul);
  }

  function _renderChecks(checks) {
    const container = document.getElementById('cb-draft-checks-body');
    if (!container) return;

    if (!checks || checks.length === 0) {
      container.innerHTML = '<p class="cb-empty-hint">Aucune alerte.</p>';
      return;
    }

    const ul = document.createElement('ul');
    ul.className = 'cb-checks-list';

    checks.forEach(check => {
      const sev = check.severity || 'info';
      const icon = sev === 'blocker' ? 'fa-circle-xmark' : sev === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-info';
      const li = document.createElement('li');
      li.className = `cb-check-item ${sev}`;
      li.innerHTML = `<i class="fa-solid ${icon}"></i><div><strong>${_esc(check.issue)}</strong><br><span style="opacity:.8">${_esc(check.fix || '')}</span></div>`;
      ul.appendChild(li);
    });

    container.innerHTML = '';
    container.appendChild(ul);
  }

  function _renderQuestions(questions) {
    const container = document.getElementById('cb-draft-questions-body');
    if (!container) return;

    if (!questions || questions.length === 0) {
      container.innerHTML = '<p class="cb-empty-hint">Aucune question en attente.</p>';
      return;
    }

    const ul = document.createElement('ul');
    ul.className = 'cb-questions-list';

    questions.forEach(q => {
      const li = document.createElement('li');
      li.className = 'cb-question-item';
      li.textContent = q;
      li.title = 'Cliquer pour répondre';
      li.onclick = () => clickSuggestedQuestion(q);
      ul.appendChild(li);
    });

    container.innerHTML = '';
    container.appendChild(ul);
  }

  function _renderBranches(branches) {
    const section   = document.getElementById('cb-draft-branches-section');
    const container = document.getElementById('cb-draft-branches-body');
    if (!section || !container) return;

    if (!branches || branches.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = '';
    const ul = document.createElement('ul');
    ul.className = 'cb-branches-list';

    branches.forEach(branch => {
      const li = document.createElement('li');
      li.className = 'cb-branch-item';
      const variants = branch.task_variants && branch.task_variants.length > 0
        ? branch.task_variants.map(v => `• ${_esc(v)}`).join('<br>')
        : '';
      li.innerHTML = `
        <div class="cb-branch-condition">⚡ ${_esc(branch.condition)}</div>
        <div style="font-size:.77em; opacity:.85; margin-bottom:2px">${_esc(branch.impact || '')}</div>
        ${variants ? `<div style="font-size:.77em; margin-top:3px">${variants}</div>` : ''}
      `;
      ul.appendChild(li);
    });

    container.innerHTML = '';
    container.appendChild(ul);
  }

  function _updateInjectBtn(tasks, status) {
    const btn   = injectBtn();
    const count = injectCount();
    if (!btn) return;

    const validTasks = tasks.filter(t => !t.flags?.out_of_scope);

    if (validTasks.length > 0 && (status === 'ready_for_validation' || status === 'validated')) {
      btn.classList.add('visible');
      btn.disabled = false;
      if (count) count.textContent = validTasks.length;
    } else {
      btn.classList.remove('visible');
    }
  }

  function _clearDraft() {
    lastDraftTasks = [];
    const ids = ['cb-draft-tasks-body', 'cb-draft-checks-body', 'cb-draft-questions-body', 'cb-draft-branches-body'];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = '<p class="cb-empty-hint">En attente de la conversation…</p>';
    });
    const branchSection = document.getElementById('cb-draft-branches-section');
    if (branchSection) branchSection.style.display = 'none';
    const btn = injectBtn();
    if (btn) {
      btn.classList.remove('visible');
      btn.disabled = false;
      btn.innerHTML = `
        <span><i class="fa-solid fa-wand-magic-sparkles"></i> Injecter <span id="chatbot-inject-count">0</span> tâche(s) dans l'activité</span>
        <span class="inject-subtitle">Les tâches validées seront ajoutées immédiatement</span>
      `;
      btn.style.background = '';
    }
  }

  // ── Utilitaires ────────────────────────────────────────────
  function _setInputEnabled(enabled) {
    const inp  = inputEl();
    const sBtn = sendBtn();
    if (inp)  inp.disabled  = !enabled;
    if (sBtn) sBtn.disabled = !enabled;
  }

  function _esc(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Markdown minimaliste (gras, italique, listes)
  function _mdToHtml(text) {
    if (!text) return '';
    let html = _esc(text);
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Lignes avec puce
    html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
    // Sauts de ligne → <br>
    html = html.replace(/\n/g, '<br>');
    return html;
  }

})();
