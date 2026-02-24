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
  let currentMode         = null;   // 'ameliorer' | 'creer'
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

    if (_fetchController) _fetchController.abort();
    _fetchController = new AbortController();
    const signal = _fetchController.signal;

    currentActId        = actId;
    storedContext       = null;
    conversationHistory = [];
    currentMode         = null;

    headerTitle().textContent = `Assistant OPTIQ — ${actName}`;
    headerSub().textContent   = 'Chargement du contexte…';

    _clearMessages();
    _clearDraft();

    overlay().classList.add('active');
    document.body.style.overflow = 'hidden';

    const loadingEl = _showTyping();

    fetch(`/api/chatbot/activity/${actId}/context`, { signal })
      .then(r => {
        if (!r.ok) throw new Error(`Erreur ${r.status}`);
        return r.json();
      })
      .then(activityContext => {
        if (currentActId !== actId) return;

        _removeTyping(loadingEl);
        storedContext = activityContext;

        const nbTasks   = activityContext.tasks   ? activityContext.tasks.length   : 0;
        const nbSavoirs = activityContext.savoirs  ? activityContext.savoirs.length  : 0;
        const nbHSC     = activityContext.hsc      ? activityContext.hsc.length      : 0;
        headerSub().textContent =
          `${nbTasks} tâche(s) · ${nbSavoirs} savoir(s) · ${nbHSC} HSC`;

        // Proposer le choix du mode avant de démarrer la conversation
        _showModeSelection(activityContext);
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        _removeTyping(loadingEl);
        _appendBotMessage('❌ Impossible de charger le contexte de l\'activité : ' + err.message);
        headerSub().textContent = 'Erreur de chargement';
      });
  };

  // ── Sélection du mode au démarrage ────────────────────────
  function _showModeSelection(ctx) {
    const nbTasks    = ctx.tasks ? ctx.tasks.length : 0;
    const hasExisting = nbTasks > 0;

    const el = document.createElement('div');
    el.className = 'cb-msg bot cb-mode-selection';
    el.id = 'cb-mode-selection-el';

    el.innerHTML = `
      <div class="cb-mode-greeting">
        Bonjour ! Je suis l'<strong>Assistant OPTIQ</strong> pour l'activité
        <strong>${_esc(ctx.name)}</strong>.<br><br>
        ${hasExisting
          ? `Cette activité possède déjà <strong>${nbTasks} tâche(s)</strong>.`
          : `Cette activité n'a pas encore de tâches.`
        }
        Que souhaitez-vous faire ?
      </div>
      <div class="cb-mode-choices">
        <button
          class="cb-mode-choice${!hasExisting ? ' cb-mode-no-tasks' : ''}"
          onclick="selectChatbotMode('ameliorer')"
          ${!hasExisting ? 'disabled' : ''}>
          <i class="fa-solid fa-magnifying-glass-chart"></i>
          <div class="cb-mode-choice-text">
            <strong>Revoir les tâches existantes</strong>
            <span>${hasExisting
              ? `Analyser et améliorer les ${nbTasks} tâche(s) selon les règles OPTIQ`
              : 'Aucune tâche existante à revoir'
            }</span>
          </div>
        </button>
        <button class="cb-mode-choice" onclick="selectChatbotMode('creer')">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          <div class="cb-mode-choice-text">
            <strong>Créer des tâches</strong>
            <span>Définir de nouvelles tâches via un entretien guidé</span>
          </div>
        </button>
      </div>
    `;

    msgContainer().appendChild(el);
    _scrollToBottom();
  }

  window.selectChatbotMode = function (mode) {
    currentMode = mode;

    // Retirer l'écran de sélection
    const el = document.getElementById('cb-mode-selection-el');
    if (el) el.remove();

    const ctx        = storedContext;
    const nbExisting = ctx.tasks ? ctx.tasks.length : 0;

    // Mettre à jour le sous-titre du header
    const modeLabel = mode === 'ameliorer' ? 'Mode révision' : 'Mode création';
    headerSub().textContent = `${modeLabel} · ${nbExisting} tâche(s) chargée(s)`;

    // Construire le message d'amorce selon le mode
    let amorce;
    if (mode === 'ameliorer') {
      const taskList = ctx.tasks.map(t => `"${t.name}"`).join(', ');
      amorce = `Mode révision activé. L'activité "${ctx.name}" a ${nbExisting} tâche(s) existante(s) : ${taskList}. Analyse-les selon les règles OPTIQ et propose des améliorations détaillées.`;
    } else {
      amorce = `Mode création activé. Je souhaite créer les tâches pour l'activité "${ctx.name}" via un entretien guidé. Commence l'interview.`;
    }

    _sendToBot(amorce);
  };

  // ── Fermeture ──────────────────────────────────────────────
  window.closeChatbot = function () {
    overlay().classList.remove('active');
    document.body.style.overflow = '';
  };

  document.addEventListener('DOMContentLoaded', function () {
    const ov = overlay();
    if (!ov) return;
    ov.addEventListener('click', function (e) {
      if (e.target === ov) closeChatbot();
    });

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

    // Supprimer les suggestions de réponse rapide
    document.querySelectorAll('.cb-quick-replies').forEach(el => el.remove());

    inp.value = '';
    inp.style.height = 'auto';
    _appendUserMessage(text);
    _sendToBot(text);
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
        if (!ok) throw new Error(data.error || 'Échec de l\'injection');
        btn.innerHTML = `<i class="fa-solid fa-check"></i> ${data.count} tâche(s) ajoutée(s) !`;
        btn.style.background = 'linear-gradient(135deg, #667eea, #8b5cf6)';

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
        mode:     currentMode || 'creer',
      }),
    })
      .then(r => r.json())
      .then(data => {
        _removeTyping(typingEl);
        if (data.error) {
          _appendBotMessage('❌ ' + data.error);
        } else {
          conversationHistory.push({ role: 'user',      content: message });
          conversationHistory.push({ role: 'assistant', content: data.assistant_message || '' });
          _appendBotMessage(data.assistant_message, data.next_questions);
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
  function _appendBotMessage(text, nextQuestions) {
    // Supprimer les anciennes suggestions rapides
    document.querySelectorAll('.cb-quick-replies').forEach(el => el.remove());

    const el = document.createElement('div');
    el.className = 'cb-msg bot';
    el.innerHTML = _mdToHtml(text);
    msgContainer().appendChild(el);

    // Afficher les suggestions de réponse dans la conversation (pas dans le panneau)
    if (nextQuestions && nextQuestions.length > 0) {
      const qrDiv = document.createElement('div');
      qrDiv.className = 'cb-quick-replies';

      nextQuestions.forEach(q => {
        const btn = document.createElement('button');
        btn.className = 'cb-quick-reply-btn';
        btn.textContent = q;
        btn.onclick = () => {
          document.querySelectorAll('.cb-quick-replies').forEach(el => el.remove());
          const inp = inputEl();
          if (inp) inp.value = q;
          sendMessage();
        };
        qrDiv.appendChild(btn);
      });

      msgContainer().appendChild(qrDiv);
    }

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
    const tasks    = data.tasks          || [];
    const checks   = data.quality_checks || [];
    const branches = data.branches       || [];
    const status   = data.status         || 'need_more_info';

    lastDraftTasks = tasks;

    _renderTasks(tasks);
    _renderChecks(checks);
    _renderStatus(status);
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
      const flags    = task.flags || {};
      const hasIssue = flags.too_detailed || flags.contains_how || flags.contains_two_tasks;
      const isOut    = flags.out_of_scope;

      const li = document.createElement('li');
      li.className = 'cb-task-item' + (isOut ? ' out-of-scope' : hasIssue ? ' has-issue' : '');

      const iconCls    = isOut ? 'error' : hasIssue ? 'warn' : 'ok';
      const iconSymbol = isOut ? 'fa-ban' : hasIssue ? 'fa-triangle-exclamation' : 'fa-check';

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
          ${toolsHtml}${linkHtml}${hintHtml}
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
      container.innerHTML = '<p class="cb-empty-hint">Aucune alerte qualité.</p>';
      return;
    }

    const ul = document.createElement('ul');
    ul.className = 'cb-checks-list';

    checks.forEach(check => {
      const sev  = check.severity || 'info';
      const icon = sev === 'blocker' ? 'fa-circle-xmark' : sev === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-info';
      const li   = document.createElement('li');
      li.className = `cb-check-item ${sev}`;
      li.innerHTML = `<i class="fa-solid ${icon}"></i><div><strong>${_esc(check.issue)}</strong><br><span style="opacity:.8">${_esc(check.fix || '')}</span></div>`;
      ul.appendChild(li);
    });

    container.innerHTML = '';
    container.appendChild(ul);
  }

  function _renderStatus(status) {
    const container = document.getElementById('cb-draft-status-body');
    if (!container) return;

    const statusConfig = {
      'need_more_info': {
        icon: 'fa-hourglass-half',
        color: '#f59e0b',
        bg: '#fffbeb',
        label: 'Analyse en cours',
        desc: 'L\'assistant recueille les informations nécessaires.',
      },
      'ready_for_validation': {
        icon: 'fa-circle-check',
        color: '#22c55e',
        bg: '#f0fdf4',
        label: 'Prêt à valider',
        desc: 'Les tâches peuvent être injectées dans l\'activité.',
      },
      'validated': {
        icon: 'fa-trophy',
        color: '#8b5cf6',
        bg: '#f5f3ff',
        label: 'Validé',
        desc: 'Les tâches ont été validées avec l\'utilisateur.',
      },
    };

    const s = statusConfig[status] || statusConfig['need_more_info'];

    const modeHtml = currentMode
      ? `<div class="cb-mode-badge">
          ${currentMode === 'ameliorer'
            ? '<i class="fa-solid fa-magnifying-glass-chart"></i> Mode révision'
            : '<i class="fa-solid fa-wand-magic-sparkles"></i> Mode création'
          }
         </div>`
      : '';

    container.innerHTML = `
      <div class="cb-status-row" style="background:${s.bg}; border-radius:7px; padding:8px 10px; display:flex; align-items:center; gap:9px;">
        <i class="fa-solid ${s.icon}" style="color:${s.color}; font-size:1.15em; flex-shrink:0;"></i>
        <div>
          <div style="font-weight:700; color:${s.color}; font-size:0.81rem;">${s.label}</div>
          <div style="font-size:0.73rem; color:#6b7280; margin-top:2px;">${s.desc}</div>
        </div>
      </div>
      ${modeHtml}
    `;
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
    const ids = ['cb-draft-tasks-body', 'cb-draft-checks-body', 'cb-draft-status-body', 'cb-draft-branches-body'];
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
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
    html = html.replace(/\n/g, '<br>');
    return html;
  }

})();
