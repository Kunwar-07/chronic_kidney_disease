// Progressive enhancement: content stays visible without IntersectionObserver.
// Only below-the-fold presentation blocks participate; inputs never move.
export function mountMotion(root, environment = window) {
  const media = environment.matchMedia('(prefers-reduced-motion: reduce)');
  const pending = new Set();
  let observer;
  const show = element => {
    if (!pending.delete(element)) return;
    element.classList.add('is-revealed');
    observer?.unobserve(element);
  };
  const revealWithin = target => {
    for (const element of pending) {
      if (element === target || target.contains(element) || element.contains(target)) show(element);
    }
  };
  const revealAll = () => {
    for (const element of pending) show(element);
    observer?.disconnect();
  };
  const onPreference = event => { if (event.matches) revealAll(); };
  const onFocus = event => {
    // Focusing the main landmark must not reveal the entire page prematurely.
    for (const element of pending) if (element.contains(event.target)) show(element);
  };
  if (!media.matches && environment.IntersectionObserver) {
    observer = new environment.IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) show(entry.target);
    }, {threshold: 0, rootMargin: '0px 0px -24px 0px'});
    const selectors = '.section-kicker, .intro-layout, .section-head, .pathway-card, .steps > article, .capability, .research-story > div, .closing, .page-shell .panel, .prose section, .trend-empty, .health-bottom';
    for (const element of root.querySelectorAll(selectors)) {
      // Visible content is never hidden during mounting, including anchor destinations.
      if (element.getBoundingClientRect().top < environment.innerHeight) continue;
      const siblings = [...element.parentElement.children];
      const stagger = element.matches('.capability, .pathway-card, .steps > article');
      element.style.setProperty('--reveal-delay', `${stagger ? (siblings.indexOf(element) % 3) * 65 : 0}ms`);
      pending.add(element);
      element.classList.add('reveal-ready');
      observer.observe(element);
    }
    root.addEventListener('focusin', onFocus);
    media.addEventListener('change', onPreference);
  }
  return {
    revealWithin,
    destroy() {
      revealAll();
      root.removeEventListener('focusin', onFocus);
      media.removeEventListener('change', onPreference);
    }
  };
}
