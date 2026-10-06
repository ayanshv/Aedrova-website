from pathlib import Path
p=Path('.')
scenes=[]
def scene(n,body,cls=''):
 scenes.append(f'<section id="s{n}" class="scene {cls}"><div class="scene-content">{body}</div></section>')
def img(src,cls='',id=''):
 return f'<img id="{id}" class="{cls}" src="assets/{src}" alt="Actual Aedrova interface capture">'
def vid(src,id,start,duration,offset=0):
 return f'<video id="{id}" src="assets/{src}" data-start="{start}" data-duration="{duration}" data-media-start="{offset}" data-track-index="{start}" muted playsinline></video>'
scene(1,'<div id="dot1" class="dot"></div><h1 id="line1"><span>Your team</span> <span>already knows</span> <span class="accent">the details.</span></h1>')
scene(2,'<h1 id="line2" data-layout-allow-overflow>Now build <span>from that understanding.</span></h1><div id="dot2" class="dot"></div>')
scene(3,img('logo.png','brand','brand3')+'<div id="name3" class="brand-name">Aedrova</div>','brand-scene')
scene(4,'<div id="badge4" class="badge">Aedrova</div>')
scene(5,'<h2 id="title5">Your team. Your next build.</h2><div id="prompt5" class="prompt">'+vid('mention-detail.mp4','mention',7.15,2.6,1)+'</div>')
scene(6,'<div id="frame6" class="screen">'+img('workspace-light.png')+'</div>')
scene(7,'<div id="frame7" class="screen">'+img('files-light.png')+'</div>')
scene(8,'<div id="frame8" class="screen">'+img('meetings-light.png')+'</div>')
scene(9,'<div id="cube9" class="cube" data-layout-ignore><div class="face front">'+img('workspace-light.png')+'</div><div class="face bottom">'+img('files-light.png')+'</div><div class="face top">'+img('meetings-light.png')+'</div></div><div id="dot9" class="dot orbit"></div>','cube-scene')
scene(10,'<div id="frame10" class="macro">'+vid('context.mp4','context',15.15,1.5,1.5)+'</div>')
scene(11,'<div id="frame11" class="macro">'+vid('result-detail.mp4','result',16.55,1.5,.3)+'</div>')
scene(12,'<div id="code12" class="code" data-layout-allow-overflow>'+vid('code-detail.mp4','code',17.9,5.1,.2)+'</div><div id="ring12" class="ring" data-layout-ignore></div><div id="caret12" class="caret" data-layout-ignore></div>')
scene(13,'<p id="console13" class="console"><span>console.log(</span><span class="accent">"From a thought to a thing."</span><span>);</span></p>')
scene(14,img('logo-end.png','brand','brand14'))
css='''
:root{--ink:#1C1C1E;--blue:#3268DB;--purple:#7357D9}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}#main{position:relative;width:1920px;height:1080px;background:#fff;overflow:hidden}
.scene{position:absolute;inset:0;width:100%;height:100%;background:transparent;overflow:hidden;perspective:1800px}.scene:not(:first-of-type){opacity:0}.scene-content{width:100%;height:100%;padding:100px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:52px}
h1,h2,p{margin:0;font-weight:400}h1{font-size:50px;font-style:italic;letter-spacing:-1.8px;line-height:1.3;white-space:nowrap}h2{font-size:39px;letter-spacing:-1px}.accent{color:var(--purple)}.dot{width:36px;height:28px;border-radius:20px;background:linear-gradient(100deg,var(--blue),var(--purple));flex-shrink:0}
#s1 .scene-content{gap:70px;padding-bottom:240px}#s2 .scene-content{gap:38px;padding-bottom:175px}#line2{font-size:68px;transform-origin:62% 48%}.brand{width:180px;height:194px;object-fit:contain;flex-shrink:0}.brand-scene .scene-content{flex-direction:row;gap:18px}.brand-name{font-style:italic;font-size:83px;letter-spacing:-3px}.badge{border-radius:26px;padding:5px 17px;background:linear-gradient(100deg,#477CF0,#8567E6);color:#fff;font-size:77px;font-style:italic;letter-spacing:-4px;box-shadow:0 0 50px #7357D966}
#s5 .scene-content{gap:30px}.prompt{width:680px;height:160px;overflow:hidden;border-radius:15px;box-shadow:0 8px 25px #1c1c1e0a}.prompt video{width:100%;height:100%;object-fit:cover}
.screen{width:1000px;height:600px;border-radius:18px;overflow:hidden;box-shadow:0 2px 28px #7357D920;transform-style:preserve-3d}.screen img{width:100%;height:100%;object-fit:cover;display:block}
.cube{position:relative;width:1050px;height:630px;transform-style:preserve-3d}.face{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;border-radius:10px;backface-visibility:hidden;background:#fff;box-shadow:0 0 24px #7357D929}.face img{width:100%;height:100%;object-fit:cover;display:block}.front{transform:translateZ(315px)}.bottom{transform:rotateX(-90deg) translateZ(315px)}.top{transform:rotateX(90deg) translateZ(315px)}.orbit{position:absolute;left:250px;top:720px}
.macro{width:1500px;height:840px;border-radius:18px;overflow:hidden;box-shadow:0 0 30px #3268db22}.macro video{width:100%;height:100%;object-fit:cover;display:block}#s11 .macro{height:560px}#s11 .macro video{object-fit:cover}
.code{width:1250px;height:800px;transform-style:preserve-3d}.code video{width:100%;height:100%;object-fit:cover;display:block;border-radius:8px}.ring{position:absolute;top:520px;left:565px;width:115px;height:65px;border:4px solid var(--purple);border-radius:50%;transform:rotate(-16deg);box-shadow:0 0 16px #7357d955}.caret{position:absolute;left:1180px;top:595px;height:65px;width:3px;background:var(--blue)}.caret:before,.caret:after{content:"";position:absolute;left:-9px;width:21px;height:3px;background:var(--blue)}.caret:after{bottom:0}
.console{font-family:Menlo,Monaco,monospace;font-size:35px;letter-spacing:-1.5px}.console span{display:inline-block}#s14 .brand{width:160px;height:175px}
.aura{position:absolute;left:40px;bottom:-190px;width:850px;height:460px;border-radius:50%;background:radial-gradient(ellipse at 35% 50%,#3268DB88,transparent 70%),radial-gradient(ellipse at 70% 70%,#7357D999,transparent 65%);filter:blur(65px);pointer-events:none}.grain{position:absolute;inset:0;z-index:50;pointer-events:none;opacity:.024;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 300 300' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch' seed='17'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
'''
html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Aedrova — reference white edition</title><script src="gsap.min.js"></script><style>'+css+'</style></head><body><div id="main" data-composition-id="main" data-start="0" data-duration="28.333333" data-width="1920" data-height="1080"><div id="aura" class="aura" data-layout-ignore></div>'+''.join(scenes)+'<div class="grain" data-layout-ignore></div><audio id="music" src="assets/reference-audio.wav" data-start="0" data-duration="28.333333" data-track-index="30" data-volume="1"></audio></div>\n<!-- ANIMATION -->\n</body></html>'
p.joinpath('index.html').write_text(html)
