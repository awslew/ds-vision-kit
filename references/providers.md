# Provider 配置：任意 OpenAI 兼容视觉端点

本套件只认三个必需配置（`VISION_API_KEY` / `VISION_BASE_URL` / `VISION_MODEL`），
任何实现了 OpenAI 兼容 `/chat/completions`、支持 `image_url` 内容块的端点都能用。
配置写在 `.env`（仓库根，或 `VISION_ENV_FILE` 指定的位置）。

## 配置写法

```ini
VISION_API_KEY=sk-...
VISION_BASE_URL=https://openrouter.ai/api/v1
VISION_MODEL=qwen/qwen3-vl-32b-instruct
LANG=zh
```

| Provider | VISION_BASE_URL | 示例 VISION_MODEL |
|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini`, `qwen/qwen3-vl-32b-instruct` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| OpenCode Go（免费套餐） | `https://opencode.ai/zen/go/v1` | `mimo-v2.5` |
| 本地 vLLM | `http://localhost:8000/v1` | 你部署的模型名 |
| Ollama | `http://localhost:11434/v1` | `llama3.2-vision` 等 |
| LM Studio | `http://localhost:1234/v1` | 你加载的模型名 |

换 provider = 只改这三行，代码零改动。

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
| `VISION_API_KEY` | — | 必需。Bearer token |
| `VISION_BASE_URL` | — | 必需。端点，不含 `/chat/completions` |
| `VISION_MODEL` | — | 必需。视觉模型 id |
| `LANG` | `zh` | 模型回答语言 |
| `VISION_ENV_FILE` | 自动探测 | 显式指定 env 文件 |
| `VISION_TIMEOUT` | `180` | 单请求超时秒数 |
| `VISION_RETRIES` | `2` | 429/5xx/网络错误重试次数 |
| `VISION_TEMPERATURE` | provider 默认 | 设为 `0` 提高图表/数据读取确定性 |
| `VISION_USER_AGENT` | Chrome UA | 置空发送纯客户端 UA |
| `VISION_ORIGIN` | 自动(opencode.ai) | 需要 Origin/Referer 的 provider 用 |
| `VISION_MAX_TOKENS` | provider 决定 | 输出 token 上限 |
| `VISION_GLANCE_BIN` | 自动探测 | long-ocr 手动指定 glance 命令路径 |
