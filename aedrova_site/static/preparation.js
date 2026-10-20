'use strict';
// Shared by website onboarding and billing opened from the desktop app.
// Completion reflects a loaded page or an actual checkout response, never a fake build.
(() => {
  const dialog = document.getElementById('preparation');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const title = document.getElementById('preparation-title');
  const copy = document.getElementById('preparation-copy');
  const status = document.getElementById('preparation-status');
  const action = document.getElementById('preparation-continue');
  const rows = [...dialog.querySelectorAll('li')];
  let active = false, controller, previousFocus;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  function step(index, message) {
    rows.forEach((row, i) => {
      row.dataset.state = i < index ? 'complete' : i === index ? 'current' : 'pending';
      if (i === index) row.setAttribute('aria-current', 'step');
      else row.removeAttribute('aria-current');
    });
    status.textContent = message;
  }
  function close() {
    active = false;
    controller?.abort();
    controller = null;
    if (dialog.open) dialog.close();
    previousFocus?.focus({preventScroll: true});
  }
  function start(kind) {
    if (active) return false;
    active = true;
    previousFocus = document.activeElement;
    const checkout = kind === 'checkout';
    title.textContent = checkout ? 'Getting your team’s order ready.' : 'Bringing your setup together.';
    copy.textContent = checkout
      ? 'One subscription for your team. You’ll review everything on Stripe before paying.'
      : 'A space for your people, your tools, and what comes next.';
    const labels = checkout
      ? ['Your team’s selection', 'Preparing secure checkout', 'Opening Stripe for your review']
      : ['Bringing your choices together', 'Getting your plan options ready', 'Ready for your next step'];
    rows.forEach((row, i) => { row.querySelector('.preparation-label').textContent = labels[i]; });
    action.hidden = checkout;
    action.textContent = 'Continue to plans →';
    step(0, checkout ? 'Your selection is ready.' : 'Keeping your team at the center.');
    dialog.showModal();
    title.focus({preventScroll: true});
    return true;
  }
  action.addEventListener('click', () => { close(); location.assign('/plans'); });
  dialog.addEventListener('cancel', event => {
    // A submitted checkout request must finish before another can be submitted.
    if (action.hidden) event.preventDefault();
    else close();
  });
  window.addEventListener('pagehide', close);
  window.addEventListener('pageshow', event => { if (event.persisted) close(); });
  window.AedrovaPreparation = {
    async plans() {
      if (!start('plans')) return;
      const request = new AbortController();
      controller = request;
      const timeout = setTimeout(() => request.abort(), 6000);
      try {
        // Warm the real plan page; do not send the optional introduction answers.
        const loaded = fetch('/plans', {credentials: 'same-origin', signal: request.signal})
          .then(response => { if (!response.ok) throw new Error('Plans unavailable'); return response.text(); });
        // Attach rejection immediately, including when an early network failure occurs.
        const ready = Promise.all([loaded, pause(900)]);
        step(1, 'Getting your team’s plan options ready.');
        await ready;
        if (!active || controller !== request) return;
        step(2, 'Your plans are ready.');
        await pause(400);
        if (!active || controller !== request) return;
        close();
        location.assign('/plans');
      } catch {
        if (!active || controller !== request) return;
        title.textContent = 'Let’s take the next step.';
        status.textContent = 'The plan page is taking a moment. Continue to open it directly.';
        rows.forEach(row => { row.dataset.state = 'pending'; row.removeAttribute('aria-current'); });
      } finally {
        clearTimeout(timeout);
      }
    },
    async checkout(operation) {
      if (!start('checkout')) return;
      const request = new AbortController();
      controller = request;
      const timeout = setTimeout(() => request.abort(), 20000);
      try {
        step(1, 'Preparing your secure checkout. No payment has been taken.');
        // The caller validates the returned Stripe URL before this step completes.
        const target = await operation(request.signal);
        step(2, 'Opening Stripe. Review your order before confirming.');
        await pause(200);
        close();
        location.assign(target);
      } catch (error) {
        const timedOut = request.signal.aborted;
        close();
        if (timedOut) throw new Error('Checkout took longer than expected. Please retry. No payment was confirmed.');
        throw error;
      } finally {
        clearTimeout(timeout);
      }
    }
  };
})();
