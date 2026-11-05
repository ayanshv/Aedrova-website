(() => {
  const navigation = document.querySelector('.nav');
  if (!navigation) return;

  const controls = [...navigation.querySelectorAll(
    '.wordmark, .desktop-nav > a:not(.button), .theme-toggle, .menu-toggle'
  )];
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const context = canvas.getContext('2d', {willReadFrequently: true});
  const video = document.querySelector('.cinema video');
  const reducedTransparency = matchMedia('(prefers-reduced-transparency: reduce)');
  let scheduled = false;

  function rgba(value) {
    const numbers = value.match(/[\d.]+/g);
    return numbers ? numbers.map(Number) : [0, 0, 0, 0];
  }

  function luminance(color) {
    const channels = color.slice(0, 3).map(value => {
      const channel = value / 255;
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  }

  function textAt(element, x, y) {
    if (!element.matches('h1,h2,h3,h4,h5,h6,p,span,a,label,button,summary,strong,em,li,div')) {
      return false;
    }
    return [...element.childNodes].some(node => {
      if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) return false;
      const range = document.createRange();
      range.selectNode(node);
      return [...range.getClientRects()].some(rect =>
        x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom
      );
    });
  }

  function mediaColor(media, x, y) {
    if (!context) return null;
    const width = media.videoWidth || media.naturalWidth;
    const height = media.videoHeight || media.naturalHeight;
    if (!width || !height) return null;
    const rect = media.getBoundingClientRect();
    const fit = getComputedStyle(media).objectFit;
    const scale = fit === 'cover'
      ? Math.max(rect.width / width, rect.height / height)
      : Math.min(rect.width / width, rect.height / height);
    const left = rect.left + (rect.width - width * scale) / 2;
    const top = rect.top + (rect.height - height * scale) / 2;
    const sourceX = (x - left) / scale;
    const sourceY = (y - top) / scale;
    if (sourceX < 0 || sourceY < 0 || sourceX >= width || sourceY >= height) return null;
    try {
      context.clearRect(0, 0, 1, 1);
      context.drawImage(media, sourceX, sourceY, 1, 1, 0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data];
    } catch {
      return null;
    }
  }

  function sample(x, y) {
    const elements = document.elementsFromPoint(x, y).filter(element =>
      !element.closest('.nav, .nav-glass-defs')
    );
    for (const element of elements) {
      const style = getComputedStyle(element);
      if (textAt(element, x, y)) {
        return {light: luminance(rgba(style.color)), text: true};
      }
      if (element instanceof HTMLImageElement) {
        const color = mediaColor(element, x, y);
        if (color && color[3] > 245) return {light: luminance(color), text: false};
      }
      if (element.classList.contains('cinema')) {
        const media = video && video.readyState >= 2
          ? video : element.querySelector('.scene-poster.active');
        const color = media && mediaColor(media, x, y);
        if (color) {
          return {light: luminance(color.map((value, index) => index < 3 ? value * 0.49 : value)), text: false};
        }
      }
      const color = rgba(style.backgroundColor);
      if (color.length >= 3 && (color[3] ?? 1) > 0.95) {
        return {light: luminance(color), text: false};
      }
    }
    return {light: luminance(rgba(getComputedStyle(document.body).backgroundColor)), text: false};
  }

  function update() {
    scheduled = false;
    if (document.hidden) return;
    const changes = controls.map(control => {
      const rect = control.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      if (reducedTransparency.matches) return {control, ink: '', halo: ''};
      if (document.body.classList.contains('menu-open')) {
        return {control, ink: '#fff', halo: '#000'};
      }
      const samples = [0.2, 0.5, 0.8].map(fraction =>
        sample(rect.left + rect.width * fraction, rect.top + rect.height / 2)
      );
      const text = samples.filter(item => item.text);
      const relevant = text.length ? text : samples;
      const light = relevant.reduce((sum, item) => sum + item.light, 0) / relevant.length;
      const darkInk = light > 0.179;
      return {
        control,
        ink: darkInk ? '#111' : '#fff',
        halo: darkInk ? '#ffffffb3' : '#000000b3'
      };
    });
    for (const change of changes) {
      if (!change) continue;
      change.control.style.setProperty('--navigation-ink', change.ink);
      change.control.style.setProperty('--navigation-halo', change.halo);
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(update);
  }

  addEventListener('scroll', schedule, {passive: true});
  addEventListener('resize', schedule);
  document.addEventListener('load', schedule, true);
  document.addEventListener('visibilitychange', schedule);
  reducedTransparency.addEventListener('change', schedule);
  new MutationObserver(schedule).observe(document.documentElement, {
    attributes: true, attributeFilter: ['data-theme']
  });
  new MutationObserver(schedule).observe(document.body, {
    attributes: true, attributeFilter: ['class']
  });
  if (document.fonts) document.fonts.ready.then(schedule);
  setInterval(() => {
    if (video && !video.paused && video.getBoundingClientRect().bottom > 0) schedule();
  }, 300);
  schedule();
})();
