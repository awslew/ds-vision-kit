# 避坑清单

踩过的坑，逐个记录根因和解法。新 provider/新场景先看这里。

## 一、Windows 特有

1. **GBK 解码崩子进程**：中文 Windows locale 是 GBK，`subprocess.run(text=True)` 不带
   `encoding=` 时按 GBK 解码子进程的 UTF-8 输出 → 读线程 UnicodeDecodeError，stdout
   变空/报 None。**解法**：子进程调用一律显式 `encoding="utf-8", errors="replace"`
   （已修进 scripts/long_screenshot_ocr.py 的 run_glance）。
2. **无扩展名 shebang 脚本不能 exec**：Windows 上直接运行 `#!/usr/bin/env python3` 的
   无 `.py` 后缀脚本 → WinError 193。**解法**：`command_for_path` 检测到无后缀/python
   shebang 就用 `[sys.executable, str(path)]` 跑（已修）。
3. **路径层级越界**：`Path.parents[3]` 在仓库层级不足 4 层时 IndexError。**解法**：
   先查 `len(parents)` 再取值（已修）。
4. **Git Bash PATH 对无扩展名脚本免疫**：`shutil.which("glance")` 在 Windows 找不到
   extensionless shim → `resolve_glance_command` 会追加试 `.bat`/`.cmd`/`.exe`，且能
   找到仓库内置 bin/glance（已修）。

## 二、Provider / 网络

5. **Cloudflare 1010 反爬**：opencode.ai/zen 拦截"不像浏览器"的客户端。**解法**：默认
   发 Chrome UA；base_url 含 opencode.ai 时自动加 Origin/Referer；其他 provider 用
   `VISION_ORIGIN` 手动加。
6. **超大图 + 长 prompt → HTTP 500**：图片过大、prompt 过长会触发 500。**解法**：
   一律先缩到最长边 1400（JPEG q88）再送。坐标按缩放图，映射回原图乘系数。
7. **429/5xx/断流**：已内置重试（默认 2 次、退避 2s/4s）和 180s 超时。批量跑还超时
   就调 `VISION_TIMEOUT` / `VISION_RETRIES`。错误信息里 API key 会打码。
8. **输出超长**：OCR/聊天记录类输出可能超 provider 的 max_tokens → 用
   `VISION_MAX_TOKENS` 或走 long-ocr 分段。
9. **确定性**：图表/数据读取想要稳定输出，设 `VISION_TEMPERATURE=0`。

## 三、视觉模型行为（prompt 层）

10. **多表格页面漏表**：整页 OCR 常只转录第一个表。**解法**：prompt 显式"这张图里有
    几个表格？每个都转 markdown，一个都不能漏"。这是 ocr-extract 的核心 prompt。
11. **ground 序数错位**："第 3 根柱"会指到第 2 根。**解法**：detect 全量枚举后再按
    特征/文字缩小，或直接按 label 定位。
12. **无标注图表系统性低估**：估读值普遍比真值低约 10（±2%）。**解法**：一律标注
    estimate:true + 误差范围，禁止当精确值。
13. **对比图必须一张调用**：两张图分开调 glance = 两次幻觉面。`glance a.png b.png -q`
    一次传俩。
14. **"变了没变"别问模型**：小变化对模型是舍入误差。`pixel-diff` 拿差异框 → glance
    --region 读内容。
15. **像素级事实别信 prose**：颜色/边框/高亮会被自信编造。颜色取 palette，几何取
    trace，差异取 pixel-diff。
16. **本地路径相对脚本而非 cwd**：部分脚本的输入路径相对脚本所在目录解析，调用时用
    绝对路径或先 cd。

## 四、OCR 长截图

17. **分段边界丢字**：长截图不分段整张送会因下采样丢字。**解法**：long-ocr 分段 +
    重叠合并；文字极小先 crop --scale 放大。
18. **聊天记录气泡归属**：普通 OCR 会把多行气泡拼成一段。**解法**：long-ocr --mode
    chat，按气泡拆消息并保留昵称。
