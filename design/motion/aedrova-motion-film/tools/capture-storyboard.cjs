const { chromium } = require('/Users/ayanshvarma/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
const browser=await chromium.launch({executablePath:'/Users/ayanshvarma/.cache/hyperframes/chrome/chrome-headless-shell/mac_arm-152.0.7977.30/chrome-headless-shell-mac-arm64/chrome-headless-shell',headless:true});
const page=await browser.newPage({viewport:{width:1080,height:608},deviceScaleFactor:1});
await page.goto('file://'+path.resolve('storyboard-jpg/still-source.html'));
await page.waitForTimeout(500);const rows=JSON.parse(fs.readFileSync('storyboard-jpg/manifest.json','utf8'));
for(const r of rows){
 await page.evaluate(async({t,n})=>{
  window.__timelines.main.seek(t);
  for(const video of document.querySelectorAll('video')){
    const start=Number(video.dataset.start),dur=Number(video.dataset.duration),offset=Number(video.dataset.mediaStart||0);
    video.style.opacity=t>=start&&t<start+dur?'1':'0';
    const target=Math.min(video.duration-.04,Math.max(0,t-start+offset));
    if(Number.isFinite(target)&&Math.abs(video.currentTime-target)>.001){await new Promise(resolve=>{video.addEventListener('seeked',resolve,{once:true});video.currentTime=target;});}
  }
  const set=(sel,css)=>Object.assign(document.querySelector(sel).style,css);
  if(n===1)set('#dot1',{left:'275px'});else if(n===2)set('#dot1',{left:'-20px'});else set('#dot1',{left:'-385px'});
  if(n===7||n===8){set('#brand3',{width:'450px',height:'485px',transform:'translateX(190px)'});set('#name3',{opacity:'0'});}else set('#brand3',{width:'260px',height:'280px'});
  if(n===4)set('#dot2',{opacity:'1',transform:'translateY(14px) scaleX(1.35)'});
  if(n===5||n===6){set('#line2',{transform:'translate(-240px,40px) scale(3.3)'});set('#dot2',{transform:'translate(20px,150px) scale(2.5)'});}
  if(n===17)set('#frame8',{transform:'translateY(540px) rotateX(38deg) scale(1.18)'});
  if(n===18){set('#cube9',{transform:'none'});set('#cube9 .front',{transform:'perspective(1600px) translateY(-230px) rotateX(28deg) scale(.9)'});set('#cube9 .bottom',{transform:'perspective(1600px) translateY(300px) rotateX(-55deg) scale(.85)'});set('#cube9 .top',{opacity:'0'});}
  if(n===19){set('#cube9',{transform:'rotateX(3deg) scale(1.19)'});set('#cube9 .bottom',{opacity:'0'});set('#cube9 .front',{transform:'translateZ(150px)'});}
  if(n===20)set('#frame10',{transform:'translateX(-180px) rotateY(-22deg) rotateZ(-3deg) scale(1.05)'});
  if(n===21){document.querySelector('#frame11').innerHTML='<img src="../qa/review-source.png" style="width:100%;height:100%;object-fit:cover">';set('#frame11',{transform:'translateX(-210px) rotateY(24deg) rotateZ(-2deg) scale(1.04)'});}
  if(n>=22&&n<=24){document.querySelector('#code').style.opacity='0';let image=document.querySelector('#module-still');if(!image){image=document.createElement('img');image.id='module-still';image.src='../assets/module-area.png';document.querySelector('#code12').prepend(image);} document.querySelector('#code').style.position='absolute';
    if(n===22)set('#code12',{transform:'translate(-220px,-120px) rotateY(-28deg) rotateX(10deg)'});
    if(n===23)set('#code12',{transform:'translate(-90px,-55px) rotateY(-14deg) rotateX(4deg)'});
    if(n===24)set('#code12',{transform:'translate(-580px,-25px) scale(1.9)'});
  }

 },{t:r.sampleTime,n:r.n});
 await page.screenshot({path:path.join('storyboard-jpg/aedrova',r.filename),type:'jpeg',quality:97});
}
await browser.close();console.log('28 Aedrova JPG storyboard frames captured. No video render.');
})().catch(e=>{console.error(e);process.exit(1)});
