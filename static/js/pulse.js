/* OptiqPulse — battement de présence (~60 s, onglet visible uniquement).
   Alimente usage_beats : « connectés maintenant », pics, temps par page.
   S'arrête après 3 échecs consécutifs (déconnecté, réseau, instance sans
   télémétrie) et réessaie au retour de visibilité. */
(function () {
  var PERIOD = 60000;
  var fails = 0;

  function beat() {
    if (document.visibilityState !== 'visible' || fails >= 3) return;
    try {
      fetch('/pulse/beat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: location.pathname }),
        keepalive: true
      }).then(function (r) { fails = r.ok ? 0 : fails + 1; })
        .catch(function () { fails++; });
    } catch (e) { fails++; }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') { fails = 0; beat(); }
  });
  setInterval(beat, PERIOD);
  beat();
})();
