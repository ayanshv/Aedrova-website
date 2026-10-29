/* Per-reader display translation. Never rewrites inputs, IDs, links or submitted text. */
(() => {
  'use strict';
  const languages={en:'English',hi:'हिन्दी',es:'Español',fr:'Français',de:'Deutsch',pt:'Português',it:'Italiano',ja:'日本語',ko:'한국어',zh:'中文',ar:'العربية',ur:'اردو',bn:'বাংলা',ta:'தமிழ்',te:'తెలుగు',id:'Bahasa Indonesia',vi:'Tiếng Việt',th:'ไทย',tr:'Türkçe',ru:'Русский'};
  const select=document.querySelector('[data-language]'), status=document.querySelector('[data-language-status]');
  if(!select)return;
  for(const [value,name] of Object.entries(languages)){const option=new Option(name,value);select.add(option);}
  const originals=new WeakMap(), rendered=new WeakMap(), attributes=new WeakMap();
  let language='en', csrf='', workspace='', signedIn=false, generation=0, enabled=true, pending=false, timer=null;
  const cache=new Map(), failed=new Set();
  const ignored=node=>node.parentElement?.closest('script,style,code,pre,textarea,option,[data-no-translate],[contenteditable="true"]');
  const setStatus=text=>{if(status.textContent!==text)status.textContent=text;status.hidden=!text;};
  async function request(path,body){
    const response=await fetch(path,{credentials:'same-origin',method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
    if(!response.ok)throw new Error('unavailable');
    return response.json();
  }
  function nodes(){
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT), result=[];
    while(walker.nextNode()){
      const node=walker.currentNode;
      if(ignored(node)||!node.textContent.trim()||node.textContent.length>12000)continue;
      const previous=rendered.get(node),source=previous===node.textContent?originals.get(node):node.textContent;
      originals.set(node,source); result.push([node,source]);
    }
    for(const element of document.body.querySelectorAll('[placeholder],[aria-label],[title],img[alt]')){
      if(element.closest('[data-no-translate],script,style,code,pre'))continue;
      let views=attributes.get(element);if(!views){views=new Map();attributes.set(element,views);}
      for(const name of ['placeholder','aria-label','title','alt']){
        if(!element.hasAttribute(name)||!element.getAttribute(name).trim())continue;
        if(!views.has(name))views.set(name,{get textContent(){return element.getAttribute(name)||'';},set textContent(v){element.setAttribute(name,v);},parentElement:element});
        const proxy=views.get(name),current=proxy.textContent;
        const source=rendered.get(proxy)===current?originals.get(proxy):current;
        originals.set(proxy,source);result.push([proxy,source]);
      }
    }
    return result;
  }
  function paint(){
    const missing=[];
    for(const [node,source] of nodes()){
      const text=language==='en'?source:cache.get(language+'\0'+source.trim());
      if(text!==undefined){
        const value=language==='en'?source:source.replace(source.trim(),text);
        if(node.textContent!==value)node.textContent=value;
        rendered.set(node,value);
      }else {if(node.textContent!==source)node.textContent=source;rendered.set(node,source);if(!failed.has(language+'\0'+source.trim()))missing.push(source.trim());}
    }
    return [...new Set(missing)];
  }
  async function translate(){
    if(pending||language==='en')return;
    const missing=paint();
    if(!missing.length)return;
    if(!signedIn||!workspace){setStatus('Navigation translated where available. Sign in for full-page AI translation.');return;}
    const stamp=generation, target=language;
    pending=true;setStatus('Translating… Original text stays available.');
    try{
      while(stamp===generation){
        const batch=[];let size=0;
        for(const source of paint()){
          const bytes=new TextEncoder().encode(source).length;
          if(bytes>24000){failed.add(target+'\0'+source);continue;}
          if(batch.length&&(batch.length===12||size+bytes>24000))break;
          batch.push(source);size+=bytes;
        }
        if(!batch.length)break;
        const result=await request('/api/translations',{workspace,language:target,texts:batch});
        if(stamp!==generation)return;
        if(!Array.isArray(result.texts)||result.texts.length!==batch.length)throw new Error('invalid');
        result.texts.forEach((value,index)=>{if(typeof value!=='string')throw new Error('invalid');cache.set(target+'\0'+batch[index],value);});
        if(cache.size>3000){const entry=cache.keys().next().value;cache.delete(entry);}
        paint();
      }
      if(stamp===generation)setStatus('AI translation · Select English to view original text.');
    }catch{if(stamp===generation){paint().forEach(source=>failed.add(target+'\0'+source));setStatus('Some text is shown in its original language. Translation is unavailable.');}}
    finally{pending=false; if(stamp!==generation)schedule();}
  }
  function schedule(){clearTimeout(timer);timer=setTimeout(translate,350);}
  async function choose(value,persist=false){
    language=Object.hasOwn(languages,value)?value:'en';select.value=language;generation++;failed.clear();
    document.documentElement.lang=language;document.documentElement.dir=['ar','ur'].includes(language)?'rtl':'ltr';
    if(typeof storage!=='undefined')storage.set('aedrova-language',language);
    if(language==='hi')try{const dictionary=await fetch('/static/locales/hi.json').then(r=>r.json());for(const [key,value] of Object.entries(dictionary))cache.set('hi\0'+key,value);}catch{}
    paint();setStatus('');schedule();
    if(persist&&signedIn)try{await request('/api/language',{language,translate:enabled});}catch{setStatus('Language changed here. Could not save to your account.');}
  }
  select.addEventListener('change',()=>choose(select.value,true));
  const observer=new MutationObserver(schedule);observer.observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:["placeholder","aria-label","title","alt"]});
  (async()=>{
    let initial=typeof storage!=='undefined'?storage.get('aedrova-language','en'):'en';
    try{
      const session=await request('/api/session');csrf=session.csrf;
      const [preferences,spaces]=await Promise.all([request('/api/language'),request('/api/workspaces')]);
      signedIn=true;initial=preferences.language;enabled=preferences.translate;
      workspace=spaces[0]?.id||'';
    }catch{}
    await choose(initial);
  })();
  document.querySelector('#logout')?.addEventListener('click',()=>{cache.clear();failed.clear();workspace='';signedIn=false;choose('en');});
})();
