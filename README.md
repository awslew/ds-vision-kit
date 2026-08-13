# ds-vision-kit

Generic vision for text-only AI agents (DeepSeek, GLM, Claude Code on a
text-only base, …): a **scene-agnostic vision core** + a **pluggable scene
layer** of Claude Code skills.

[中文说明](README.zh-CN.md)

## What this is

Most coding agents are excellent with text but blind to images. This repo is a
"vision front-end": give it an image, get back structured text a text-only
model can reason over.

It is organized as two layers:

```
 Scene layer  (skills/<scene>/SKILL.md) — pluggable, one skill per job
 ─────────────────────────────────────────────────────────────
   ui-feedback    ocr-extract      chart-reading      image-qa
   (UI design     (text/table →    (chart data →      (Q&A / locate /
    review)        Markdown)        JSON + summary)     compare)
   ▲ each: trigger conditions + tool passes + prompt template + output format
   │
 Vision core  (vision-core skill + core/ + bin/ + scripts/) — scene-agnostic
 ─────────────────────────────────────────────────────────────
   glance  ground  detect  trace  crop       (vision + pixel boxes)
   palette  pixel-diff  extract-fg  html-shot  long-ocr   (local pixel tools)
   └── core/vision_client.py  (talks to ANY OpenAI-compatible vision endpoint)
```

- **Vision core** = the commands + provider config. It has no opinions about
  UI or charts; it answers raw questions.
- **Scene layer** = one skill per job. Each skill ships its own trigger
  conditions, tool-pass sequence, **prompt template**, and output format.
- **Scene registry** = `skills/_template/` — 4 steps to add a new scene.

## Why a scene layer?

Without it you get what we had: a "vision toolkit" that secretly only knows how
to review UI. Adding a new recognition task meant editing the base. With the
split, adding "extract this table" or "read this chart" is just a new SKILL.md
— the base never changes. That is the single feature this repo adds on top of
[upstream](https://github.com/Anionex/agent-vision-toolkit).

## Auto, not manual

Two things happen automatically so you don't route anything by hand:

- **Providers auto-detect + fail over.** Configure as many OpenAI-compatible
  endpoints as you like (`VISION_EXTRA_PROVIDERS` + `VISION_PROVIDER_<NAME>_*`);
  the client detects which are configured, and when the current one errors
  (rate-limited, quota out, down) the next provider is tried automatically.
  `VISION_RACE=1` races them, first valid answer wins.
- **Scenes auto-route on intent.** You say the intent ("extract this table",
  "read this chart", "review this UI") and attach the image — the scene skill
  whose description matches is invoked, or `vision-core` reads the matching
  scene's SKILL.md and follows it exactly. You never name a scene or a provider.

## Quick start

```bash
# 1. clone
git clone <this-repo> && cd ds-vision-kit

# 2. install python deps (pillow/numpy/vtracer — all optional per tool)
pip install -r requirements.txt

# 3. put the commands on PATH and copy the skills into ~/.claude/skills
python install.py

# 4. configure one vision endpoint
cp .env.example .env          # then fill VISION_API_KEY / VISION_BASE_URL / VISION_MODEL

# 5. verify
glance tests/images/chart_barline.png -q "how many bars?"
```

`install.py` creates launchers for `glance ground detect trace crop palette
pixel-diff extract-fg html-shot long-ocr` (both POSIX shims and `.cmd` files on
Windows) and copies the skills under `~/.claude/skills/`. Point `VISION_*` at
any OpenAI-compatible vision endpoint — OpenRouter, OpenAI, a local vLLM/Ollama,
or OpenCode Go's free tier. See [references/providers.md](references/providers.md).

## Using the scenes

| User says | Scene | What it does |
|---|---|---|
| "review this UI / give design feedback" | `ui-feedback` | multi-pass: glance detail → palette colors → detect inventory → structured design report |
| "extract the text/table from this image" | `ocr-extract` | verbatim OCR; table → Markdown (prompt forces "enumerate every table, miss none"); long screenshots via `long-ocr` |
| "read the data off this chart" | `chart-reading` | chart → JSON (chartType/xAxis/series) with honest `estimate` flags for gridline-read values; recommends `VISION_TEMPERATURE=0` |
| anything else about an image | `image-qa` | describe / Q&A / locate / compare via glance + ground + pixel-diff |

Dispatch table with trigger phrases: [references/scenes.md](references/scenes.md).

## Adding a new scene

Copy `skills/_template/SKILL.md.template`, fill in the six blocks, add one row
to the dispatch table, and verify against a real image. Details:
[skills/_template/README.md](skills/_template/README.md).

## Known accuracy (measured)

See [references/accuracy.md](references/accuracy.md). Highlights:

- Labeled charts: near-exact (modern VLMs hit 99–100% on known data).
- Unlabeled chart gridline reading: ±2%, systematically low — always flagged `estimate`.
- Multi-table pages: the model silently drops lower tables unless the prompt
  forces enumeration (the `ocr-extract` template fixes this).
- Pixel-level facts (colors, sizes, diffs) come from local tools
  (`palette`/`trace`/`pixel-diff`), never from model prose.

## Project layout

```
core/                generalized OpenAI-compatible vision client (+ config)
bin/                 glance ground detect trace crop
scripts/             palette pixel-diff extract-fg html-shot long-ocr
skills/
  _template/         scene registration: template + how-to
  vision-core/       the base-tool skill
  ui-feedback/       scene: UI design review
  ocr-extract/       scene: text/table → Markdown
  chart-reading/     scene: chart data extraction
  image-qa/          scene: Q&A / locate / compare
references/          scenes / providers / accuracy / pitfalls
tests/               synthetic fixtures + smoke tests
install.py           put commands on PATH + install skills
```

## Credits

This project forks and extends [Anionex/agent-vision-toolkit](https://github.com/Anionex/agent-vision-toolkit)
(MIT) — the vision core (`glance/ground/detect/trace/crop`, the local pixel
scripts, and the `vision_client`) is upstream code plus two Windows fixes and
provider-generalization patches. See [LICENSE](LICENSE) (both copyrights).
The `ui-feedback` scene builds on the unblind ui-review pattern. The chart
scene's accuracy methodology follows
[themenonlab/chart-extraction-validation](https://themenonlab.blog/blog/chart-extraction-validation).
Design patterns borrowed from the community: multi-provider naming
(`xiincs/claude-code-vision-skill`), intent-routed single entry + JSON envelope
(`Sorwcyra/ds-vision-skill`), no-key OCR fallback + timeout cap
(`LearningByDoingNow/vision-skill`).
