'use strict';
const $ = (selector) => document.querySelector(selector);
const storage = {get(key, fallback=null){try{return JSON.parse(localStorage.getItem(key)) ?? fallback;}catch{return fallback;}},set(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{}}};
const savedTheme = storage.get('aedrova-theme');
const theme = savedTheme === 'dark' ? 'dark' : 'light';
document.documentElement.dataset.theme=theme;
document.querySelectorAll('.theme-toggle').forEach(button=>button.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;storage.set('aedrova-theme',next);}));
document.querySelectorAll('.desktop-nav a,.mobile-menu a').forEach(link=>{if(link.getAttribute('href')===location.pathname&&location.pathname!=='/')link.setAttribute('aria-current','page');});

// Homepage visits begin at the hero; explicit section links retain their target.
if(document.body.classList.contains('home-page')){
  history.scrollRestoration='manual';
  function landOnHero(){
    if(!location.hash){window.scrollTo({top:0,left:0,behavior:'instant'});return;}
    try{document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({behavior:'instant',block:'start'});}catch{}
  }
  landOnHero();
  window.addEventListener('pageshow',()=>requestAnimationFrame(landOnHero));
}else history.scrollRestoration='auto';

// One local overhead loop. Browser-blocked playback always exposes a play button.
const cinema=$('.cinema');
if(cinema){
  const video=cinema.querySelector('.scene');
  const motion=cinema.querySelector('.motion-toggle');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let visible=true,paused=reduced.matches,blocked=false,pending=false;
  video.muted=true;video.defaultMuted=true;video.playsInline=true;
  function renderMotion(){
    const stopped=paused||blocked;
    cinema.classList.toggle('motion-paused',stopped);
    motion.textContent=stopped?'Play background ▷':'Pause motion Ⅱ';
    motion.setAttribute('aria-label',stopped?'Play background video':'Pause background video');
  }
  function syncMotion(){
    if(!paused&&visible&&!document.hidden){
      if(!video.hasAttribute('src')){video.src=video.dataset.src;video.load();}
      if(!pending){
        pending=true;
        video.play().catch(error=>{
          if(error.name!=='AbortError'&&!paused&&visible&&!document.hidden){blocked=true;renderMotion();}
        }).finally(()=>{pending=false;});
      }
    }else video.pause();
    renderMotion();
  }
  video.addEventListener('playing',()=>{blocked=false;video.classList.toggle('active',true);renderMotion();});
  video.addEventListener('error',()=>{video.classList.remove('active');blocked=true;renderMotion();});
  motion.addEventListener('click',()=>{
    paused=blocked?false:!paused;blocked=false;
    if(video.error){video.src=video.dataset.src;video.load();}
    syncMotion();
  });
  document.addEventListener('visibilitychange',syncMotion);
  reduced.addEventListener('change',event=>{paused=event.matches;syncMotion();});
  if('IntersectionObserver' in window)new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;syncMotion();},{threshold:.05}).observe(cinema);
  syncMotion();
}
const menuButton=$('.menu-toggle'),menu=$('#mobile-menu');
if(menuButton&&menu){
  const behind=[$('main'),$('footer'),$('.nav .wordmark')];
  function setMenu(open){
    menu.hidden=!open;menuButton.setAttribute('aria-expanded',String(open));menuButton.setAttribute('aria-label',open?'Close navigation':'Open navigation');document.body.classList.toggle('menu-open',open);
    behind.forEach(element=>{if(element)element.inert=open;});
    if(open)menu.querySelector('a').focus();else menuButton.focus();
  }
  menuButton.addEventListener('click',()=>setMenu(menu.hidden));
  menu.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>setMenu(false)));
  document.addEventListener('keydown',event=>{
    if(menu.hidden)return;
    if(event.key==='Escape'){event.preventDefault();setMenu(false);}
    if(event.key==='Tab'){
      const controls=[menuButton,...menu.querySelectorAll('a,button')];const first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  matchMedia('(min-width: 961px)').addEventListener('change',event=>{if(event.matches&&!menu.hidden)setMenu(false);});
}

if(!matchMedia('(prefers-reduced-motion: reduce)').matches && 'IntersectionObserver' in window){document.documentElement.classList.add('js-motion');const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target);}}),{threshold:.08});document.querySelectorAll('.reveal').forEach(element=>observer.observe(element));}
let toastTimer;function notice(message){const toast=$('.toast');toast.textContent=message;toast.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('visible'),6500);}
let csrf='';async function api(path,body){const response=await fetch(path,{credentials:'same-origin',method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});let data;try{data=await response.json();}catch{throw new Error('The service did not respond. Please try again.');}if(!response.ok)throw new Error(data.error||data.detail||'Could not complete this request. Please retry.');return data;}
async function busy(button,operation){const children=[...button.childNodes];button.disabled=true;button.setAttribute('aria-busy','true');button.textContent='One moment…';try{await operation();}catch(error){notice(error.message);}finally{button.disabled=false;button.removeAttribute('aria-busy');button.replaceChildren(...children);}}
const params=new URLSearchParams(location.search);if(['monthly','annual'].includes(params.get('plan')))storage.set('aedrova-plan',params.get('plan'));
if(params.has('cancelled'))notice('Checkout cancelled. No new subscription was confirmed.');if(params.has('login_error'))notice('Google sign-in did not finish. Please try again.');
const form=$('#onboarding-form');
if(form){
  const saved=storage.get('aedrova-intro',{});
  const state=saved&&typeof saved==='object'&&!Array.isArray(saved)?saved:{};
  // Every visit begins with an introduction; retain answers, never restore the old page.
  let step=0;
  const fields=[...form.querySelectorAll('fieldset')];
  const lastStep=fields.length-1;
  const nickname=$('#nickname'),firstWin=$('#first-win');
  nickname.value=state.nickname||'Aedrova';
  firstWin.value=state.first_win||'';
  function save(){
    delete state.step;
    state.nickname=nickname.value;
    state.first_win=firstWin.value;
    storage.set('aedrova-intro',state);
  }
  function show(advance=false){
    fields.forEach((field,index)=>field.hidden=index!==step);
    document.querySelectorAll('.wizard-progress span').forEach((span,index)=>span.classList.toggle('done',index<=step));
    $('.wizard-progress').setAttribute('aria-label',`Question ${step+1} of ${fields.length}`);
    $('#wizard-back').hidden=step===0;
    $('#wizard-next').innerHTML=step===lastStep?'See my plans <span>↗</span>':'Continue <span>→</span>';
    const heading=fields[step].querySelector('h2');
    heading.tabIndex=-1;heading.focus({preventScroll:true});
    if(advance)fields[step].scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
    save();
  }
  form.querySelectorAll('.option-grid').forEach(group=>{
    const response=group.closest('fieldset').querySelector('.intro-response');
    group.querySelectorAll('button').forEach(button=>{
      const selected=state[group.dataset.answer]===button.textContent;
      button.setAttribute('aria-pressed',String(selected));
      if(selected&&response)response.textContent=button.dataset.response||'';
      button.addEventListener('click',()=>{
        state[group.dataset.answer]=button.textContent;
        group.querySelectorAll('button').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
        if(response)response.textContent=button.dataset.response||'';
        save();
      });
    });
  });
  nickname.addEventListener('input',save);firstWin.addEventListener('input',save);
  $('#wizard-back').addEventListener('click',()=>{if(step>0){step--;show(true);}});
  $('#wizard-next').addEventListener('click',()=>{if(step===lastStep){save();location.href='/plans';}else{step++;show(true);}});
  form.addEventListener('submit',event=>{event.preventDefault();$('#wizard-next').click();});
  show();
}
const inquiry=$('#enterprise-form');if(inquiry)inquiry.addEventListener('submit',event=>{event.preventDefault();busy(inquiry.querySelector('button[type=submit]'),async()=>{const body=Object.fromEntries(new FormData(inquiry));await api('/api/inquiries',body);inquiry.hidden=true;$('#inquiry-success').hidden=false;$('#inquiry-success').tabIndex=-1;$('#inquiry-success').focus();});});
if ($('#workspace')) {
  let selected = '', spaces = [], checkoutReady = false, testMode = false;
  let balanceRevision = 0;
  const select = $('#workspace'), status = $('#account-status'), planSelect = $('#billing-plan');
  let plan = storage.get('aedrova-plan', 'monthly');
  if (!['monthly', 'annual'].includes(plan)) plan = 'monthly';
  planSelect.value = plan;
  function renderPlan() {
    plan = planSelect.value;
    storage.set('aedrova-plan', plan);
    const address = new URL(location.href); address.searchParams.set('plan', plan);
    history.replaceState(null, '', address.href);
    $('#selected-plan').textContent = planSelect.selectedOptions[0].dataset.description +
      ', renews until cancelled. Review details before paying on Stripe.';
  }
  $('#activate-free').addEventListener('click', () => busy($('#activate-free'), async () => { await api('/api/free/' + encodeURIComponent(select.value), {}); await balance(); }));
  renderPlan();
  planSelect.addEventListener('change', renderPlan);
  function checkoutKey() {
    const key = 'aedrova-checkout-' + selected + '-' + plan;
    let value = storage.get(key);
    if (!value || value.expires < Date.now()) {
      value = {id: crypto.randomUUID(), expires: Date.now() + 29 * 60 * 1000};
      storage.set(key, value);
    }
    return value.id;
  }
  async function balance() {
    const revision = ++balanceRevision;
    selected = select.value;
    storage.set('aedrova-workspace', selected);
    const address = new URL(location.href);
    if (selected) address.searchParams.set('workspace', selected);
    else address.searchParams.delete('workspace');
    history.replaceState(null, '', address.href);
    $('#checkout').disabled = true;
    $('#portal').disabled = true;
    $('#topup').disabled = true;
    $('#balance').hidden = true;
    if (!selected) {
      status.textContent = 'Create your first workspace to continue. Signing in never charges your card.';
      return;
    }
    const entry = spaces.find(space => space.id === selected);
    const canManage = ['owner', 'admin'].includes(entry?.role);
    status.textContent = 'Checking this workspace…';
    const data = await api('/api/balance/' + encodeURIComponent(selected));
    if (revision !== balanceRevision) return;
    $('#balance').replaceChildren();
    $('#portal').disabled = !canManage || !data.has_billing || ['no_plan', 'pending'].includes(data.status);
    $('#checkout').disabled = !canManage || !checkoutReady || (data.status === 'active' && data.plan !== 'free');
    $('#activate-free').disabled = $('#activate-free').dataset.enabled !== 'true' || !canManage || data.status === 'active';
    if (data.status === 'active') {
      const monthlyBudget = Math.max(1, data.monthly_budget || data.allowance);
      for (const [label, value] of [['Monthly AI available', Math.min(100, Math.max(0, Math.round(100 * (monthlyBudget - (data.monthly_spent || 0)) / monthlyBudget)))], ['Monthly AI used', Math.min(100, Math.round(100 * (data.monthly_spent || 0) / monthlyBudget))]]) {
        const div = document.createElement('div'), small = document.createElement('small'), strong = document.createElement('strong');
        small.textContent = label; strong.textContent = value + '%';
        div.append(small, strong); $('#balance').append(div);
      }
      const reset = document.createElement('p');
      reset.textContent = 'Monthly reset: ' + new Date((data.reset_at || data.period_end) * 1000).toLocaleDateString() + ' · ' + (data.monthly_requests || 0) + '/' + (data.monthly_request_limit || 0) + ' model requests';
      $('#balance').append(reset);
      $('#balance').hidden = false;
      $('#topup').disabled = !canManage || data.plan === 'free';
      status.textContent = testMode ? 'Test subscription confirmed. Paid AI remains disabled in this sandbox.' :
        'Your ' + ({free:'Free',monthly:'Pro',annual:'Team'}[data.plan] || data.plan) + ' plan is active. ' + (data.available <= (data.monthly_budget || data.allowance) * 0.1 ? 'Your AI allowance is nearly used. Review your plan or wait for the monthly reset. Human chat stays available.' : 'Run your builds from the Mac app.');
    } else {
      status.textContent = !canManage ? 'Your workspace owner or admin manages the subscription.' :
        checkoutReady ? 'Review your selected plan on Stripe before confirming. ' + (testMode ? 'Test payments only.' : '') :
        'Paid beta checkout is being prepared. No payment has been taken. Your workspace is ready for the Mac app.';
    }
  }
  async function load(preferredWorkspace = '') {
    const session = await api('/api/session');
    csrf = session.csrf; checkoutReady = session.checkout_enabled; testMode = session.stripe_test_mode;
    $('#topup').hidden = !session.topup_enabled;
    spaces = await api('/api/workspaces'); select.replaceChildren();
    if (!spaces.length) {
      const option = document.createElement('option'); option.value = ''; option.textContent = 'Your first workspace'; select.append(option);
    }
    for (const space of spaces) {
      const option = document.createElement('option'); option.value = space.id; option.textContent = space.name + ' · ' + space.role; select.append(option);
    }
    const saved = preferredWorkspace || new URL(location.href).searchParams.get('workspace') || storage.get('aedrova-workspace');
    if (spaces.some(space => space.id === saved)) select.value = saved;
    await balance();
  }
  select.addEventListener('change', () => balance().catch(error => { status.textContent = error.message; }));
  $('#create-workspace').addEventListener('click', event => busy(event.currentTarget, async () => {
    const name = $('#new-workspace').value.trim();
    if (!name) throw new Error('Give your workspace a name first.');
    const intro = storage.get('aedrova-intro', {});
    const nickname = /^[A-Za-z0-9][A-Za-z0-9 _-]{0,31}$/.test((intro.nickname || '').trim()) ? intro.nickname.trim() : 'Aedrova';
    const result = await api('/api/workspaces', {name, nickname});
    storage.set('aedrova-workspace', result.id); $('#new-workspace').value = '';
    await load(result.id); notice('Your team’s workspace is ready.');
  }));
  function redirectStripe(value, hostname) {
    const target = new URL(value);
    if (target.protocol !== 'https:' || target.hostname !== hostname || target.username || target.password)
      throw new Error('Billing returned an unexpected address.');
    location.href = target.href;
  }
  $('#checkout').addEventListener('click', event => busy(event.currentTarget, async () => {
    const result = await api('/api/checkout', {workspace: selected, plan, request_id: checkoutKey()});
    redirectStripe(result.url, 'checkout.stripe.com');
  }));
  $('#portal').addEventListener('click', event => busy(event.currentTarget, async () => {
    const result = await api('/api/portal/' + encodeURIComponent(selected), {}); redirectStripe(result.url, 'billing.stripe.com');
  }));
  $('#topup').addEventListener('click', event => busy(event.currentTarget, async () => {
    const result = await api('/api/topup', {workspace: selected, plan: 'ai_credits', request_id: crypto.randomUUID()});
    redirectStripe(result.url, 'checkout.stripe.com');
  }));
  $('#logout').addEventListener('click', event => busy(event.currentTarget, async () => { await api('/api/logout', {}); location.href = '/account'; }));
  load().catch(error => {
    if (select.options.length === 1 && select.options[0].textContent === 'Loading your spaces…') select.options[0].textContent = 'Workspace unavailable';
    status.textContent = error.message; $('#checkout').disabled = true; $('#portal').disabled = true;
  });
}
if ($('[data-checkout-return]')) {
  let attempts = 0;
  const status = $('#payment-status'), button = $('#check-payment');
  async function checkPayment() {
    const reference = params.get('session_id');
    if (!reference) { status.textContent = 'Sign in to your account to view subscription status.'; button.hidden = true; return; }
    const data = await api('/api/checkout/status?session_id=' + encodeURIComponent(reference));
    storage.set('aedrova-workspace', data.workspace);
    const accountLink = $('#payment-account');
    accountLink.href = '/account?workspace=' + encodeURIComponent(data.workspace);
    if (data.billing_status === 'active') {
      status.textContent = data.stripe_test_mode ? 'Test subscription confirmed. Paid AI remains disabled in this sandbox.' : 'Subscription confirmed. Your workspace is ready.';
      button.hidden = true;
    } else if (data.checkout_status === 'expired') {
      status.textContent = 'This checkout expired. Return to your account to start again.';
    } else {
      status.textContent = data.payment_status === 'paid' ? 'Payment received. Waiting for secure subscription confirmation…' : 'Payment is not confirmed yet. Return to your account or check again.';
      if (++attempts < 6) setTimeout(() => checkPayment().catch(error => { status.textContent = error.message; }), 3000);
    }
  }
  button.addEventListener('click', event => busy(event.currentTarget, checkPayment));
  checkPayment().catch(() => { status.textContent = 'Sign in to your account to check this payment. Paid access is never enabled by this return page alone.'; });
}

const waitlistForm=$('#waitlist-form');
if(waitlistForm){
  waitlistForm.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!waitlistForm.reportValidity())return;
    const submit=waitlistForm.querySelector('button[type=submit]'),error=$('#waitlist-error');
    if(submit.disabled)return;
    error.hidden=true;submit.disabled=true;submit.setAttribute('aria-busy','true');
    try{
      const fields=new FormData(waitlistForm);
      await api('/api/waitlist',{email:String(fields.get('email')).trim(),consent:fields.get('consent')==='on'});
      $('#waitlist-entry').hidden=true;$('#waitlist-success').hidden=false;$('#waitlist-success').focus();
      waitlistForm.reset();
    }catch(problem){error.textContent=problem.message;error.hidden=false;}
    finally{submit.disabled=false;submit.removeAttribute('aria-busy');}
  });
}
