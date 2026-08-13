# 场景分发：哪个场景接哪个请求

用户看图请求 → 先按下面的表选场景 skill → 场景 skill 内部再决定用 vision-core
的哪些命令。核心命令（glance/ground/detect/...）不直接接请求，是场景层的工具。

## 分发表

| 用户说 / 想要 | 场景 | 核心工具 |
|---|---|---|
| "评审这个 UI"、"设计反馈"、"这个界面怎么改"、"还原这个页面" | `ui-feedback` | glance + palette + detect |
| "把文字/表格提取出来"、"OCR"、"转录"、"表格转 markdown"、"扫描件转文字" | `ocr-extract` | glance --ocr + long-ocr |
| "读这个图的数据"、"图表提取"、"柱状图/折线图/饼图数值" | `chart-reading` | glance + detect + --region |
| "这张图是什么"、"图里有没有 X"、"X 在哪里"、"对比两张图"、"判断这个截图" | `image-qa` | glance + ground + pixel-diff |
| 复合请求（"评审 UI 并把按钮文字也提取出来"） | 主场景为主，辅助场景补 pass | — |

## 选不中的兜底

- 命中多个 → 用最贴近用户主要意图的那个，需要时再补其他场景的 pass
- 都不像 → 用 vision-core 直接问（= image-qa 的做法）

## 为什么这样分

场景不是按"图片类型"（UI 图/图表/文档）分的，而是按**用户想要的结果**分：
同样一张表格截图，"转成 markdown"走 ocr-extract，"找出数字异常"走 chart-reading。
如果按图片类型分，请求意图和场景会互相穿透。
