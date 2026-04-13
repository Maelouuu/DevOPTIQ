// Code/static/js/activity_highlight.js

document.addEventListener("DOMContentLoaded", () => {
  const url = new URL(window.location.href);

  // Highlight by ID (existing behaviour)
  const activityId = url.searchParams.get("activity_id") || url.searchParams.get("highlight");

  // Highlight by name (cross-carto navigation)
  const highlightName = url.searchParams.get("highlight_name");

  let container = null;

  if (activityId) {
    container =
      document.querySelector(`.activity-container[data-activity-id="${activityId}"]`) ||
      null;

    if (!container) {
      const details = document.getElementById(`details-${activityId}`);
      if (details) container = details.closest(".activity-container");
    }
  } else if (highlightName) {
    const nameNorm = highlightName.trim().toLowerCase();
    document.querySelectorAll(".activity-container").forEach(card => {
      const h2 = card.querySelector("h2");
      if (h2 && h2.textContent.trim().toLowerCase() === nameNorm) {
        container = card;
      }
    });
  }

  if (!container) return;

  // Ajout de la classe de highlight
  container.classList.add("highlighted-activity");

  // On ouvre les détails si possible
  const header = container.querySelector(".activity-header");
  if (header && typeof header.click === "function") {
    header.click();
  }

  // Scroll au centre de l'écran
  container.scrollIntoView({ behavior: "smooth", block: "center" });
});
