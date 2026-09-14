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

  // ── Flèches de défilement ──────────────────────────────────────────
  // La nav déborde souvent, et la barre native est masquée : sans trackpad ni
  // molette horizontale, rien ne permettait de la faire glisser. C'était un
  // liseré de 3 px qu'on tirait — un geste que rien n'annonçait. Deux flèches
  // disent d'elles-mêmes ce qu'elles font.
  const precedent = document.getElementById('card-arrow-prev');
  const suivant   = document.getElementById('card-arrow-next');

  if (scroll && precedent && suivant) {
    const debordement = () => scroll.scrollWidth - scroll.clientWidth;

    // Un pas = presque une page, en gardant un item en commun : on ne perd pas
    // le fil de ce qu'on regardait.
    const pas = () => Math.max(120, scroll.clientWidth * 0.8);

    function rafraichir() {
      const max = debordement();
      const utile = max > 2;
      for (const f of [precedent, suivant]) f.classList.toggle('is-usable', utile);
      // En butée, la flèche reste VISIBLE mais s'estompe : la faire disparaître
      // ferait sauter la mise en page à chaque extrémité atteinte.
      precedent.classList.toggle('is-end', utile && scroll.scrollLeft <= 1);
      suivant.classList.toggle('is-end', utile && scroll.scrollLeft >= max - 1);
    }

    // ⚠️ `scroll-snap-type: x mandatory` et `behavior: 'smooth'` se battent :
    // chaque image du défilement est ramenée sur l'item le plus proche, et le
    // trajet met plus d'une seconde pour finir par arriver. On neutralise le
    // magnétisme le temps du geste — exactement ce que faisait l'ancien liseré
    // pendant qu'on le tirait — puis on le rend, pour que le repos reste calé
    // sur un item.
    let remiseEnPlace = null;

    function glisser(sens) {
      const max = debordement();
      if (max <= 2) return;
      const cible = Math.max(0, Math.min(max, scroll.scrollLeft + sens * pas()));

      clearTimeout(remiseEnPlace);
      scroll.style.scrollSnapType = 'none';
      scroll.scrollTo({ left: cible, behavior: 'smooth' });

      remiseEnPlace = setTimeout(() => {
        scroll.style.scrollSnapType = '';
        rafraichir();
      }, 420);
    }

    precedent.addEventListener('click', () => glisser(-1));
    suivant.addEventListener('click', () => glisser(1));

    scroll.addEventListener('scroll', rafraichir, { passive: true });
    scroll.addEventListener('scrollend', rafraichir);
    window.addEventListener('resize', rafraichir);
    if (window.ResizeObserver) new ResizeObserver(rafraichir).observe(scroll);
    // ⚠️ Les icônes Font Awesome arrivent APRÈS le premier rendu : la largeur
    // utile change, donc on recalcule une fois tout chargé — sinon les flèches
    // restent masquées sur une nav qui déborde pourtant.
    window.addEventListener('load', rafraichir);
    rafraichir();

    // Molette verticale → défilement horizontal, sauf en butée (sinon on
    // bloquerait le défilement de la PAGE au survol de la nav).
    scroll.addEventListener('wheel', (e) => {
      const max = debordement();
      if (max <= 2 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      if ((e.deltaY < 0 && scroll.scrollLeft <= 0) ||
          (e.deltaY > 0 && scroll.scrollLeft >= max - 1)) return;
      e.preventDefault();
      scroll.scrollLeft = Math.max(0, Math.min(max, scroll.scrollLeft + e.deltaY));
      rafraichir();
    }, { passive: false });
  }
})();
