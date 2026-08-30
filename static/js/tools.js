// tools.js — suppression d'un outil rattaché à une tâche.
//
// ⚠️ Ce fichier est chargé APRÈS tasks.js : toute fonction qui y porte le
// même nom écrase celle de tasks.js. showToolForm / hideToolForm /
// submitTools y vivaient en double (ancienne version à base de <select>)
// et reprenaient la main sur le sélecteur d'outils refait. Elles ont été
// retirées : ne rien redéfinir ici de ce que tasks.js expose déjà.

function deleteToolFromTask(taskId, toolId) {
  if (!confirm("Confirmez-vous la suppression de cet outil ?")) return;
  fetch('/tools/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: parseInt(taskId),
      tool_id: parseInt(toolId)
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
      return;
    }
    const badgesContainer = document.getElementById('tools-badges-' + taskId);
    if (!badgesContainer) return;
    const badge = badgesContainer.querySelector(`span[data-tool-id="${toolId}"]`);
    if (badge) badge.remove();
  })
  .catch(error => {
    alert(error.message);
  });
}
