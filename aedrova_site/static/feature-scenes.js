(() => {
  const root = document.querySelector('.visual-home');
  if (!root) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scenes = [...root.querySelectorAll('[data-feature-scene]')];
  const visibleScenes = new Set();
  const motionButton = root.querySelector('.illustration-motion');
  const buildScene = root.querySelector('.build-scene');
  let paused = false;
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
    root.classList.toggle('motion-enabled', !reducedMotion.matches);
    root.classList.toggle('motion-paused', !enabled);
    motionButton.setAttribute('aria-pressed', String(!enabled));
    motionButton.textContent = enabled ? 'Ⅱ Pause illustrations' : '▷ Play illustrations';
    motionButton.disabled = reducedMotion.matches;
    if (reducedMotion.matches) motionButton.textContent = 'Reduced motion enabled';
    scenes.forEach(scene => scene.classList.toggle('is-playing', enabled && !document.hidden && visibleScenes.has(scene)));
  }
  motionButton.addEventListener('click', () => { paused = !paused; updateMotion(); });
  reducedMotion.addEventListener('change', updateMotion);
  document.addEventListener('visibilitychange', updateMotion);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          visibleScenes.add(entry.target);
          entry.target.classList.add('has-entered');
        } else {
          visibleScenes.delete(entry.target);
        }
      });
      updateMotion();
    }, { threshold: 0.12 });
    scenes.forEach(scene => observer.observe(scene));
  } else {
    scenes.forEach(scene => { visibleScenes.add(scene); scene.classList.add('has-entered'); });
  }
  buildScene.querySelectorAll('[data-build-step]').forEach(button => button.addEventListener('click', () => {
    showBuild(button.dataset.buildStep, true);
    updateMotion();
  }));
  updateMotion();
})();
