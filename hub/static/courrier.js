/* Page Courrier — remplissage des deux moitiés.
 *
 * ⚠️ Les deux appels partent EN PARALLÈLE et s'affichent séparément. Une
 * lecture IMAP demande deux à quatre secondes, une base Neon froide une : en
 * série, les chiffres attendraient la boîte pour rien. C'est la leçon de
 * /panel, où le rendu bloquait sur un appel inter-services.
 */
(function () {
  "use strict";

  var zReset = document.getElementById("cr-reset");
  var zBoite = document.getElementById("cr-boite");
  var nReset = document.getElementById("cr-reset-note");
  var nBoite = document.getElementById("cr-boite-note");
  var bouton = document.getElementById("cr-refresh");
  if (!zReset || !zBoite) { return; }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;",
               '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pluriel(n, un, plusieurs) {
    return n + " " + (n > 1 ? plusieurs : un);
  }

  // ── Réinitialisations ───────────────────────────────────────────────────

  function serie(points) {
    // L'échelle est celle du maximum observé : une hauteur absolue rendrait
    // toutes les séries plates dès qu'une instance est peu sollicitée.
    var max = 0, i;
    for (i = 0; i < points.length; i++) { if (points[i].n > max) { max = points[i].n; } }
    var out = '<div class="cr-serie" role="img" aria-label="'
            + esc(pluriel(points.length, "jour", "jours")) + '">';
    for (i = 0; i < points.length; i++) {
      var p = points[i];
      var h = max > 0 ? Math.max(2, Math.round((p.n / max) * 46)) : 2;
      out += '<span class="cr-barre' + (p.n ? "" : " vide")
           + '" style="height:' + h + 'px" title="' + esc(p.jour) + " — "
           + esc(pluriel(p.n, "demande", "demandes")) + '"></span>';
    }
    return out + "</div>";
  }

  function comptes(liste) {
    if (!liste.length) { return ""; }
    var out = '<ul class="cr-comptes">';
    for (var i = 0; i < liste.length && i < 8; i++) {
      var c = liste[i];
      out += "<li>"
           + '<span class="cr-qui">' + esc(c.nom) + "</span>"
           + '<span class="cr-lang">' + esc(c.langue) + "</span>"
           + '<span class="cr-mail">' + esc(c.email) + "</span>"
           + '<span class="cr-n">' + esc(pluriel(c.demandes, "demande", "demandes"))
           + (c.abouties < c.demandes
               ? " · " + (c.demandes - c.abouties) + " sans suite" : "")
           + "</span></li>";
    }
    if (liste.length > 8) {
      out += '<li><span class="cr-mail">et ' + (liste.length - 8)
           + " de plus</span></li>";
    }
    return out + "</ul>";
  }

  function carte(i) {
    var corps;
    if (i.erreur) {
      corps = '<p class="cr-etat cr-mal">Lecture impossible : '
            + esc(i.erreur) + "</p>";
    } else if (!i.present) {
      // ⚠️ Pas une panne : la réinitialisation n'est pas déployée partout.
      corps = '<p class="cr-etat">La réinitialisation de mot de passe n\'est pas '
            + "encore déployée sur cette instance — sa base ne porte pas la "
            + "table des demandes.</p>";
    } else if (!i.total) {
      corps = '<p class="cr-etat">Aucune demande sur la période.</p>';
    } else {
      corps = '<div class="cr-chiffres">'
            + '<div class="cr-chiffre"><b>' + i.total + "</b><span>demandes</span></div>"
            + '<div class="cr-chiffre"><b>' + i.abouties + "</b><span>abouties</span></div>"
            + '<div class="cr-chiffre' + (i.abandonnees ? " alerte" : "") + '"><b>'
            + i.abandonnees + "</b><span>sans suite</span></div>"
            + '<div class="cr-chiffre"><b>' + i.inconnues
            + "</b><span>adresse inconnue</span></div>"
            + "</div>"
            + serie(i.serie || [])
            + comptes(i.comptes || []);
    }
    return '<article class="carte acc-courrier">'
         + '<div class="carte-bandeau"><svg class="ic"><use href="#i-base"></use></svg>'
         + "<code>" + esc(i.nom) + "</code></div>"
         + '<div class="carte-corps">' + corps + "</div></article>";
  }

  function rendreReset(j) {
    if (!j.configure) {
      zReset.innerHTML = '<div class="cr-manque">'
        + "<h3>Aucune base suivie</h3>"
        + "<p>Le hub découvre l'adresse des bases dans les specs Cloud Run "
        + "au déploiement. Aucune n'a été trouvée : redéployez le hub.</p></div>";
      return;
    }
    if (nReset) {
      nReset.textContent = pluriel(j.jours, "dernier jour", "derniers jours");
    }
    var out = '<div class="grille-paire">';
    for (var i = 0; i < j.instances.length; i++) { out += carte(j.instances[i]); }
    zReset.innerHTML = out + "</div>";
  }

  // ── Boîte de réception ──────────────────────────────────────────────────

  var NATURE = { rejet: "rejet", auto: "auto", reponse: "réponse" };

  function rendreBoite(j) {
    if (!j.configure) {
      // On dit QUOI faire. Un « non configuré » sec envoie chercher ailleurs.
      zBoite.innerHTML = '<div class="cr-manque">'
        + "<h3>La boîte n'est pas branchée</h3>"
        + "<p>Il manque un mot de passe d'application — <strong>un second</strong>, "
        + "distinct de celui qui sert à envoyer : révoquer l'un ne doit pas couper "
        + "l'autre.</p>"
        + "<ol>"
        + "<li>Compte Google de l'adresse d'envoi → Sécurité → "
        + "Mots de passe d'application → en créer un, nommé <code>Optiq Hub</code>.</li>"
        + "<li>Dépôt GitHub → Settings → Secrets → Actions : "
        + "<code>HUB_IMAP_USER</code> (l'adresse) et "
        + "<code>HUB_IMAP_PASSWORD</code> (le mot de passe d'application, "
        + "sans les espaces).</li>"
        + "<li>Redéployer le hub.</li>"
        + "</ol></div>";
      if (nBoite) { nBoite.textContent = ""; }
      return;
    }
    if (j.erreur) {
      zBoite.innerHTML = '<p class="cr-etat cr-mal">Connexion refusée : '
        + esc(j.erreur) + "</p>";
      return;
    }
    if (nBoite) {
      nBoite.textContent = j.adresse
        + (j.compte && j.compte.rejet ? " · " + pluriel(j.compte.rejet, "rejet", "rejets") : "");
    }
    if (!j.messages.length) {
      zBoite.innerHTML = '<p class="cr-etat">Rien reçu — c\'est la bonne '
        + "nouvelle : aucun rejet n'est revenu.</p>";
      return;
    }
    var out = '<article class="carte acc-courrier"><div class="carte-corps">'
            + '<ul class="cr-liste">';
    for (var i = 0; i < j.messages.length; i++) {
      var m = j.messages[i];
      out += '<li class="cr-msg">'
           + '<span class="cr-nat ' + esc(m.nature) + '">'
           + esc(NATURE[m.nature] || m.nature) + "</span>"
           + "<span><span class='cr-sujet'>" + esc(m.sujet) + "</span>"
           + '<span class="cr-de">' + esc(m.de) + "</span></span>"
           + '<span class="cr-date">' + esc(m.date) + "</span></li>";
    }
    zBoite.innerHTML = out + "</ul></div></article>";
  }

  // ── Chargement ──────────────────────────────────────────────────────────

  function charger(chemin, zone, rendre, force) {
    fetch(chemin + (force ? "?force=1" : ""), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      })
      .then(rendre)
      .catch(function (e) {
        zone.innerHTML = '<p class="cr-etat cr-mal">Le hub n\'a pas pu lire '
          + "cette partie : " + esc(e.message) + "</p>";
      });
  }

  function tout(force) {
    zReset.innerHTML = '<p class="cr-attente">Lecture des bases…</p>';
    zBoite.innerHTML = '<p class="cr-attente">Connexion à la boîte…</p>';
    charger("/api/courrier/reset", zReset, rendreReset, force);
    charger("/api/courrier/boite", zBoite, rendreBoite, force);
  }

  if (bouton) {
    bouton.addEventListener("click", function () {
      bouton.disabled = true;
      tout(true);
      // Le cache serveur est court ; le bouton se rend la main dès que les
      // deux zones sont réécrites, sans attendre une promesse qu'on ne tient
      // pas (chaque moitié se termine de son côté).
      setTimeout(function () { bouton.disabled = false; }, 1200);
    });
  }

  tout(false);
})();
