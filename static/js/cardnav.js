// cardnav.js — hamburger mobile only; desktop always shows items
(function () {
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
})();
