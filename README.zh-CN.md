# ds-vision-kit

给纯文本 AI 智能体（DeepSeek、GLM，或跑在纯文本底座上的 Claude Code…）提供视觉能力的
**通用识图核心 + 可插拔分场景层** Claude Code skills。

[English](README.md)

## 这是什么

多数编码智能体对文字很强、对图片是瞎的。这个仓库是一个"视觉前端"：给它一张图，
还给你一段纯文本模型能直接推理的结构化文字。

架构分两层：

```
 场景层  (skills/<scene>/SKILL.md) —— 可插拔，每个任务一个 skill
 ─────────────────────────────────────────────────────────────
   ui-feedback    ocr-extract      chart-reading      image-qa
   (UI 设计反馈)   (文字/表格→       (图表数据→         (图像问答 /
                    Markdown)        JSON+摘要)          定位 / 对比)
   ▲ 每个：触发条件 + 工具 pass 流程 + prompt 模板 + 输出格式
   │
 通用核心  (vision-core skill + core/ + bin/ + scripts/) —— 场景无关
 ─────────────────────────────────────────────────────────────
   glance  ground  detect  trace  crop       (视觉 + 像素坐标框)
   palette  pixel-diff  extract-fg  html-shot  long-ocr   (本地像素工具)
   └── core/vision_client.py  (对接任意 OpenAI 兼容视觉端点)
```

- **通用核心** = 命令 + provider 配置。它对 UI、图表没有倾向，只回答原始问题。
- **场景层** = 每个任务一个 skill，自带触发条件、工具 pass 顺序、**prompt 模板**、输出格式。
- **场景注册机制** = `skills/_template/`——新增一个场景只需 4 步。

## 为什么要分场景层？

不分的话就会变成我们原来的样子：一个"视觉工具包"其实只懂评审 UI，加一个识别任务
就得改底座。拆分后，"提取表格""读图表"只是新增一个 SKILL.md，底座永远不动。
这正是本仓库在[上游](https://github.com/Anionex/agent-vision-toolkit)之上加的唯一核心特性。

## 快速开始

```bash
# 1. 克隆
git clone <本仓库> && cd ds-vision-kit

# 2. 装 Python 依赖（pillow/numpy/vtracer，均为按需可选）
pip install -r requirements.txt

# 3. 把命令放进 PATH，并把 skills 复制到 ~/.claude/skills
python install.py

# 4. 配置一个视觉端点
cp .env.example .env   # 填 VISION_API_KEY / VISION_BASE_URL / VISION_MODEL

# 5. 验证
glance tests/images/chart_barline.png -q "有几个柱子？"
```

`install.py` 会为 `glance ground detect trace crop palette pixel-diff
extract-fg html-shot long-ocr` 创建启动器（Windows 上同时生成 POSIX shim 和
`.cmd` 文件），并把 skills 复制到 `~/.claude/skills/`。`VISION_*` 指向任意
OpenAI 兼容视觉端点即可——OpenRouter、OpenAI、本地 vLLM/Ollama，或 OpenCode Go
免费套餐。见 [references/providers.md](references/providers.md)。

## 场景用法

| 用户说 | 场景 | 做什么 |
|---|---|---|
| "评审这个 UI / 设计反馈" | `ui-feedback` | 多 pass：glance 详细 → palette 色号 → detect 组件清单 → 结构化设计报告 |
| "把这张图的文字/表格提取出来" | `ocr-extract` | 逐字 OCR；表格→Markdown（prompt 强制"逐个枚举所有表格，一个都不能漏"）；长截图走 `long-ocr` |
| "读这个图的数据" | `chart-reading` | 图表→JSON(chartType/xAxis/series)，刻度线估读的数值诚实标 `estimate`；建议 `VISION_TEMPERATURE=0` |
| 其他看图 | `image-qa` | glance + ground + pixel-diff 做描述/问答/定位/对比 |

完整分发表（含触发词）：[references/scenes.md](references/scenes.md)。

## 新增一个场景

复制 `skills/_template/SKILL.md.template`，填六块内容，在分发表加一行，用一张
真实图验证。步骤见 [skills/_template/README.md](skills/_template/README.md)。

## 已知精度（实测）

见 [references/accuracy.md](references/accuracy.md)。要点：

- 有标注图表：接近精确（现代视觉模型在已知数据上 99–100%）。
- 无标注、按刻度估读：±2%，且系统性低估——一律标 `estimate`。
- 多表格页面：模型会静默漏掉靠下的表，除非 prompt 强制枚举（ocr-extract 模板已修）。
- 像素级事实（颜色/尺寸/差异）一律来自本地工具（palette/trace/pixel-diff），
  不信模型 prose。

## 目录结构

```
core/                泛化 OpenAI 兼容视觉客户端（+ 配置）
bin/                 glance ground detect trace crop
scripts/             palette pixel-diff extract-fg html-shot long-ocr
skills/
  _template/         场景注册：模板 + 步骤说明
  vision-core/       通用底座 skill
  ui-feedback/       场景：UI 设计反馈
  ocr-extract/       场景：文字/表格 → Markdown
  chart-reading/     场景：图表数据提取
  image-qa/          场景：问答 / 定位 / 对比
references/          scenes / providers / accuracy / pitfalls
tests/               合成测试图 + 冒烟测试
install.py           装 PATH 命令 + 装 skills
```

## 致谢

本仓库 fork 并扩展自
[Anionex/agent-vision-toolkit](https://github.com/Anionex/agent-vision-toolkit)
(MIT)——视觉核心（glance/ground/detect/trace/crop、本地像素脚本、vision_client）
是上游代码 + 两个 Windows 修复 + provider 泛化补丁。见 [LICENSE](LICENSE)
（保留双方版权）。`ui-feedback` 场景基于 unblind 的 ui-review 模式。图表场景的精度
方法论参考 [themenonlab/chart-extraction-validation](https://themenonlab.blog/blog/chart-extraction-validation)。
借鉴的社区设计模式：多 provider 命名约定
（[xiincs/claude-code-vision-skill](https://github.com/xiincs/claude-code-vision-skill)）、
单入口意图路由 + JSON envelope（[Sorwcyra/ds-vision-skill](https://github.com/Sorwcyra/ds-vision-skill)）、
无 key 时 OCR 兜底 + 超时上限（[LearningByDoingNow/vision-skill](https://github.com/LearningByDoingNow/vision-skill)）。
