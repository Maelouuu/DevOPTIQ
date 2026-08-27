// cardnav.js — hamburger mobile only; desktop always shows items
(function () {
  // Mark active nav item based on current URL
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-card').forEach(card => {
    const href = card.getAttribute('href');
    if (href && (currentPath === href || currentPath.startsWith(href + '/') || currentPath.startsWith(href + '?'))) {
      card.classList.add('active');
    }
  });

  const nav       = document.getElementById('card-nav');
  const hamburger = document.getElementById('hamburger');
  const content   = nav?.querySelector('.card-nav-content');
  let isOpen = false;

  function openMenu() {
    if (!nav || !content) return;
    nav.classList.add('open');
    content.setAttribute('aria-hidden', 'false');
    hamburger?.classList.add('open');
    hamburger?.setAttribute('aria-label', 'Fermer le menu');
    isOpen = true;
  }

  function closeMenu() {
    if (!nav || !content) return;
    nav.classList.remove('open');
    content.setAttribute('aria-hidden', 'true');
    hamburger?.classList.remove('open');
    hamburger?.setAttribute('aria-label', 'Ouvrir le menu');
    isOpen = false;
  }

  function toggleMenu() { isOpen ? closeMenu() : openMenu(); }

  hamburger?.addEventListener('click', toggleMenu);
  hamburger?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleMenu(); }
  });

  document.addEventListener('click', (e) => {
    if (isOpen && nav && !nav.contains(e.target)) closeMenu();
  });

  // Touch scroll horizontal
  const scroll = document.querySelector('.card-scroll');
  if (scroll) {
    let startX, scrollLeft, scrolling = false;
    scroll.addEventListener('touchstart', e => {
      scrolling = true;
      startX = e.touches[0].pageX - scroll.offsetLeft;
      scrollLeft = scroll.scrollLeft;
    }, { passive: true });
    scroll.addEventListener('touchmove', e => {
      if (!scrolling) return;
      const dx = (e.touches[0].pageX - scroll.offsetLeft - startX) * 1.4;
      scroll.scrollLeft = scrollLeft - dx;
    }, { passive: true });
    scroll.addEventListener('touchend', () => { scrolling = false; }, { passive: true });
  }

  // ── Liseré de défilement ───────────────────────────────────────────
  // Sans trackpad (ni molette horizontale) la nav était impossible à faire
  // défiler : le liseré est une vraie barre, on peut la tirer, et la molette
  // verticale déplace la nav tant qu'elle n'est pas en butée.
  const bar   = document.getElementById('card-scrollbar');
  const track = bar?.querySelector('.card-scrollbar-track');
  const thumb = bar?.querySelector('.card-scrollbar-thumb');

  if (scroll && bar && track && thumb) {
    let masquer = null;

    const debordement = () => scroll.scrollWidth - scroll.clientWidth;

    function rafraichir() {
      const max = debordement();
      if (max <= 2) { bar.classList.remove('is-scrollable'); return; }
      bar.classList.add('is-scrollable');
      const largeurRail = track.clientWidth;
      const largeur = Math.max(28, largeurRail * (scroll.clientWidth / scroll.scrollWidth));
      thumb.style.width = largeur + 'px';
      thumb.style.transform =
        'translateX(' + ((largeurRail - largeur) * (scroll.scrollLeft / max)) + 'px)';
    }

    function montrer() {
      if (!bar.classList.contains('is-scrollable')) return;
      bar.classList.add('is-active');
      clearTimeout(masquer);
      masquer = setTimeout(() => bar.classList.remove('is-active'), 1200);
    }

    scroll.addEventListener('scroll', () => { rafraichir(); montrer(); }, { passive: true });
    window.addEventListener('resize', rafraichir);
    if (window.ResizeObserver) new ResizeObserver(rafraichir).observe(scroll);
    // les icônes Font Awesome arrivent après le premier rendu : la largeur
    // utile change, donc on recalcule une fois tout chargé.
    window.addEventListener('load', rafraichir);
    rafraichir();

    // Molette verticale → défilement horizontal, sauf en butée (sinon on
    // bloquerait le défilement de la page au survol de la nav).
    scroll.addEventListener('wheel', (e) => {
      const max = debordement();
      if (max <= 2 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      const cible = scroll.scrollLeft + e.deltaY;
      if ((e.deltaY < 0 && scroll.scrollLeft <= 0) ||
          (e.deltaY > 0 && scroll.scrollLeft >= max - 1)) return;
      e.preventDefault();
      scroll.scrollLeft = Math.max(0, Math.min(max, cible));
      montrer();
    }, { passive: false });

    // Tirer le liseré (ou cliquer dans le rail pour sauter à cet endroit)
    let saisi = false, snapInitial = '';

    function positionner(clientX) {
      // Le clic peut tomber n'importe où dans la zone de captation : on le
      // ramène sur le rail, bornes comprises.
      const rail = track.getBoundingClientRect();
      const largeur = thumb.offsetWidth;
      const course = rail.width - largeur;
      if (course <= 0) return;
      const x = Math.max(0, Math.min(course, clientX - rail.left - largeur / 2));
      scroll.scrollLeft = (x / course) * debordement();
    }

    bar.addEventListener('pointerdown', (e) => {
      if (!bar.classList.contains('is-scrollable')) return;
      saisi = true;
      bar.classList.add('is-dragging');
      bar.setPointerCapture(e.pointerId);
      // le scroll-snap ferait sauter le curseur pendant le glissé
      snapInitial = scroll.style.scrollSnapType;
      scroll.style.scrollSnapType = 'none';
      if (e.target !== thumb) positionner(e.clientX);
      e.preventDefault();
    });

    bar.addEventListener('pointermove', (e) => {
      if (!saisi) return;
      positionner(e.clientX);
      e.preventDefault();
    });

    function relacher(e) {
      if (!saisi) return;
      saisi = false;
      bar.classList.remove('is-dragging');
      scroll.style.scrollSnapType = snapInitial;
      try { bar.releasePointerCapture(e.pointerId); } catch (err) { /* deja relache */ }
    }
    bar.addEventListener('pointerup', relacher);
    bar.addEventListener('pointercancel', relacher);
  }
})();
