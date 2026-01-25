/**
 * activities_tabs.js
 * Gestion des onglets et de l'affichage des activités
 */

/**
 * Toggle l'affichage du contenu d'une activité
 */
function toggleActivity(activityId) {
    const content = document.getElementById(`content-${activityId}`);
    const icon = document.getElementById(`icon-${activityId}`);
    const container = document.querySelector(`[data-activity-id="${activityId}"]`);

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        icon.classList.add('rotated');
        // Ajouter la classe expanded pour l'animation d'agrandissement
        if (container) {
            container.classList.add('expanded');
        }
    } else {
        content.style.display = 'none';
        icon.classList.remove('rotated');
        // Retirer la classe expanded pour rétrécir
        if (container) {
            container.classList.remove('expanded');
        }
    }
}

/**
 * Ouvre un onglet spécifique et masque les autres
 */
function openTab(event, tabId, activityId) {
    // Masquer tous les contenus d'onglets pour cette activité
    const allTabContents = document.querySelectorAll(`#content-${activityId} .tab-content`);
    allTabContents.forEach(content => {
        content.classList.remove('active');
    });

    // Désactiver tous les boutons d'onglets pour cette activité
    const allTabButtons = document.querySelectorAll(`#content-${activityId} .tab-button`);
    allTabButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Afficher l'onglet sélectionné
    const selectedTab = document.getElementById(tabId);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activer le bouton d'onglet cliqué
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    }
}

/**
 * Ouvre automatiquement une activité et un onglet spécifique
 * Utile pour les liens profonds depuis d'autres pages
 */
function openActivityTab(activityId, tabName) {
    // Ouvrir l'activité si elle est fermée
    const content = document.getElementById(`content-${activityId}`);
    const icon = document.getElementById(`icon-${activityId}`);
    const activityContainer = document.querySelector(`[data-activity-id="${activityId}"]`);

    if (content && (content.style.display === 'none' || content.style.display === '')) {
        content.style.display = 'block';
        if (icon) {
            icon.classList.add('rotated');
        }
        if (activityContainer) {
            activityContainer.classList.add('expanded');
        }
    }

    // Ouvrir l'onglet spécifique
    const tabId = `${tabName}-${activityId}`;
    openTab(null, tabId, activityId);

    // Scroller jusqu'à l'activité
    if (activityContainer) {
        activityContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Initialisation au chargement de la page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Vérifier s'il y a un hash dans l'URL pour ouvrir une activité spécifique
    const hash = window.location.hash;
    if (hash) {
        const match = hash.match(/#activity-(\d+)(?:-(.+))?/);
        if (match) {
            const activityId = match[1];
            const tabName = match[2] || 'overview';

            // Attendre un court instant pour que le DOM soit complètement chargé
            setTimeout(() => {
                openActivityTab(activityId, tabName);
            }, 100);
        }
    }
});

/**
 * Fonction pour ouvrir/fermer tous les détails d'activités
 */
function toggleAllActivities(expand = true) {
    const allActivities = document.querySelectorAll('.activity-container');

    allActivities.forEach(container => {
        const activityId = container.getAttribute('data-activity-id');
        const content = document.getElementById(`content-${activityId}`);
        const icon = document.getElementById(`icon-${activityId}`);

        if (content && icon) {
            if (expand) {
                content.style.display = 'block';
                icon.classList.add('rotated');
                container.classList.add('expanded');
            } else {
                content.style.display = 'none';
                icon.classList.remove('rotated');
                container.classList.remove('expanded');
            }
        }
    });
}

// Exposer les fonctions globalement
window.toggleActivity = toggleActivity;
window.openTab = openTab;
window.openActivityTab = openActivityTab;
window.toggleAllActivities = toggleAllActivities;
