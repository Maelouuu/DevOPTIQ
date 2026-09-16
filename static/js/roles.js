// static/js/roles.js

// ⚠️ Cette fenêtre parlait par `alert()` et en français en dur. Les messages
// passent maintenant par `window.GARANT_I18N` (injecté par le gabarit) et
// s'écrivent DANS la fenêtre : une alerte système ferme le contexte au moment
// précis où l'on a besoin de le relire pour corriger.
function _garantT(cle) {
    var d = window.GARANT_I18N || {};
    return d[cle] || cle;
}

function _garantNote(message) {
    var el = document.getElementById('garant-note');
    if (!el) { return; }
    el.textContent = message || '';
    el.classList.toggle('hidden', !message);
}

function openGarantModal(activityId) {
    document.getElementById('garantModal').style.display = 'flex';
    document.getElementById('garant-activity-id').value = activityId;
    document.getElementById('garant-new-role').value = '';
    _garantNote('');

    var selectElem = document.getElementById('garant-role-select');
    selectElem.innerHTML = '';

    fetch('/roles/list')
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (!data.length) {
                var vide = document.createElement('option');
                vide.value = '';
                vide.textContent = _garantT('none');
                vide.disabled = true;
                selectElem.appendChild(vide);
                return;
            }
            data.forEach(function (r) {
                var opt = document.createElement('option');
                opt.value = r.name;            // on stocke le nom
                opt.textContent = r.name;
                selectElem.appendChild(opt);
            });
        })
        .catch(function () { _garantNote(_garantT('load_failed')); });
}

function closeGarantModal() {
    document.getElementById('garantModal').style.display = 'none';
}

function toggleDetails(detailsId) {
    var details = document.getElementById(detailsId);

    if (details.style.display === 'none' || details.style.display === '') {
        details.style.display = 'block';
    } else {
        details.style.display = 'none';
    }
}

function submitGarantRole() {
    var activityId = document.getElementById('garant-activity-id').value;
    var selectElem = document.getElementById('garant-role-select');
    var newRoleInput = document.getElementById('garant-new-role').value.trim();
    var roleName = newRoleInput || selectElem.value;

    if (!roleName) {
        _garantNote(_garantT('need'));
        return;
    }

    fetch('/roles/garant/activity/' + activityId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_name: roleName })
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                _garantNote(data.error);
                return;
            }
            var garantSpan = document.getElementById('activity-garant-' + activityId);
            if (garantSpan) { garantSpan.textContent = data.role.name; }
            closeGarantModal();
        })
        .catch(function () { _garantNote(_garantT('save_failed')); });
}
