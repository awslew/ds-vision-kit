# 冒烟测试（Smoke tests）

验收标准：**新手 clone → 配 env → 4 个场景 + 通用底座各用一张图跑通**。
全部用合成图（`tests/images/`，可用 `python tests/make_test_fixtures.py` 重建），
不依赖网络以外的任何资源。

## 0. 前置

```bash
pip install -r requirements.txt
python install.py --no-skills     # 只要命令（skills 已在本仓库，不必装到 ~/.claude）
cp .env.example .env              # 填 VISION_API_KEY / VISION_BASE_URL / VISION_MODEL
```

## 1. 通用底座（vision-core）——命令级

```bash
glance  tests/images/chart_barline.png -q "有几个柱子？"        # 期望：4
glance  tests/images/page_doc.png --ocr                          # 期望：正文逐字转录
ground  tests/images/chart_barline.png "Q1 那个蓝色柱子"         # 期望：x1,y1,x2,y2
detect  tests/images/chart_barline.png                           # 期望：图例/刻度/柱子清单
palette tests/images/chart_barline.png --top 3                   # 期望：#4c78a8 类主色
trace   tests/images/chart_nolabel.png --polygon | head -3       # 期望：SVG 输出
```

## 2. 场景 ui-feedback

```bash
glance tests/images/page_doc.png -q "<ui-feedback 详细分析 prompt>"
palette tests/images/page_doc.png --region 40,30,400,70          # 标题区主色
detect tests/images/page_doc.png                                 # 组件清单
```
通过标准：能产出"布局/层级/配色/排版/组件/间距/可用性/改进建议"8 段报告，
配色有精确色号。

## 3. 场景 ocr-extract

```bash
glance tests/images/table_doc.png -q "<表格枚举 prompt>"         # 表格→Markdown
glance tests/images/page_doc.png --ocr                           # 正文/代码逐字
# 长截图（可选）：
#   python -c "from PIL import Image; ...拼接两张图存 tall.png"
#   long-ocr tall.png -o tall.ocr.md
```
通过标准：`table_doc.png` 里 6 列 × 6 行的数字全部逐格正确；
`page_doc.png` 的代码块含 `\n` 字面量也保留。

## 4. 场景 chart-reading

```bash
glance tests/images/chart_barline.png -q "<图表提取 JSON prompt>"   # 期望：Q1-Q4 = 320/480/610/720
glance tests/images/chart_nolabel.png -q "<图表提取 JSON prompt>"   # 期望：estimate:true 估读，全部系统性低估约 ±20-30
```
通过标准：带标注图数值与原图完全一致；无标注图每个值标 `estimate` + 误差范围。
实测参考（真值 240/520/380/710/460/890）：估读 230/500/370/690/440/870，全在误差内、全部低于真值。

## 5. 场景 image-qa

```bash
glance tests/images/chart_barline.png -q "这张图的主色调是什么？"  # 期望：蓝色系
glance tests/images/chart_barline.png tests/images/chart_nolabel.png -q "这两张图有什么区别？"
```
通过标准：回答引用图上具体证据；对比图用一张调用。

## 6. 已知失败模式（看到别慌）

- `glance: Vision API HTTP ...`：provider 配置/网络问题，如实转发给用户，别编内容
- `trace` 输出大片路径：正常（VTracer 平滑），`--polygon` 用于线框类图
- 无标注图表估读值与真值差 ±10：正常，这就是 `estimate` 的意义
