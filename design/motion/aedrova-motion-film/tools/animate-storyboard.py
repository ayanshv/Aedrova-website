from pathlib import Path
import re
p=Path('index.html');Path('previous-white-animation.html.txt').write_text(p.read_text())
s=Path('storyboard-jpg/still-source.html').read_text().replace('../assets/','assets/').replace('../gsap.min.js','gsap.min.js')
s=s.replace('body{width:1080px;height:608px;overflow:hidden}#main{transform:scale(.5625);transform-origin:top left}','body{width:1920px;height:1080px;overflow:hidden}')
s=s.replace('#brand3{width:150px;height:165px}','#brand3{width:260px;height:280px}')
s=s.replace('transform:rotate(-7deg) skewX(-18deg)','transform:rotate(-7deg) skewX(-18deg) scaleX(var(--underline,1));transform-origin:left')
s=re.sub(r'<video id="result".*?</video>','<img src="qa/review-source.png" style="width:100%;height:100%;object-fit:cover" alt="Actual local code review">',s)
s=re.sub(r'<video id="code".*?</video>','<img src="assets/module-area.png" alt="Actual generated Python module">',s)
s=s.replace('data-start="15.15" data-duration="1.5"','data-start="15.05" data-duration="1.5"')
s=s.replace('</style></head>','</style><style>.front,.bottom,.top{transform:none}.top{display:none}.cube{transform-style:flat}#frame10,#frame11{flex-shrink:0}#line1 span{display:inline-block}.console .char{display:inline-block;white-space:pre}</style></head>')
s=re.sub(r'<script>.*?</script>',Path('tools/storyboard-timeline.js').read_text(),s,flags=re.S)
s=re.sub(r'\.(front|bottom|top)\{transform:[^}]*\}',r'.\1{}',s)
p.write_text(s)
