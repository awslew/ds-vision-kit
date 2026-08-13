# 新增一个场景：4 步

场景层 = 一个目录 + 一个 SKILL.md，只描述"这个场景怎么做"，全部工具能力来自
vision-core（通用底座）。新增一个场景只需 4 步：

## 第 1 步 — 起目录和名字

```bash
mkdir skills/<scene-name>
cp skills/_template/SKILL.md.template skills/<scene-name>/SKILL.md
```

`<scene-name>` 用 kebab-case（如 `ocr-extract`、`chart-reading`）。SKILL.md 的
`name` 字段、`metadata.scene` 字段都填这个名字。

## 第 2 步 — 填 SKILL.md 六块

照模板填：触发场景 / 工作流（pass 序列）/ 关键 prompt / 输出格式 / 工具 /
来源。要点：

- **触发场景**要写"用户说什么话"会命中，而不是"这个场景是什么"。分发靠 description
  里的触发词，Claude Code 靠它选 skill。
- **关键 prompt 完整贴出来**，能复制就走，不要引用外部文件——prompt 是这个场景
  的灵魂（例如 ocr-extract 里"表格逐个枚举，一个都不能漏"就是从实测漏表 bug 提炼的）。
- **输出格式固定**，让主模型不用看图也能直接用。

## 第 3 步 — 接进分发表

在 `references/scenes.md` 的分发表里加一行：用户说 X → 场景名。同时在
`skills/vision-core/SKILL.md` 的分发小节加一行。

## 第 4 步 — 验证

用一张真实图跑通，并把这个场景的验证步骤写进 `tests/smoke_tests.md`（验收标准：
新手 clone → 配 env → 该场景用一张真实图跑通）。

---

## 场景层职责 vs 通用核心职责（别混）

| | 通用核心 (vision-core) | 场景层 (skills/<scene>) |
|---|---|---|
| 职责 | 命令 + provider + 像素工具 | 触发条件 + 工具 pass 流程 + prompt + 输出格式 |
| 例子 | glance/ground/detect/palette | ocr-extract 的"表格枚举 prompt" |
| 变化 | 几乎不变 | 想加什么识别任务就加什么 |
| 测试 | 命令级（一张图一个命令） | 场景级（一张图走完整流程） |

新增识别任务 = 新增场景，**不要**去改 vision-core 的命令。
