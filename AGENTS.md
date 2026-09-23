# AGENTS.md

面向在此仓库工作的 coding agent。**只写"看代码不容易知道"的约束**。
项目介绍见 [README.md](./README.md)，工具用法见 [skills/vision-core/SKILL.md](./skills/vision-core/SKILL.md)。

## 这是什么

给**纯文本 AI agent** 用的视觉工具集，两层结构：**scene-agnostic 的视觉内核**
（`core/vision_client.py` + `bin/` + `scripts/`）和**可插拔的场景层**
（`skills/<scene>/SKILL.md`）。它是上游 [Anionex/agent-vision-toolkit](https://github.com/Anionex/agent-vision-toolkit)
（MIT）的 fork，新增的唯一东西就是场景层。

**改代码前必须理解的机制**：

1. **内核不许知道场景**。`ui-feedback` / `ocr-extract` / `chart-reading` / `image-qa` 的差异
   全部写在各自的 `SKILL.md` 里（触发条件 + 工具趟次 + prompt 模板 + 输出格式）。
   **新增一个识别任务 = 新增一个 `SKILL.md`，不是改内核**——这是本仓库存在的理由，
   把场景逻辑塞进 `core/` 或 `bin/` 就等于退化成上游。
2. **`bin/*` 是薄启动器，不是实现**。它们只做 `sys.path.insert(repo_root)` 然后
   `from detect import main` / `from core.vision_client import ...`；真正的逻辑在仓库根的
   `detect.py` / `ground.py` 和 `scripts/*.py` 里。不要把逻辑写进 `bin/`。
3. **`install.py` 的两件事**：往 PATH 目录写启动器（Windows 同时写 POSIX shim 与 `.cmd`，
   因为 Git Bash 与 cmd.exe 对路径/斜杠的处理不同），并把 `skills/` **连同 `references/`**
   复制到 `~/.claude/skills/`——场景 skill 里写的是相对路径 `../references/*.md`，
   没有那份 references 副本，装好的 skill 会读不到文档。目标目录已存在时**跳过而不是覆盖**。
4. **坐标契约**：模型侧返回的是 0–1000 归一化网格，工具换算回**原图像素**；
   传 `--region` 时命中的框也映射回原图坐标。小图会按 `VISION_MIN_UPSCALE`（默认 800、LANCZOS）
   等比上采样后再发——所以**不要让上采样改变坐标语义**，换算逻辑在 `core/vision_client.py`。
5. **像素级事实只从本地工具出**：精确颜色 / 尺寸 / 偏移 / 差异一律来自
   `palette` / `trace` / `pixel-diff` / `ground` / `detect` 的数值输出，
   **绝不采信模型口述**。这是精度契约（见 `references/accuracy.md`），
   不要为了"少一次调用"把它换成一次 `glance`。
6. **估读必须标 `estimate`**：无标注图表的网格线估读系统性偏低（实测 ±2%），
   `chart-reading` 的输出格式里 `estimate` 标记是契约的一部分，不是可选装饰。
7. **`long-ocr` 不能退化成一次 OCR**：它负责找低内容切带、分块调用、**只合并重复的重叠区**。
   整张长图走一次 `glance --ocr` 会漏内容。
8. **多 provider 是自动的**：端点从环境变量自动探测，当前端点失败自动切下一个，
   `VISION_RACE=1` 并发竞速。不要加"手动指定 provider"的必填参数——用户不该按 provider 路由。

## 常用命令

核实自 `install.py`、`requirements.txt`、`tests/smoke_tests.md` 与
[skills/vision-core/SKILL.md](./skills/vision-core/SKILL.md)：

```bash
pip install -r requirements.txt          # 可选依赖：pillow / numpy / vtracer
python install.py                        # 装命令 + 复制 skills 到 ~/.claude/skills
python install.py --no-skills            # 只装命令
python install.py --bin DIR --dry-run    # 换安装目录 / 只预览
cp .env.example .env                     # Windows: copy .env.example .env

glance tests/images/chart_barline.png -q "how many bars?"   # 装完后的验证命令
glance <image> --ocr                                          # 逐字 OCR
glance <image> --region X1,Y1,X2,Y2 -q "..."                  # 放大局部提问
glance <img1> <img2> -q "..."                                 # 两张图必须在同一次调用里对比
ground <image> "<target>"                                     # 定位，输出像素框
detect <image> ["buttons"]                                    # 元素清单
trace <image> [--polygon] [-o out.svg]                        # 本地矢量化，不调视觉 API
crop <image> --region X1,Y1,X2,Y2 -o out.png                  # 裁剪（--scale N 放大）
palette <image> --region X1,Y1,X2,Y2 --candidates '#F9FAFA'    # 区域主色 / 候选色取值
pixel-diff <a> <b>                                            # 差异百分比 + 最差区域框
extract-fg <image> --region X1,Y1,X2,Y2 -o icon.png           # 前景抠成透明 PNG
html-shot page.html --width 1440 --height 900 -o page.png      # 需本机 Chrome/Edge
long-ocr work/page.png -o work/page.ocr.md                    # 长截图分块 OCR

python tests/make_test_fixtures.py       # 重建 tests/images/ 下的合成夹具
python scripts/secret_scan.py            # 推送前：扫受跟踪文件 + 整个 git 历史
glance --help                            # install.py 会提示用它验证安装
```

冒烟测试的真实命令与通过标准全部在 [tests/smoke_tests.md](./tests/smoke_tests.md)
（需要真实端点与网络，不是离线单测）。

## 改动纪律

**高风险区（改前先想清楚）**

- `core/vision_client.py`：所有命令共用的唯一视觉客户端（端点解析、降级、竞速、重试、
  超时、上采样、坐标换算都在这里）。改它会同时影响 10 个命令和 4 个场景。
- **坐标 / 上采样的换算**：一旦不守恒，`ground`/`detect` 的框就再也喂不进 `crop`/`--region`。
- **各场景 `SKILL.md` 的输出格式契约**：`estimate` 标记、表格枚举要求、JSON 字段名
  是被下游直接消费的，改格式等于破坏调用方。
- **`install.py` 的启动器写法**：POSIX shim 必须用正斜杠且加引号（反斜杠会被 shell 吃掉，
  未加引号的 Windows 路径会直接 `<exec>` 失败），`.cmd` 用反斜杠。别"统一"成一种。
- **`.env.example` 是唯一的环境变量清单**：新增变量要同时更新它、`README.md` 与
  `references/providers.md`，否则用户永远不知道有这个开关。
- **`tests/images/*` 是合成夹具**（可用 `tests/make_test_fixtures.py` 重建），
  不要换成真实截图——`tests/output/` 已被 gitignore，那是本地产物目录。

**已知取舍：不要"修"**

- **无标注图表网格线估读会系统性偏低**：这是模型的物理限制，用 `estimate` 如实标注就是正确做法，
  不要"调 prompt 让它更准"到编数字。
- **多表格页面会静默丢表**：修法是在 prompt 里强制枚举（已做），不是换模型。
- **`trace` 只处理扁平高对比图形**，文字变曲线、输出路径很密是正常的（`--polygon` 用于线框类图）。
- **`ground` 的序数描述（"第 3 个"）可能匹配错实例**：正确做法是 `detect` 全枚举后筛，
  不要靠调 prompt 硬掰。
- **`html-shot` 依赖本机浏览器**，`trace` 依赖 vtracer——它们是可选依赖，
  缺了就如实报错，不要偷偷改成"用视觉模型画 SVG"。
- **只用 4 种图片格式（PNG/JPEG/GIF/WebP）**：不支持的是有意边界。
- 默认答案语言是中文（`LANG=zh`）；要英文回答设 `LANG=en`。

**历史与归属**

- 本仓库是 upstream 的 fork：`LICENSE` 里保留**两份版权声明**，
  `skills/vision-core/SKILL.md` 的 frontmatter 里也有 `source:` 归属行。
  **不要删除或"整理"这些归属声明。**
- README 的 Credits 一节列了借鉴来源（unblind 的 ui-review 模式、
  `xiincs/claude-code-vision-skill`、`Sorwcyra/ds-vision-skill`、
  `LearningByDoingNow/vision-skill`、chart-extraction-validation）。
  新增借鉴要补进去，**不要抹掉已有的**。

## 目录 / 模块速览

| 路径 | 职责 |
|---|---|
| `core/vision_client.py` | 通用 OpenAI 兼容视觉客户端：端点解析 / 降级 / 竞速 / 重试 / 上采样 / 坐标换算 |
| `bin/glance` · `bin/ground` · `bin/detect` · `bin/trace` · `bin/crop` | 5 个薄启动器（插入 repo root 到 `sys.path` 后 import 实现） |
| `detect.py` · `ground.py`（仓库根） | `detect` / `ground` 的真实实现 |
| `scripts/dominant_colors.py` | `palette` 实现 |
| `scripts/pixel_diff.py` | `pixel-diff` 实现 |
| `scripts/extract_fg.py` | `extract-fg` 实现 |
| `scripts/html_shot.py` | `html-shot`（headless Chrome/Edge） |
| `scripts/long_screenshot_ocr.py` | `long-ocr`：切带 → 分块 → 合并重叠 |
| `scripts/secret_scan.py` | 推送前密钥扫描（含 git 历史） |
| `skills/vision-core/SKILL.md` | 内核 skill：工具选择表、粗到细流程、场景路由 |
| `skills/<scene>/SKILL.md` | 4 个场景：`ui-feedback` / `ocr-extract` / `chart-reading` / `image-qa` |
| `skills/_template/` | 新场景模板与四步说明 |
| `references/` | `scenes.md` / `providers.md` / `accuracy.md` / `pitfalls.md`（装到 skill 侧供相对引用） |
| `tests/` | 合成夹具（`images/`、`fixtures/`）、`smoke_tests.md`、`make_test_fixtures.py` |
| `install.py` | 命令启动器 + skill 安装 |
| `.env.example` | 全部 `VISION_*` 变量的唯一清单 |

## 不要做的事

- 不要把场景逻辑写进 `core/` 或 `bin/`（那是上游的形态，本仓库就是为了改掉它）。
- 不要提交 `.env`、任何真实 `VISION_API_KEY`、cookie、`*.pem` / `*.key` / `cookies.txt`；
  推送前跑 `python scripts/secret_scan.py` 并处理每一条命中。
- 不要把 `tests/output/`（本地产物、可能是私人截图）加进版本库。
- 不要发明没在 `.env.example` / `core/vision_client.py` 里存在的环境变量名。
- 不要写死端点 URL / 模型 id / key：端点一律来自环境变量。
- 不要删除上游版权声明与 Credits 里的借鉴来源。
- 不要往 README / `llms.txt` / `AGENTS.md` 里写没核实过的命令、路径或文件名。
