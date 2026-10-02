// Exercise playback failures and recovery without real media or remote services.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function element(){const classes=new Set();return {classes,events:{},attrs:{},dataset:{src:'/static/overhead-pedestrians.mp4'},classList:{toggle(c,on){if(on)classes.add(c);else classes.delete(c);},remove(c){classes.delete(c);}},addEventListener(t,cb){this.events[t]=cb;},setAttribute(k,v){this.attrs[k]=v;},hasAttribute(k){return k==='src'&&Boolean(this.src);},load(){this.error=null;},pause(){this.paused=true;},play(){this.calls=(this.calls||0)+1;return this.reject?Promise.reject(Object.assign(new Error('Blocked'),{name:'NotAllowedError'})):Promise.resolve();}};}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 for(const reduced of [false,true]){
  const video=element(),motion=element(),cinema=element();video.reject=true;
  cinema.querySelector=s=>s==='.scene'?video:motion;
  const document={hidden:false,events:{},addEventListener(t,cb){this.events[t]=cb;}};
  const preference={matches:reduced,addEventListener(t,cb){this.changed=cb;}};
  let observer;
  const context={$:()=>cinema,storage:{get:()=>true,set(){throw Error('Pause must not persist');}},matchMedia:()=>preference,document,window:{IntersectionObserver:true},IntersectionObserver:class{constructor(cb){observer=cb;}observe(){}}};
  const source=fs.readFileSync('aedrova_site/static/site.js','utf8');
  vm.runInNewContext(source.slice(source.indexOf('// One local overhead'),source.indexOf('const menuButton')),context);
  await tick();assert(video.muted&&video.defaultMuted&&video.playsInline);
  assert.equal(Boolean(video.src),!reduced);
  assert.equal(motion.attrs['aria-label'],'Play background video');
  assert(cinema.classes.has('motion-paused'));
  video.reject=false;motion.events.click();await tick();video.events.playing();
  assert.equal(video.src,'/static/overhead-pedestrians.mp4');assert(video.classes.has('active'));
  assert.equal(motion.attrs['aria-label'],'Pause background video');
  motion.events.click();assert(video.paused);assert(cinema.classes.has('motion-paused'));
  motion.events.click();await tick();document.hidden=true;document.events.visibilitychange();assert(video.paused);
  document.hidden=false;document.events.visibilitychange();await tick();
  observer([{isIntersecting:false}]);assert(video.paused);
  observer([{isIntersecting:true}]);await tick();
  video.error={};video.events.error();assert(!video.classes.has('active'));assert.equal(motion.attrs['aria-label'],'Play background video');
  motion.events.click();await tick();assert.equal(video.error,null);
  preference.changed({matches:true});assert(cinema.classes.has('motion-paused'));
 }
 console.log('Autoplay rejection recovery, muted playback, pause, visibility, media error retry and reduced motion pass.');
})().catch(error=>{console.error(error);process.exitCode=1;});
