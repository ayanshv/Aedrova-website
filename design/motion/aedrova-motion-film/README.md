# Aedrova — reference white edition

Finished 28⅓-second adaptation of the owner's supplied motion reference, with a white canvas, Aedrova blue-purple accents, Aedrova copy, and real native product captures.

## Files
- `Aedrova-reference-white.mp4`: revised 1920 × 1080, 30 fps H.264/AAC film.
- `index.html`: authoritative editable HyperFrames / GSAP composition.
- `DESIGN.md`: reference beat map and visual identity.
- `Aedrova-motion-film.mp4`, `dark-original.html.txt`: preserved earlier dark version.
- `qa/`: static layouts, reference and export contact sheets, runtime checks, decode logs, tween map and acceptance notes.

The revised film reconstructs the supplied reference's shot order, components and motion vocabulary from its rendered pixels. Its original editable animation project was not supplied, so this is not a pixel-identical reskin. No reference visual frames are used in the final film. Audio is retained from the supplied reference as requested by “everything else stays identical.”

Native app media includes real workspace, files and meetings-tab captures, plus actual recorded mention, context search, code review and local build results. These are product-preview captures, not newly fabricated UI. The code macro holds an actual code-review frame to keep text visible while the camera moves. It contains no account credentials. Opening and closing text are editorial copy.

This task does not change or deploy application/website functionality. Public launch, managed AI availability and hosted meeting acceptance are not asserted.

## Preview and render

Studio: http://localhost:3017/#project/aedrova-motion-film

With Node, FFmpeg, FFprobe and Chrome configured:

```sh
pnpm exec hyperframes check
pnpm exec hyperframes render --output Aedrova-reference-white.mp4 --fps 30 --quality high --workers 2 --strict-all
pnpm exec hyperframes preview --background --port 3017
```

`index.html` is the final source; tools/build-white.py and tools/animate-white.py record initial construction, before the final QA adjustments.
