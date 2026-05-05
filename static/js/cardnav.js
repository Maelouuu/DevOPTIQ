// Code/static/js/cardnav.js
(function () {
  const nav = document.getElementById('card-nav');
  const hamburger = document.getElementById('hamburger');
  const content = nav?.querySelector('.card-nav-content');
  const cards = Array.from(nav?.querySelectorAll('.nav-card') || []);
  let isOpen = false;

  // Nettoyage de toute hauteur inline éventuellement laissée par d'anciennes versions
  if (nav) nav.style.height = '';

  function openMenu() {
    if (!nav || !content) return;
    nav.classList.add('open');
    content.setAttribute('aria-hidden', 'false');
    hamburger?.classList.add('open');
    hamburger?.setAttribute('aria-label', 'Fermer le menu');

    // Apparition des cartes avec animation GSAP
    if (window.gsap) {
      gsap.fromTo(cards, 
        { y: 12, opacity: 0 }, 
        { y: 0, opacity: 1, duration: 0.3, ease: 'power2.out', stagger: 0.05 }
      );
    }
    isOpen = true;
  }

  function closeMenu() {
    if (!nav || !content) return;
    if (window.gsap) {
      gsap.to(cards, { 
        y: -8, 
        opacity: 0, 
        duration: 0.2, 
        ease: 'power2.in', 
        stagger: 0.03, 
        onComplete: finalize 
      });
    } else {
      finalize();
    }
    function finalize(){
      nav.classList.remove('open');
      content.setAttribute('aria-hidden', 'true');
      hamburger?.classList.remove('open');
      hamburger?.setAttribute('aria-label', 'Ouvrir le menu');
      // S'assurer qu'aucune hauteur inline ne traîne
      nav.style.height = '';
      isOpen = false;
    }
  }

  function toggleMenu() { 
    isOpen ? closeMenu() : openMenu(); 
  }

  // Event listeners
  hamburger?.addEventListener('click', toggleMenu);
  hamburger?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { 
      e.preventDefault(); 
      toggleMenu(); 
    }
  });

  // Fermer le menu si on clique en dehors
  document.addEventListener('click', (e) => {
    if (isOpen && nav && !nav.contains(e.target)) {
      closeMenu();
    }
  });

  // Au resize : on ne recalcul pas la hauteur (CSS only)
  window.addEventListener('resize', () => {
    if (nav) nav.style.height = '';
  });

  // Support tactile pour le scroll horizontal
  const cardScroll = document.querySelector('.card-scroll');
  if (cardScroll) {
    let isScrolling = false;
    let startX;
    let scrollLeft;

    cardScroll.addEventListener('touchstart', (e) => {
      isScrolling = true;
      startX = e.touches[0].pageX - cardScroll.offsetLeft;
      scrollLeft = cardScroll.scrollLeft;
    }, { passive: true });

    cardScroll.addEventListener('touchmove', (e) => {
      if (!isScrolling) return;
      const x = e.touches[0].pageX - cardScroll.offsetLeft;
      const walk = (x - startX) * 1.5;
      cardScroll.scrollLeft = scrollLeft - walk;
    }, { passive: true });

    cardScroll.addEventListener('touchend', () => {
      isScrolling = false;
    }, { passive: true });
  }
})();