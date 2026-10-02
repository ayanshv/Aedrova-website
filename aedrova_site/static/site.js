'use strict';
const $ = (selector) => document.querySelector(selector);
const storage = {get(key, fallback=null){try{return JSON.parse(localStorage.getItem(key)) ?? fallback;}catch{return fallback;}},set(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{}}};
const theme = storage.get('aedrova-theme',matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
document.documentElement.dataset.theme=theme;
document.querySelectorAll('.theme-toggle').forEach(button=>button.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;storage.set('aedrova-theme',next);}));

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
  matchMedia('(min-width: 701px)').addEventListener('change',event=>{if(event.matches&&!menu.hidden)setMenu(false);});
}

if(!matchMedia('(prefers-reduced-motion: reduce)').matches && 'IntersectionObserver' in window){document.documentElement.classList.add('js-motion');const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target);}}),{threshold:.08});document.querySelectorAll('.reveal').forEach(element=>observer.observe(element));}
let toastTimer;function notice(message){const toast=$('.toast');toast.textContent=message;toast.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('visible'),6500);}
let csrf='';async function api(path,body){const response=await fetch(path,{credentials:'same-origin',method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});let data;try{data=await response.json();}catch{throw new Error('The service did not respond. Please try again.');}if(!response.ok)throw new Error(data.error||data.detail||'Could not complete this request. Please retry.');return data;}
async function busy(button,operation){const text=button.textContent;button.disabled=true;button.textContent='One moment…';try{await operation();}catch(error){notice(error.message);}finally{button.disabled=false;button.textContent=text;}}
const params=new URLSearchParams(location.search);if(['weekly','monthly'].includes(params.get('plan')))storage.set('aedrova-plan',params.get('plan'));
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
  function show(){
    fields.forEach((field,index)=>field.hidden=index!==step);
    document.querySelectorAll('.wizard-progress span').forEach((span,index)=>span.classList.toggle('done',index<=step));
    $('.wizard-progress').setAttribute('aria-label',`Question ${step+1} of ${fields.length}`);
    $('#wizard-back').hidden=step===0;
    $('#wizard-next').innerHTML=step===lastStep?'See my plans <span>↗</span>':'Continue <span>→</span>';
    const heading=fields[step].querySelector('h2');
    heading.tabIndex=-1;heading.focus({preventScroll:true});save();
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
  $('#wizard-back').addEventListener('click',()=>{if(step>0){step--;show();}});
  $('#wizard-next').addEventListener('click',()=>{if(step===lastStep){save();location.href='/plans';}else{step++;show();}});
  form.addEventListener('submit',event=>{event.preventDefault();$('#wizard-next').click();});
  show();
}
const inquiry=$('#enterprise-form');if(inquiry)inquiry.addEventListener('submit',event=>{event.preventDefault();busy(inquiry.querySelector('button[type=submit]'),async()=>{const body=Object.fromEntries(new FormData(inquiry));await api('/api/inquiries',body);inquiry.hidden=true;$('#inquiry-success').hidden=false;$('#inquiry-success').tabIndex=-1;$('#inquiry-success').focus();});});
if($('#workspace')){let selected='',spaces=[],checkoutReady=false;const select=$('#workspace');const status=$('#account-status');const plan=storage.get('aedrova-plan','monthly');$('#selected-plan').textContent=plan==='weekly'?'Weekly · $10/week, renews until cancelled. Review details before paying on Stripe.':'Monthly · $49/month, renews until cancelled. Review details before paying on Stripe.';async function balance(){selected=select.value;storage.set('aedrova-workspace',selected);$('#checkout').disabled=!selected||!checkoutReady;$('#portal').disabled=!selected;if(!selected){status.textContent='Create your first workspace to continue. Signing in never charges your card.';$('#balance').hidden=true;return;}const entry=spaces.find(space=>space.id===selected);const canManage=['owner','admin'].includes(entry?.role);$('#checkout').disabled=!canManage||!checkoutReady;$('#portal').disabled=!canManage;const data=await api('/api/balance/'+encodeURIComponent(selected));$('#balance').replaceChildren();if(data.status==='active'){for(const [label,value] of [['AI remaining',data.available],['Included usage this period',data.spent],['Purchased credit balance',data.credit_balance||0]]){const div=document.createElement('div');const small=document.createElement('small');small.textContent=label;const strong=document.createElement('strong');strong.textContent='$'+(value/1e6).toFixed(2);div.append(small,strong);$('#balance').append(div);}$('#balance').hidden=false;$('#topup').disabled=!canManage;status.textContent='Your '+data.plan+' subscription is active. Run your builds from the Mac app.';}else{$('#balance').hidden=true;$('#topup').disabled=true;status.textContent=checkoutReady?'Choose your plan and continue to Stripe to review every detail before paying.':'Paid beta checkout is being prepared. No payment has been taken. Your workspace is ready for the Mac app.';}}async function load(){const session=await api('/api/session');csrf=session.csrf;checkoutReady=session.checkout_enabled;$('#topup').hidden=!session.topup_enabled;spaces=await api('/api/workspaces');select.replaceChildren();if(!spaces.length){const option=document.createElement('option');option.value='';option.textContent='Your first workspace';select.append(option);}for(const space of spaces){const option=document.createElement('option');option.value=space.id;option.textContent=space.name+' · '+space.role;select.append(option);}const saved=params.get('workspace')||storage.get('aedrova-workspace');if(spaces.some(space=>space.id===saved))select.value=saved;await balance();}select.addEventListener('change',()=>balance().catch(error=>notice(error.message)));$('#create-workspace').addEventListener('click',event=>busy(event.currentTarget,async()=>{const name=$('#new-workspace').value.trim();if(!name)throw new Error('Give your workspace a name first.');const intro=storage.get('aedrova-intro',{});const nickname=/^[A-Za-z0-9][A-Za-z0-9 _-]{0,31}$/.test((intro.nickname||'').trim())?intro.nickname.trim():'Aedrova';const result=await api('/api/workspaces',{name,nickname});storage.set('aedrova-workspace',result.id);$('#new-workspace').value='';await load();notice('Your team’s workspace is ready.');}));$('#checkout').addEventListener('click',event=>busy(event.currentTarget,async()=>{const result=await api('/api/checkout',{workspace:selected,plan,request_id:crypto.randomUUID()});const target=new URL(result.url);if(target.protocol!=='https:'||target.hostname!=='checkout.stripe.com')throw new Error('Checkout returned an unexpected address.');location.href=target.href;}));$('#portal').addEventListener('click',event=>busy(event.currentTarget,async()=>{const result=await api('/api/portal/'+encodeURIComponent(selected),{});const target=new URL(result.url);if(target.protocol!=='https:'||target.hostname!=='billing.stripe.com')throw new Error('Subscription management returned an unexpected address.');location.href=target.href;}));$('#topup').addEventListener('click',event=>busy(event.currentTarget,async()=>{const result=await api('/api/topup',{workspace:selected,plan:'ai_credits',request_id:crypto.randomUUID()});const target=new URL(result.url);if(target.protocol!=='https:'||target.hostname!=='checkout.stripe.com')throw new Error('Checkout returned an unexpected address.');location.href=target.href;}));$('#logout').addEventListener('click',event=>busy(event.currentTarget,async()=>{await api('/api/logout',{});location.href='/account';}));load().catch(error=>{status.textContent=error.message;$('#checkout').disabled=true;$('#portal').disabled=true;});}
