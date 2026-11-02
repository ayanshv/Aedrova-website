'use strict';
(() => {
  const tour = document.querySelector('[data-product-tour]');
  if (!tour) return;
  const tabs = [...tour.querySelectorAll('[role="tab"]')];
  const panels = [...tour.querySelectorAll('[role="tabpanel"]')];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const small = matchMedia('(max-width: 700px)');
  let selected = 0, frame = 0, inView = false;
  const activeAnimations = new Set();
  function animate(element, frames, timing) {
    if (reduced.matches || !element.animate) return;
    const animation = element.animate(frames, timing);
    activeAnimations.add(animation);
    animation.finished.catch(() => {}).finally(() => activeAnimations.delete(animation));
  }
  function neutral() {
    panels.forEach(panel => {
      const picture = panel.querySelector('.tour-picture');
      picture.style.removeProperty('transform');
    });
  }
  function draw() {
    frame = 0;
    if (reduced.matches || small.matches || !inView || document.hidden) return;
    const picture = panels[selected].querySelector('.tour-picture');
    const bounds = picture.parentElement.getBoundingClientRect();
    const entry = Math.max(0, Math.min(1, (bounds.top - innerHeight * .18) / (innerHeight * .8)));
    // A small entry settle, never a pinned scene or a replacement scroll position.
    picture.style.transform = `perspective(1400px) translateY(${entry * 10}px) rotateX(${entry * 2.5}deg) scale(${1 - entry * .012})`;
  }
  function schedule() {
    if (!frame && !reduced.matches && !small.matches && inView) frame = requestAnimationFrame(draw);
  }
  function select(index, focus = false) {
    selected = index;
    activeAnimations.forEach(animation => animation.cancel());
    tabs.forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
      panels[i].hidden = i !== index;
    });
    if (focus) tabs[index].focus({preventScroll:true});
    animate(panels[index], [{opacity:.72, transform:'translateY(6px)'}, {opacity:1, transform:'none'}],
      {duration:260, easing:'cubic-bezier(.2,.7,.2,1)'});
    neutral(); schedule();
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(i));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (i + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) {event.preventDefault(); select(next, true);}
    });
  });
  select(0);
  tour.querySelector('[role="tablist"]').hidden = false;
  tour.classList.add('tour-enhanced');
  function followHash() {
    const index = panels.findIndex(panel => '#' + panel.id === location.hash);
    if (index < 0) return;
    select(index);
    requestAnimationFrame(() => tour.scrollIntoView({block:'start', behavior:'instant'}));
  }
  window.addEventListener('hashchange', followHash);
  followHash();
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const items = entry.target.matches('[data-stagger]') ? [...entry.target.children] : [entry.target];
        items.forEach((item, i) => animate(item,
          [{opacity:.65, transform:`translateY(${small.matches ? 10 : 16}px)`}, {opacity:1, transform:'none'}],
          {duration:620, delay:Math.min(i, 3) * 65, easing:'cubic-bezier(.2,.7,.2,1)'}));
        observer.unobserve(entry.target);
      });
    }, {threshold:.12});
    document.querySelectorAll('[data-reveal],[data-stagger]').forEach(element => observer.observe(element));
    new IntersectionObserver(entries => {inView = entries[0].isIntersecting; schedule();},
      {threshold:0}).observe(tour);
  }
  window.addEventListener('scroll', schedule, {passive:true});
  window.addEventListener('resize', () => {neutral(); schedule();}, {passive:true});
  reduced.addEventListener('change', () => {
    activeAnimations.forEach(animation => animation.cancel());
    neutral(); schedule();
  });
  small.addEventListener('change', () => {neutral(); schedule();});
  document.addEventListener('visibilitychange', schedule);
})();
