from pathlib import Path
p=Path('index.html')
js='''
<script>
window.__timelines=window.__timelines||{};
const tl=gsap.timeline({paused:true});
const starts=[0,2,4.65,6.65,7.1,9.65,10.5,11.55,12.95,15.1,16.5,17.85,22.8,25.65];
starts.slice(1).forEach((t,i)=>{
 tl.to('#s'+(i+1),{opacity:0,filter:'blur(9px)',duration:.18,ease:'power2.inOut'},t);
 tl.fromTo('#s'+(i+2),{opacity:0,filter:'blur(6px)'},{opacity:1,filter:'blur(0px)',duration:.22,ease:'sine.inOut',immediateRender:false},t);
});
tl.from('#aura',{opacity:0,y:90,duration:.8,ease:'sine.out'},.12);
tl.to('#aura',{x:180,scaleX:1.2,duration:3.9,ease:'sine.inOut'},.9);
tl.to('#aura',{opacity:.02,duration:.4,ease:'sine.inOut'},7.0);
tl.to('#aura',{opacity:.3,x:10,duration:.4,ease:'sine.inOut'},12.9);
tl.to('#aura',{opacity:.05,duration:.4,ease:'sine.inOut'},17.8);
tl.to('#aura',{opacity:1,x:230,duration:1,ease:'sine.inOut'},22.8);
tl.to('#aura',{x:120,scaleX:.8,duration:3,ease:'sine.inOut'},25.3);
tl.from('#dot1',{scaleX:.4,opacity:0,duration:.3,ease:'back.out(1.7)'},.1);
tl.from('#line1 span',{opacity:0,y:8,filter:'blur(4px)',stagger:.14,duration:.28,ease:'power3.out'},.18);
tl.to('#dot1',{scaleX:.76,duration:1.15,ease:'sine.inOut'},.7);
tl.from('#line2',{opacity:0,y:10,filter:'blur(8px)',duration:.35,ease:'expo.out'},2.05);
tl.from('#dot2',{scaleX:.4,opacity:0,duration:.24,ease:'back.out(1.4)'},2.2);
tl.to('#line2',{scale:3.3,x:-355,y:85,duration:.72,ease:'power4.inOut'},2.43);
tl.to('#dot2',{scale:2.5,x:285,y:190,duration:.72,ease:'sine.inOut'},2.43);
tl.from('#brand3',{opacity:0,scale:.6,rotation:-18,x:195,duration:.55,ease:'expo.out'},4.81);
tl.to('#brand3',{x:0,duration:.44,ease:'power3.inOut'},5.32);
tl.from('#name3',{opacity:0,x:30,filter:'blur(6px)',duration:.48,ease:'sine.out'},5.4);
tl.from('#badge4',{opacity:0,scale:.8,filter:'blur(6px)',duration:.27,ease:'back.out(1.2)'},6.7);
tl.from('#title5',{opacity:0,y:12,duration:.28,ease:'power3.out'},7.17);
tl.from('#prompt5',{opacity:0,scale:.8,duration:.4,ease:'expo.out'},7.18);
tl.to('#prompt5',{scale:1.05,duration:1.7,ease:'sine.inOut'},7.65);
[6,7,8].forEach((n,i)=>{
 const t=starts[n-1];tl.from('#frame'+n,{opacity:0,scale:.85,rotationY:i%2?-7:7,x:i%2?-60:60,duration:.3,ease:'expo.out'},t+.05);
 tl.to('#frame'+n,{rotationY:i%2?3:-3,scale:1.03,duration:Math.max(.4,starts[n]-t-.32),ease:'sine.inOut'},t+.36);
});
tl.from('#cube9',{opacity:0,scale:.65,rotationX:18,y:80,duration:.5,ease:'power3.out'},13.01);
tl.to('#cube9',{rotationX:78,rotationY:-4,duration:.64,ease:'power4.inOut'},13.43);
tl.to('#cube9',{rotationX:3,rotationY:5,scale:1.14,duration:.7,ease:'expo.inOut'},14.17);
tl.from('#dot9',{opacity:0,scale:.2,duration:.3,ease:'back.out(1.5)'},13.13);
tl.to('#dot9',{y:-260,x:180,duration:1.4,ease:'sine.inOut'},13.5);
tl.from('#frame10',{opacity:0,scale:1.1,rotationY:-14,filter:'blur(10px)',duration:.44,ease:'expo.out'},15.15);
tl.to('#frame10',{rotationY:7,x:-55,scale:1.15,duration:.75,ease:'sine.inOut'},15.69);
tl.from('#frame11',{opacity:0,scale:1.13,rotationY:16,filter:'blur(8px)',duration:.35,ease:'power4.out'},16.55);
tl.to('#frame11',{rotationY:-5,x:55,scale:1.04,duration:.82,ease:'sine.inOut'},16.97);
tl.from('#code12',{opacity:0,x:-240,rotationY:-25,rotationX:9,filter:'blur(8px)',duration:.65,ease:'expo.out'},17.97);
tl.to('#code12',{rotationY:-7,rotationX:4,x:50,scale:1.12,duration:1.2,ease:'sine.inOut'},18.67);
tl.from('#ring12',{opacity:0,scale:.1,duration:.35,ease:'back.out(1.7)'},19.0);
tl.from('#caret12',{opacity:0,scaleY:.1,duration:.3,ease:'power3.out'},20.7);
tl.to('#code12',{scale:1.9,x:-270,y:70,duration:1.1,ease:'power4.inOut'},20.9);
tl.to('#ring12',{x:-380,y:30,scale:1.5,duration:1.1,ease:'power4.inOut'},20.9);
tl.to('#caret12',{x:210,y:85,scaleY:1.4,duration:1.1,ease:'power4.inOut'},20.9);
tl.from('#console13 span',{opacity:0,filter:'blur(10px)',x:24,stagger:.14,duration:.52,ease:'expo.out'},22.97);
tl.to('#console13',{scale:1.015,duration:1.5,ease:'sine.inOut'},23.9);
tl.from('#brand14',{opacity:0,scale:.55,rotation:-12,duration:.5,ease:'back.out(1.2)'},25.8);
tl.to('#brand14',{scale:1.02,duration:1.6,ease:'sine.inOut'},26.4);
window.__timelines.main=tl;
</script>
'''
p.write_text(p.read_text().replace('<!-- ANIMATION -->',js))
