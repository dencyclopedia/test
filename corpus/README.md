# Corpus

Test images with UTF-8 ground truth (`<image>.gt.txt` next to each image) for the accuracy benches.
`manifest.json` describes every image: set, source text, font, size, DPI, degradation parameters, seed,
`synthetic` flag and sha256. Licences and text sources: [SOURCES.md](SOURCES.md).

All images are generated (rendered text, or a real Chromium screenshot of a local HTML page written for this corpus),
so every one is labelled `"synthetic": true`. Captions must say "synthetic".

## Sets

| set | images | what |
|---|---|---|
| `clean` | 189 | 3 Gutenberg passages (~1,100-1,300 chars). 12 pt in 6 fonts (DejaVu Serif, Caladea, Carlito, Inter, DejaVu Sans Mono, Courier 10 Pitch) and 8 pt in 3 fonts (DejaVu Serif, Carlito, DejaVu Sans Mono), each at 70/100/150/200/300/400/600 DPI. Letter width (8.5 in), 1 in margins, page height trimmed to the text. Grayscale, anti-aliased, PNG with the DPI in its header. |
| `degraded` | 80 | 4 half-page bases at 300 DPI (Austen/DejaVu Serif, Doyle/Carlito, Shelley/Courier 10 Pitch, Carroll/Inter) x 20 levels: none; Gaussian blur sigma 1/2/3 px; Gaussian noise sigma 15/30/50; JPEG quality 90/70/50/30; skew 1/3/5 degrees; diagonal lighting gradient 50%/75%; low contrast (ink 100/paper 190, ink 150/paper 190); simulated phone photo level 1/2 (perspective warp + grey surround + off-centre vignette + blur + sensor noise + JPEG q85). |
| `receipt` | 16 | 10 generated 80 mm receipts at 300 DPI (mono and sans fonts), 4 "faded thermal" variants, 2 simulated phone photos. |
| `screenshot` | 20 | 5 UIs (settings, dashboard, chat, inbox, terminal) x light/dark x device scale 1/2, captured with Playwright/Chromium. Ground truth = `document.body.innerText`. |
| `multilingual` | 28 | UDHR, 2 pages per language: eng deu fra spa por ita rus chi_sim jpn kor ara hin vie uzb, 12 pt at 300 DPI in a font that covers the script. |
| `line`, `word`, `sparse`, `layout` | 8, 10, 4, 5 | single lines, single words, scattered labels, two-column pages, sideways (90/270) and upside-down pages: for the PSM and online-tool benches. |

## Rebuild

```sh
python3 corpus/gen/fetch_sources.py        # texts (already committed) + Noto fonts (sha256-checked, git-ignored)
node corpus/gen/screenshots.js             # screenshot set (Playwright + Chromium)
python3 corpus/gen/build_corpus.py         # everything else + manifest.json
```
Rendering is deterministic: seeds come from crc32 of the image id, and a rebuild with the same Pillow (12.3.0),
NumPy and OpenCV versions gives byte-identical images (checked: 261/261 images identical across two builds).
Ground truth is the text exactly as drawn (after the edits listed in SOURCES.md); if a font lacked a glyph the
character would be replaced by an ASCII fallback and listed in `text_substitutions` (none were needed).

## Known limits
- Rendered pages are cleaner than real scans; the `degraded` set covers one degradation at a time (except the phone simulation).
- Reading order in screenshots, receipts and labels is not always unique; benches report an extra order-independent word recall for those.
