# Provider 配置：多端点自动检测 + 故障转移

本套件支持同时配置**多个** OpenAI 兼容视觉端点。请求时自动探测已配置的端点，
当前端点失败（限流/额度耗尽/宕机）自动切到下一个——**不用手动切换**。
配置写在 `.env`（仓库根，或 `VISION_ENV_FILE` 指定的位置）。

## 配置写法

```ini
# 主 provider（必填，最简路径）
VISION_API_KEY=sk-...
VISION_BASE_URL=https://opencode.ai/zen/go/v1
VISION_MODEL=mimo-v2.5
LANG=zh

# 额外 provider（可选，自动检测 + 自动故障转移）
VISION_EXTRA_PROVIDERS=openrouter,local
VISION_PROVIDER_OPENROUTER_API_KEY=sk-...
VISION_PROVIDER_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
VISION_PROVIDER_OPENROUTER_MODEL=qwen/qwen3-vl-32b-instruct
VISION_PROVIDER_LOCAL_API_KEY=no-key-needed
VISION_PROVIDER_LOCAL_BASE_URL=http://localhost:8000/v1
VISION_PROVIDER_LOCAL_MODEL=my-vision-model

# 优先级（默认：primary 先，再按声明顺序）；把最可靠的放最前
VISION_PROVIDER_ORDER=local,primary,openrouter

# 可选：race 模式——所有 provider 并发，先到先得（会烧所有 provider 的额度）
# VISION_RACE=1
# VISION_RACE_TIMEOUT=45
```

## 怎么工作

1. **自动检测**：每次请求前扫描 `VISION_*` 环境变量，凡是三个必需字段（key/base/model）
   齐全的 provider 都加入候选。缺字段的 provider 会打 stderr 提示并跳过，不影响其他。
2. **故障转移**（默认）：按优先级依次尝试。当前 provider 重试（默认 2 次）后仍失败，
   自动切下一个；全部失败才报错（报第一个的错误）。
3. **race**（可选）：`VISION_RACE=1` 时所有 provider 并发请求，第一个有效响应胜出，
   其余取消。适合"有几个免费额度、想尽量快"的场景，代价是所有 provider 都扣额度。
4. **手动切**（最不推荐，但保留）：`VISION_PROVIDER_ORDER` 里只留一个名字即可固定用某家。

## 小贴士

- **主 provider 放最前**：故障转移默认按顺序走，把已验证的、最快的放 primary 或最前。
- **额度保护**：OpenCode Go 免费套餐快用完时会 429，加一个 OpenRouter 免费模型当备胎，
  请求自动回落，不再卡死。
- **本地兜底**：敏感图配一个本地 vLLM/Ollama 当最后一道，不外发数据。
- **race 慎用**：默认故障转移不烧多余额度；race 是"快"优先不是"省"优先。

| Provider | VISION_BASE_URL | 示例 VISION_MODEL |
|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini`, `qwen/qwen3-vl-32b-instruct` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| OpenCode Go（免费套餐） | `https://opencode.ai/zen/go/v1` | `mimo-v2.5` |
| 本地 vLLM | `http://localhost:8000/v1` | 你部署的模型名 |
| Ollama | `http://localhost:11434/v1` | `llama3.2-vision` 等 |
| LM Studio | `http://localhost:1234/v1` | 你加载的模型名 |

换/加 provider = 改环境变量，代码零改动。

## 每个 provider 的小贴士

### OpenRouter
- 模型名带供应商前缀：`openai/gpt-4o-mini`。免费/低成本模型很多，适合批量。
- 有些视觉模型（Llama 4 Scout 等）图表 JSON 输出不稳，参考 chart-reading 场景的校验 pass。

### OpenCode Go（作者实测主力）
- 免费套餐内可用，模型 `mimo-v2.5`（小米视觉模型）。
- **反爬**：该站 Cloudflare 会 1010 拦截"不像浏览器"的客户端。套件默认发送 Chrome
  User-Agent；对 base_url 含 `opencode.ai` 的自动加 `Origin`/`Referer`。若其他 provider
  也 1010，设置 `VISION_ORIGIN=<你的站点>`。
- 超大图 + 超长 prompt 会 HTTP 500 → 一律先缩图到最长边 1400（JPEG q88）。
- 请求可能较慢/抖动，默认重试 2 次、超时 180s，可按需调 `VISION_TIMEOUT` / `VISION_RETRIES`。

### OpenAI
- 官方端点不需要任何浏览器头，`VISION_USER_AGENT=` 置空发纯客户端请求亦可。

### 本地 / 离线
- 完全本地模型（vLLM/Ollama）没有任何外发数据，适合敏感内容。
- 图表提取精度参考 references/accuracy.md：Qwen3-VL / Nemotron 这类开源视觉模型在
  有标注图表上已达 99%+ 准确率。

## 环境变量总表（全部可选，除三个必需）

| 变量 | 默认 | 说明 |
|---|---|---|
| `VISION_API_KEY` | — | 必需。主 provider Bearer token |
| `VISION_BASE_URL` | — | 必需。主 provider 端点，不含 `/chat/completions` |
| `VISION_MODEL` | — | 必需。主 provider 视觉模型 id |
| `VISION_EXTRA_PROVIDERS` | 空 | 逗号分隔的额外 provider 名列表 |
| `VISION_PROVIDER_<NAME>_API_KEY` | — | 额外 provider 的 key（NAME 大写） |
| `VISION_PROVIDER_<NAME>_BASE_URL` | — | 额外 provider 的端点 |
| `VISION_PROVIDER_<NAME>_MODEL` | — | 额外 provider 的模型 |
| `VISION_PROVIDER_ORDER` | primary 优先 | 逗号分隔的优先级，如 `local,primary` |
| `VISION_RACE` | 关 | `1`=所有 provider 并发，先到先得 |
| `VISION_RACE_TIMEOUT` | `45` | race 模式等待秒数 |
| `LANG` | `zh` | 模型回答语言 |
| `VISION_ENV_FILE` | 自动探测 | 显式指定 env 文件 |
| `VISION_TIMEOUT` | `180` | 单次请求超时秒数 |
| `VISION_RETRIES` | `2` | 每个 provider 的 429/5xx/网络错误重试次数 |
| `VISION_TEMPERATURE` | provider 默认 | 设为 `0` 提高图表/数据读取确定性 |
| `VISION_USER_AGENT` | Chrome UA | 置空发送纯客户端 UA |
| `VISION_ORIGIN` | 自动(opencode.ai) | 需要 Origin/Referer 的 provider 用 |
| `VISION_MAX_TOKENS` | provider 决定 | 输出 token 上限 |
| `VISION_MIN_UPSCALE` | `800` | 小图自动放大到该最长边（LANCZOS），`0`=关闭；坐标不受影响 |
| `VISION_GLANCE_BIN` | 自动探测 | long-ocr 手动指定 glance 命令路径 |
