/* OptiqPulse — rendu du dashboard (vanilla JS, SVG maison).
   Série unique bleue partout, tooltips au survol, rafraîchissement 60 s. */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var state = { src: 'all', range: '7d', data: null, selUser: null };
  var tooltip = $('#tooltip');

  /* ---------- utilitaires ---------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtMin(m) {
    if (m >= 90) return Math.round(m / 6) / 10 + ' h';
    return m + ' min';
  }
  var TZ = { timeZone: 'Europe/Paris' };
  function fmtDate(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Paris' });
  }
  function fmtDateTime(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', timeZone: 'Europe/Paris' }) + ' ' +
           d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' });
  }
  function showTip(html, x, y) {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    var w = tooltip.offsetWidth, sw = window.innerWidth;
    tooltip.style.left = Math.min(x + 14, sw - w - 10) + 'px';
    tooltip.style.top = (y + 14) + 'px';
  }
  function hideTip() { tooltip.hidden = true; }

  /* ---------- tuiles ---------- */
  function renderTiles(t) {
    $('#tiles').innerHTML =
      tile('Connectés maintenant', t.online_now, '', true) +
      tile('Pic de simultanés', t.peak, 'sur la période') +
      tile('Utilisateurs uniques', t.unique_users, 'sur la période') +
      tile('Moyenne / jour actif', t.avg_daily_users, 'utilisateurs') +
      tile('Temps total', fmtMin(t.total_minutes), 'onglet visible') +
      tile('Pages vues', t.views, '') +
      tile('Actions', t.actions, 'créations, modifications…');
  }
  function tile(label, value, sub, hero) {
    return '<div class="tile' + (hero ? ' hero' : '') + '">' +
      '<div class="t-label">' + esc(label) + '</div>' +
      '<div class="t-value">' + esc(value) + '</div>' +
      (sub ? '<div class="t-sub">' + esc(sub) + '</div>' : '') + '</div>';
  }

  /* ---------- en ligne ---------- */
  function renderOnline(list) {
    var el = $('#online-list');
    if (!list.length) {
      el.innerHTML = '<div class="online-empty">Personne en ligne pour le moment.</div>';
      return;
    }
    el.innerHTML = list.map(function (o) {
      return '<div class="online-row"><span class="dot"></span>' +
        '<span class="who">' + esc(o.user) + '</span>' +
        '<span class="where">· ' + esc(o.label) + '</span>' +
        (state.src === 'all' ? '<span class="src-tag">' + esc(o.source) + '</span>' : '') +
        '<span class="since">' + (o.since_min === 0 ? "à l'instant" : 'il y a ' + o.since_min + ' min') + '</span></div>';
    }).join('');
  }

  /* ---------- graphique principal ---------- */
  var W = 560, H = 220, PAD = { l: 34, r: 12, t: 14, b: 26 };

  function renderMainChart(data) {
    var isToday = state.range === 'today';
    $('#main-chart-title').textContent = isToday
      ? "Utilisateurs par heure (aujourd'hui)" : 'Utilisateurs par jour';
    var rows = isToday
      ? data.hourly.map(function (h) { return { x: h.hour + ' h', users: h.users, views: h.views }; })
      : data.daily.map(function (d) { return { x: fmtDate(d.date), users: d.users, views: d.views, minutes: d.minutes, peak: d.peak }; });
    if (!rows.some(function (r) { return r.users > 0 || r.views > 0; })) {
      $('#main-chart').innerHTML = '<div class="empty">Aucune activité sur la période.</div>';
      return;
    }
    var max = Math.max.apply(null, rows.map(function (r) { return r.users; }).concat([1]));
    // Échelle à pas ENTIERS (0, step, 2·step…) — jamais de graduations inégales
    var step = Math.max(1, Math.ceil(max / 4));
    var top = step * Math.ceil(max / step);
    var iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
    var n = rows.length;
    var X = function (i) { return PAD.l + (n === 1 ? iw / 2 : i * iw / (n - 1)); };
    var Y = function (v) { return PAD.t + ih - (v / top) * ih; };

    var grid = '', labels = '';
    for (var val = 0; val <= top; val += step) {
      var y = Y(val);
      grid += '<line x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y + '" y2="' + y +
              '" stroke="var(--grid)" stroke-width="1"/>';
      labels += '<text class="axis-label" x="' + (PAD.l - 7) + '" y="' + (y + 3.5) + '" text-anchor="end">' + val + '</text>';
    }
    var every = Math.ceil(n / 8);
    rows.forEach(function (r, i) {
      if (i % every === 0 || i === n - 1) {
        labels += '<text class="axis-label" x="' + X(i) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(r.x) + '</text>';
      }
    });

    var pts = rows.map(function (r, i) { return X(i) + ',' + Y(r.users); }).join(' ');
    var area = PAD.l + ',' + (PAD.t + ih) + ' ' + pts + ' ' + (W - PAD.r) + ',' + (PAD.t + ih);
    var markers = '';
    rows.forEach(function (r, i) {
      if (r.users > 0) {
        markers += '<circle cx="' + X(i) + '" cy="' + Y(r.users) + '" r="3" fill="var(--series-1)" stroke="var(--surface)" stroke-width="2"/>';
      }
    });

    $('#main-chart').innerHTML =
      '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Utilisateurs actifs">' +
      grid +
      '<polygon points="' + area + '" fill="var(--series-1)" opacity="0.10"/>' +
      '<polyline points="' + pts + '" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>' +
      markers + labels +
      '<line x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + (PAD.t + ih) + '" y2="' + (PAD.t + ih) + '" stroke="var(--baseline)"/>' +
      '<rect id="chart-hit" x="' + PAD.l + '" y="' + PAD.t + '" width="' + iw + '" height="' + ih + '" fill="transparent"/>' +
      '<line id="crosshair" y1="' + PAD.t + '" y2="' + (PAD.t + ih) + '" stroke="var(--baseline)" stroke-dasharray="3 3" visibility="hidden"/>' +
      '</svg>';

    var svg = $('#main-chart svg'), hit = $('#chart-hit'), cross = $('#crosshair');
    hit.addEventListener('mousemove', function (ev) {
      var box = svg.getBoundingClientRect();
      var mx = (ev.clientX - box.left) * W / box.width;
      var i = Math.max(0, Math.min(n - 1, Math.round((mx - PAD.l) / (iw / Math.max(n - 1, 1)))));
      var r = rows[i];
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i));
      cross.setAttribute('visibility', 'visible');
      var html = '<b>' + esc(r.x) + '</b><br>' + r.users + ' utilisateur' + (r.users > 1 ? 's' : '') +
                 '<br>' + r.views + ' pages vues';
      if (r.minutes != null) html += '<br>' + fmtMin(r.minutes) + ' de présence';
      if (r.peak != null && r.peak > 0) html += '<br>pic : ' + r.peak + ' simultané' + (r.peak > 1 ? 's' : '');
      showTip(html, ev.clientX, ev.clientY);
    });
    hit.addEventListener('mouseleave', function () {
      cross.setAttribute('visibility', 'hidden'); hideTip();
    });
  }

  /* ---------- barres horizontales ---------- */
  function renderHBars(sel, rows, unit) {
    var el = $(sel);
    if (!rows.length) {
      el.innerHTML = '<div class="empty">Rien sur la période.</div>';
      return;
    }
    var max = Math.max.apply(null, rows.map(function (r) { return r.value; }).concat([1]));
    el.innerHTML = rows.map(function (r) {
      var pct = Math.max(1.5, r.value / max * 100);
      return '<div class="hbar" title="' + esc(r.label) + '">' +
        '<div class="hb-label">' + esc(r.label) + '</div>' +
        '<div><div class="hb-track" style="width:' + pct + '%"></div></div>' +
        '<div class="hb-value">' + (unit === 'min' ? fmtMin(r.value) : r.value) + '</div></div>';
    }).join('');
  }

  /* ---------- table utilisateurs ---------- */
  function renderUsers(users) {
    var tb = $('#users-table tbody');
    if (!users.length) {
      tb.innerHTML = '<tr><td colspan="9" class="empty">Aucun utilisateur sur la période.</td></tr>';
      return;
    }
    tb.innerHTML = users.map(function (u) {
      return '<tr data-key="' + esc(u.key) + '" data-src="' + esc(u.source) + '" data-uid="' + u.user_id + '" data-name="' + esc(u.name) + '">' +
        '<td><span class="status-dot' + (u.online ? ' on' : '') + '"></span></td>' +
        '<td><div>' + esc(u.name) + '</div><div class="u-mail">' + esc(u.email) + '</div></td>' +
        '<td><span class="src-tag">' + esc(u.source) + '</span></td>' +
        '<td>' + fmtDateTime(u.last_seen) + '</td>' +
        '<td class="num">' + fmtMin(u.minutes) + '</td>' +
        '<td class="num">' + u.views + '</td>' +
        '<td class="num">' + u.actions + '</td>' +
        '<td class="num">' + u.sessions + '</td>' +
        '<td>' + esc(u.top_pages.join(' · ')) + '</td></tr>';
    }).join('');
    Array.prototype.forEach.call(tb.querySelectorAll('tr'), function (tr) {
      tr.addEventListener('click', function () { openJourney(tr); });
    });
  }

  /* ---------- parcours ---------- */
  function openJourney(tr) {
    var tb = $('#users-table tbody');
    Array.prototype.forEach.call(tb.querySelectorAll('tr'), function (r) { r.classList.remove('sel'); });
    tr.classList.add('sel');
    state.selUser = tr.dataset.key;
    $('#journey-card').hidden = false;
    $('#journey-title').textContent = 'Parcours — ' + tr.dataset.name +
      ' (' + tr.dataset.src + ')';
    $('#journey').innerHTML = '<div class="empty">Chargement…</div>';
    fetch('/api/journey?src=' + encodeURIComponent(tr.dataset.src) +
          '&user=' + tr.dataset.uid + '&range=' + state.range)
      .then(function (r) { return r.json(); })
      .then(function (d) { renderJourney(d.journey); })
      .catch(function () {
        $('#journey').innerHTML = '<div class="empty">Erreur de chargement.</div>';
      });
    $('#journey-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderJourney(rows) {
    if (!rows.length) {
      $('#journey').innerHTML = '<div class="empty">Aucun événement sur la période.</div>';
      return;
    }
    var html = '', lastDay = '';
    rows.forEach(function (r) {
      var d = new Date(r.ts);
      var day = d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Paris' });
      if (day !== lastDay) { html += '<div class="j-day">' + esc(day) + '</div>'; lastDay = day; }
      var extra = [];
      if (r.page_minutes) extra.push(fmtMin(r.page_minutes) + ' au total sur cette page');
      if (r.kind === 'action') extra.push(r.method + (r.status >= 400 ? ' · échec ' + r.status : ''));
      html += '<div class="j-row">' +
        '<span class="j-time">' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' }) + '</span>' +
        '<span class="j-kind ' + r.kind + '">' + (r.kind === 'view' ? 'page' : 'action') + '</span>' +
        '<span class="j-label">' + esc(r.label) + '</span>' +
        '<span class="j-path">' + esc(r.path) + '</span>' +
        (extra.length ? '<span class="j-extra">' + esc(extra.join(' · ')) + '</span>' : '') +
        '</div>';
    });
    $('#journey').innerHTML = html;
  }

  /* ---------- chargement ---------- */
  function load() {
    fetch('/api/overview?src=' + encodeURIComponent(state.src) + '&range=' + state.range)
      .then(function (r) {
        if (r.status === 401) { location.href = '/login'; throw new Error('auth'); }
        return r.json();
      })
      .then(function (data) {
        state.data = data;
        $('#src-errors').innerHTML = data.errors.map(function (e) {
          return '<div class="src-error">⚠ Instance « ' + esc(e.source) +
                 ' » injoignable — ' + esc(e.error) + '</div>';
        }).join('');
        renderTiles(data.tiles);
        renderOnline(data.online);
        renderMainChart(data);
        renderHBars('#pages-views', data.pages_views, '');
        renderHBars('#pages-time', data.pages_time, 'min');
        renderUsers(data.users);
        $('#foot').textContent = 'Actualisé à ' +
          new Date(data.generated_at).toLocaleTimeString('fr-FR', TZ) +
          ' — heure de Paris, rafraîchissement automatique toutes les 60 s.';
      })
      .catch(function (e) { if (e.message !== 'auth') console.error(e); });
  }

  $('#src-select').addEventListener('change', function () {
    state.src = this.value; state.selUser = null;
    $('#journey-card').hidden = true;
    load();
  });
  Array.prototype.forEach.call(document.querySelectorAll('#range-nav button'), function (b) {
    b.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('#range-nav button'), function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      state.range = b.dataset.range;
      load();
    });
  });

  load();
  setInterval(load, 60000);
})();
