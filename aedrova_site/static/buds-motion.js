/* Local artwork, eye-only blinks. No model calls, tracking or timers in hidden tabs. */
(() => {
  const eyes = [
    [[257,309,35,79],[349,308,34,77]], [[222,303,36,80],[322,303,36,80]],
    [[181,289,36,80],[281,289,36,80]], [[201,246,34,73],[318,244,34,74]],
    [[175,258,35,75],[267,258,35,75]], [[149,269,34,70],[231,269,34,71]]
  ];
  const looks = ['builder','designer','marketing','finance','research','product'];
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const atlas = new Image();
  const mounted = new Map();
  let timer;
  function mount() {
    document.querySelectorAll('.site-bud,.connected-bud').forEach((el) => {
      if (mounted.has(el)) return;
      const index = looks.findIndex(look => el.classList.contains('look-' + look));
      if (index < 0) return;
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 512;
      canvas.setAttribute('aria-hidden', 'true');
      canvas.style.cssText = 'width:100%;height:100%;display:block;pointer-events:none';
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      el.append(canvas);
      el.style.backgroundImage = 'none';
      const row = {el, canvas, ctx, index, offset: mounted.size * .71, closed: null};
      mounted.set(el, row);
      draw(row, false);
    });
  }
  function draw(row, closed) {
    if (row.closed === closed) return;
    const {ctx, index} = row;
    const sizeX = atlas.naturalWidth / 3, sizeY = atlas.naturalHeight / 2;
    const x0 = index % 3 * sizeX, y0 = Math.floor(index / 3) * sizeY;
    ctx.clearRect(0,0,512,512);
    ctx.drawImage(atlas,x0,y0,sizeX,sizeY,0,0,512,512);
    if (closed) eyes[index].forEach(([x,y,w,h]) => {
      ctx.drawImage(atlas, x0+(x-9)*sizeX/512, y0+y*sizeY/512, 4*sizeX/512, h*sizeY/512, x,y,w,h);
      ctx.drawImage(atlas,x0+x*sizeX/512,y0+y*sizeY/512,w*sizeX/512,h*sizeY/512,x,y+h/2-2,w,4);
    });
    row.closed = closed;
  }
  function schedule() {
    clearInterval(timer);
    mounted.forEach(row => draw(row,false));
    if (motion.matches || document.hidden) return;
    timer = setInterval(() => {
      const seconds = performance.now()/1000;
      mounted.forEach(row => {
        const rect = row.el.getBoundingClientRect();
        if (rect.bottom >= 0 && rect.top <= innerHeight) draw(row, (seconds+row.offset)%4.4 < .18);
      });
    }, 80);
  }
  atlas.onload = () => {
    mount(); schedule();
    new MutationObserver(() => { mount(); }).observe(document.body,{childList:true,subtree:true});
  };
  // Asset failure leaves the original CSS artwork intact.
  atlas.src = '/static/buds-atlas.png';
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', schedule);
})();
