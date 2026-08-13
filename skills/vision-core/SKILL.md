---
name: vision-core
description: >-
  Scene-agnostic vision core for ds-vision-kit: glance (describe/ask/OCR an
  image), ground (locate a target, pixel box), detect (element inventory),
  trace (image to SVG geometry), crop (cut a pixel box to a file), plus local
  pixel tools palette / pixel-diff / extract-fg / html-shot / long-ocr. Use for
  ANY image task — the scene skills (ui-feedback, ocr-extract, chart-reading,
  image-qa) build on this. See ../references/scenes.md to pick a scene.
metadata:
  source: https://github.com/Anionex/agent-vision-toolkit (MIT, see LICENSE)
  depends_on:
    - vision config (.env: VISION_API_KEY / VISION_BASE_URL / VISION_MODEL)
---

# vision-core

Scene-agnostic eyes for a text-only agent. Read one shared vision config
(`VISION_API_KEY` / `VISION_BASE_URL` / `VISION_MODEL` / `LANG`) — no extra
credentials. Pick the tool by the question you are answering:

| Question | Tool |
|---|---|
| "What does this image show / say?" | `glance` |
| "Where is X?" — a thing you can name | `ground` |
| "Where are all the Xs?" — every instance of a kind | `detect` |
| "What is its exact shape, size, offset?" | `trace` |
| "Cut this box out as its own image file" | `crop` |
| "Which colours dominate a region, and which palette value fits it?" | `palette` |
| "Where do two images differ?" | `pixel-diff` |
| "OCR this long screenshot / scrolling page / chat history" | `long-ocr` |
| "Extract the icon/logo foreground as transparent PNG" | `extract-fg` |
| "Turn this HTML file into a screenshot" | `html-shot` |

`glance` answers what something is; `ground` and `detect` answer where.
You give `ground` a description of a particular thing; you give `detect` a
kind and it enumerates the instances. Both give real coordinates on a 0-1000
grid scaled to your image — accurate enough to crop, click, and compare. When a
number has to be exact (sizes, offsets, shapes), `trace` derives it from the
actual pixels.

## Use the provided tools before hand-rolled pixels

- cut a box out of an image → `crop`, not Pillow
- sample a region's palette → `palette`
- compare two images → `pixel-diff`
- vectorize to SVG → `trace`
- locate / inventory elements → `ground` / `detect`
- describe / OCR an image → `glance`
- safely split, OCR, and merge a long screenshot → `long-ocr`
- HTML file to a screenshot → `html-shot`

Hand-written Pillow is only for what none of them return: a relation between
two things you already located (a gap, a distance), a resize or overlay.

## glance — ask about an image

```bash
glance <image>                                 # detailed description
glance <image> -q "<question>"                 # targeted question (qualitative only)
glance <image> --ocr                           # verbatim OCR
glance <image> --region X1,Y1,X2,Y2 -q "..."   # zoom into a crop
glance <img1> <img2> -q "..."                  # compare in ONE call
```

Compare with `glance` by passing all paths to one call — separate calls cannot
see both images. `--region` uploads only the crop, so small text and icons
become readable. "What changed between these two?" is not a glance question —
run `pixel-diff` first to get the box, then `glance --region` that box.

For a tall scrolling screenshot, do not send the whole image through one OCR
call: use `long-ocr`, which finds low-content cut bands, invokes `glance` on
each chunk, and merges only duplicated overlap:

```bash
long-ocr work/page.png -o work/page.ocr.md
long-ocr work/chat.png --mode chat --resume -o work/chat.ocr.md
```

## ground — locate a named target

```bash
ground <image> "<target description>"
ground <image> "<target>" --region X1,Y1,X2,Y2
```

Output: `x1: .., y1: .., x2: .., y2: ..` in original-image pixels (with
`--region` too — crop hits are mapped back). If several boxes come back
numbered, your description matched more than one element — narrow it with what
distinguishes the one you mean, and ask again. The box is a handle, not just an
answer — it feeds the next call:

```bash
$ ground screenshot.png "the send button"
x1: 1067, y1: 841, x2: 1108, y2: 881
$ glance screenshot.png --region 1067,841,1108,881 -q "is it enabled or greyed out?"
```

Known limitation: an ordinal description like "the 3rd bar" can match the wrong
instance. Prefer `detect` (full enumeration) then narrow by description, or
ground by a distinguishing feature (its label, its position).

## detect — find every instance of a kind

```bash
detect <image>                        # every element
detect <image> "buttons"              # one kind only
detect <image> --region X1,Y1,X2,Y2   # inside one box
```

Output is a numbered list with each item's visible text and box. A full-screen
pass is a fast first draft — counts vary run to run on dense screens. For
completeness, detect the layout blocks first, then `detect --region` each block.

## trace — exact shape geometry (local, no vision API)

```bash
trace <image>                                  # b/w spline SVG to stdout
trace <image> --polygon                        # boxy diagrams/wireframes
trace <image> --region X1,Y1,X2,Y2 -o out.svg  # crop first
```

Coordinates come from the actual pixels, not a model's estimate. Flat,
high-contrast graphics only; text becomes curves. Small images are upscaled
automatically before tracing.

## crop — cut a pixel box out of an image (local)

```bash
crop <image> --region X1,Y1,X2,Y2             # writes <image-stem>.crop.png next to the input
crop <image> --region X1,Y1,X2,Y2 -o out.png
crop <image> --region X1,Y1,X2,Y2 --scale 4   # upscale the cut-out 4x (LANCZOS)
```

Once a box is worth keeping — the same crop is about to feed `pixel-diff`,
`palette`, and `trace` in turn — cut it to a file once and reuse it.

## palette — a region's palette, and the exact value among candidates (local)

```bash
palette <image> --region X1,Y1,X2,Y2                         # top colour clusters + shares
palette <image> --region X1,Y1,X2,Y2 --candidates '#F9FAFA,#F5F5F5'  # pick the best candidate
```

A vision model names a colour ("light gray") but not its value. Take the value
from here, never from `glance`'s prose.

## pixel-diff — where two images differ (local)

```bash
pixel-diff <a> <b>
```

Prints an overall difference percentage plus the worst regions as `x1: ..`
boxes you can feed straight into `glance --region`. Exact where a vision model
rounds off.

## extract-fg — icon foreground as transparent PNG (local)

```bash
extract-fg shot.png --region X1,Y1,X2,Y2 -o icon.png
extract-fg d/icon1.png d/icon2.png        # auto mode (crop --scale cut-outs)
```

## html-shot — render an HTML file to an image (local, needs Chrome/Edge)

```bash
html-shot page.html                      # writes page.png, 1280x800
html-shot page.html --width 1440 --height 900 -o page.png
html-shot page.html --scale 2            # 2x pixels: small text stays readable
```

The visual-alignment loop: write HTML, screenshot it, then compare with the
design using `pixel-diff`. Headless Chrome/Chromium/Edge — no Python deps.

## Work from a copy, not a temp path

If the image lives in a temp directory, before your first tool call copy it
somewhere durable and run everything against the copy:

```bash
cp "<the temp path>" work/shot.png
glance work/shot.png -q "..."
```

## When you have a description instead of the image

If an image reached you only as text and its file path is visible, do not
reason past a missing detail — look again yourself:

1. `glance <path> -q "<the specific detail>"` — one qualitative follow-up.
2. `ground <path> "<target>"` then `glance <path> --region <that box> -q "..."` —
   locate, then zoom. The reliable way to inspect one element closely.

If the file no longer exists, say so instead of guessing.

## Coarse to fine — the method behind every task

For a single question, `glance` is the whole answer. For anything multi-step,
work outside-in:

1. One full-image pass (`glance`, or a description you already have) for layout
   and an inventory of what is where.
2. For any element that matters, `ground` it, then zoom with
   `glance --region <box> -q "..."`. Full-image passes routinely miss small
   text and icons; a crop puts all the pixels on one detail. Cut the box to a
   file first with `crop` if it will be re-used.
3. Never take a *prose* answer for a pixel-level fact — exact colors, small
   offsets, sizes. Get numbers from `trace`, `ground` boxes, `pixel-diff`, or
   `palette`.

## Dispatch: which scene handles which request

This core answers raw questions. For a job, hand off to the matching scene
skill (each has its own SKILL.md with trigger + passes + prompt + output):

| User says / wants | Scene skill |
|---|---|
| "评审这个 UI / 设计反馈 / 还原这个界面" | `ui-feedback` |
| "把这张图的文字/表格转出来" | `ocr-extract` |
| "读这个图的数据 / 图表提取" | `chart-reading` |
| Anything else about an image | `image-qa` (or use core directly) |

Full dispatch table: `../references/scenes.md`.

## Notes

- Only PNG / JPEG / GIF / WebP images are supported.
- If a command is not found, run `python install.py` (or install the optional
  deps) — report this to the user instead of improvising.
- If the vision API fails, relay the error faithfully; never fabricate image
  content. `glance` retries on 429/5xx automatically.
