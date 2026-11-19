(() => {
  const root = document.querySelector('.visual-home');
  if (!root) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scenes = [...root.querySelectorAll('[data-feature-scene]')];
  const visibleScenes = new Set();
  const motionButton = root.querySelector('.illustration-motion');
  const buildScene = root.querySelector('.build-scene');
  let paused = false;
  let buildTimer = null;
  let buildChosen = false;
  let phaseIndex = 1;
  const phases = {
    build: ['Working in a build copy', 'Building the optional invite step', 'Illustration · original project unchanged'],
    review: ['Invite flow checked', 'Ready for your review', 'Review the changes before applying'],
    apply: ['Review approved', 'Changes applied after approval', 'Illustrated result']
  };
  function showBuild(phase, userInitiated = false) {
    buildScene.dataset.buildPhase = phase;
    buildScene.querySelector('.build-outcome').setAttribute('aria-live', userInitiated ? 'polite' : 'off');
    buildScene.querySelectorAll('[data-build-step]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.buildStep === phase));
    });
    ['status', 'outcome', 'detail'].forEach((field, index) => {
      buildScene.querySelector(`[data-build-${field}]`).textContent = phases[phase][index];
    });
  }
  function updateMotion() {
    const enabled = !paused && !reducedMotion.matches;
    root.classList.toggle('motion-enabled', enabled);
    root.classList.toggle('motion-stopped', !enabled);
    motionButton.setAttribute('aria-pressed', String(!enabled));
    motionButton.textContent = enabled ? 'Ⅱ Pause illustrations' : '▷ Play illustrations';
    motionButton.disabled = reducedMotion.matches;
    if (reducedMotion.matches) motionButton.textContent = 'Reduced motion enabled';
    scenes.forEach(scene => scene.classList.toggle('is-playing', enabled && !document.hidden && visibleScenes.has(scene)));
    clearInterval(buildTimer);
    buildTimer = null;
    if (enabled && !document.hidden && visibleScenes.has(buildScene) && !buildChosen) {
      buildTimer = setInterval(() => {
        phaseIndex = (phaseIndex + 1) % 3;
        showBuild(['build', 'review', 'apply'][phaseIndex]);
      }, 3500);
    }
  }
  motionButton.addEventListener('click', () => { paused = !paused; updateMotion(); });
  reducedMotion.addEventListener('change', updateMotion);
  document.addEventListener('visibilitychange', updateMotion);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.isIntersecting ? visibleScenes.add(entry.target) : visibleScenes.delete(entry.target));
      updateMotion();
    }, { threshold: 0.12 });
    scenes.forEach(scene => observer.observe(scene));
  } else {
    scenes.forEach(scene => visibleScenes.add(scene));
  }
  const buds = {
    builder: ['Orbit', 'I found the brief. I’ll build the invite flow from it.', 'Invite flow ready for review', 'builder'],
    designer: ['Pixel', 'I checked the handoff. The invite step can wait.', 'Invite layout reviewed', 'designer'],
    research: ['Scout', 'The team already decided this. Here’s the source.', 'Decision linked to its source', 'research']
  };
  const tabs = [...root.querySelectorAll('[data-bud-demo]')];
  function chooseBud(tab) {
    const [name, response, deliverable, look] = buds[tab.dataset.budDemo];
    tabs.forEach(button => {
      const selected = button === tab;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
    });
    root.querySelector('#bud-role-scene').setAttribute('aria-labelledby', tab.id);
    root.querySelector('.bud-portrait > .site-bud').className = `site-bud look-${look}`;
    root.querySelector('[data-bud-name]').textContent = name;
    root.querySelector('[data-bud-response]').textContent = response;
    root.querySelector('[data-bud-deliverable]').textContent = deliverable;
    if (!reducedMotion.matches && !paused) {
      root.querySelector('.bud-output').animate([{ opacity: 0.4, transform: 'translateY(5px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 240, easing: 'ease-out' });
    }
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => chooseBud(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      chooseBud(tabs[next]);
      tabs[next].focus();
    });
  });
  buildScene.querySelectorAll('[data-build-step]').forEach(button => button.addEventListener('click', () => {
    buildChosen = true;
    showBuild(button.dataset.buildStep, true);
    updateMotion();
  }));
  updateMotion();
})();
