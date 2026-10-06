const { chromium } = require('/Users/ayanshvarma/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'); const path=require('path');
(async()=>{
const browser=await chromium.launch({executablePath:'/Users/ayanshvarma/.cache/hyperframes/chrome/chrome-headless-shell/mac_arm-152.0.7977.30/chrome-headless-shell-mac-arm64/chrome-headless-shell',headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080}});
await page.goto('file://'+path.resolve('index.html')); await page.waitForTimeout(500);
fs.mkdirSync('qa/white-static',{recursive:true});
const bounds=[];
for(let i=1;i<=14;i++){
await page.evaluate(async id=>{
 document.querySelectorAll('.scene').forEach(s=>{s.style.opacity=s.id===id?'1':'0'});
 const v=document.querySelector('#'+id+' video');if(v){v.currentTime=1; await new Promise(r=>v.addEventListener('seeked',r,{once:true}));}
},'s'+i);
await page.screenshot({path:'qa/white-static/scene-'+i+'.png'});
bounds.push(await page.evaluate(id=>Array.from(document.querySelectorAll('#'+id+' .scene-content > *')).map(e=>{const b=e.getBoundingClientRect();return{scene:id,tag:e.tagName,id:e.id,x:b.x,y:b.y,width:b.width,height:b.height,inside:b.x>=0&&b.y>=0&&b.right<=1920&&b.bottom<=1080}}),'s'+i));
}
fs.writeFileSync('qa/white-static/bounds.json',JSON.stringify(bounds,null,2));await browser.close();console.log('14 static hero layouts captured');
})().catch(e=>{console.error(e);process.exit(1)});
