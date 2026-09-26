# 需求收集器 v1 设计文档（Demand Collector）

日期：2026-09-26
状态：设计已获用户逐节确认
项目：0001ProductDiscoveryTools

## 1. 背景与目标

用户想做一个 AI 驱动的互联网需求信息收集器，**目的是发现产品创业机会**：从海外社区的讨论中自动发现真实痛点/需求，提炼成带评分的机会清单，以中文网页面板呈现。

成功标准：

- 每天自动采集并更新，用户零操作；
- 面板上每条机会显示中文需求描述、评分、付费意愿、原文链接；
- 全链路零月费（GitHub Actions + Pages + 免费 API + 用户已有的 Agnes token 计划）；
- 用户本人不会代码，所有交互只通过面板和对话完成。

## 2. 已确认的关键决策

| 决策点 | 结论 | 来源 |
|---|---|---|
| 用途 | 找产品创业机会 | 用户确认 |
| 数据源 | 海外社区为主（中文平台反爬+法律风险，不做） | 用户确认 + 调研 |
| 产出形态 | 网页面板 | 用户确认 |
| 触发方式 | 定时自动（GitHub Actions cron） | 用户确认 |
| LLM | Agnes AI（OpenAI 兼容，base_url `https://apihub.agnes-ai.com/v1`），默认模型 `Agnes 3.0 Flash`，token 计划 key 由用户提供 | 用户提供 key + 文档调研 |
| 架构 | 方案 A：GitHub Actions 采集 → 数据 JSON 进仓库 → GitHub Pages 静态面板 | 用户在 A/B/C 中选定 |
| 语言 | 面板默认中文：标题翻译+摘要+需求句+理由全中文，点开看英文原文 | 用户要求"要看中文" |

## 3. 总体架构

```
GitHub Actions 每日 06:00 北京时间（UTC 22:00）cron 触发
  → collector 采集最近 24h 数据（三源独立，一源失败不影响其余）
  → Agnes 3.0 Flash 批量分析（提取+翻译+打分，一次调用完成）
  → 按 id 去重合并 → data/opportunities.json（git 提交）
  → push 触发 GitHub Pages 面板自动更新
```

无服务器、无数据库、无常驻进程。运行失败让 Action 显式变红，不做兜底。

## 4. 组件

### 4.1 collector/（Python 3.12，依赖仅 requests + pydantic）

| 模块 | 职责 |
|---|---|
| `fetch_hn.py` | Algolia HN Search API（免 key），按 config 关键词搜最近 24h 帖子 |
| `fetch_reddit.py` | Reddit OAuth（requests 直调，不引 PRAW），抓 config 中 subreddit 列表的 hot/new |
| `fetch_ph.py` | Product Hunt GraphQL API v2，抓每日上新产品 |
| `analyze.py` | 调 Agnes API，每批 20-30 条，强制 JSON 输出（见 §6） |
| `dedupe.py` | 按记录 id 去重，合并新旧数据，裁剪 90 天以前记录 |
| `run.py` | 入口：采集 → 分析 → 去重合并 → 写 `data/opportunities.json`；本地可 `python -m collector run --dry-run` 冒烟 |

### 4.2 collector/config.json（非密钥配置，用户可改）

关键词列表、subreddit 列表、模型名、评分展示阈值、保留天数（默认 90）。

### 4.3 panel/index.html（零构建，原生 JS 单文件）

读 `data/opportunities.json` 渲染。无框架、无构建步骤。

### 4.4 .github/workflows/daily.yml

cron 定时 + 支持手动 `workflow_dispatch` 触发；跑测试 → 采集 → commit 数据 → push。

## 5. 数据模型

`data/opportunities.json` 为对象数组，新记录在前：

```json
{
  "id": "hn-39271823",
  "source": "hn | reddit | ph",
  "title_en": "原标题",
  "title_zh": "AI 翻译的中文标题",
  "text_en": "正文截断 2000 字符",
  "summary_zh": "AI 中文摘要",
  "url": "原文链接",
  "author": "…",
  "created_at": "2026-09-25T12:00:00Z",
  "captured_at": "2026-09-26T22:15:00Z",
  "metrics": { "upvotes": 123, "comments": 45 },
  "ai": {
    "is_demand": true,
    "demand_zh": "一句话需求（中文）",
    "category": "dev-tools",
    "score": 8,
    "willingness_to_pay": "strong | weak | none",
    "reason_zh": "中文判断理由"
  }
}
```

`is_demand=false` 的记录不进入面板（仍留档）。id 规则：`hn-<item id>`、`reddit-<fullname>`、`ph-<date>-<slug>`。

## 6. LLM 分析设计

- OpenAI 兼容 `/chat/completions`，`response_format: {"type": "json_object"}`。
- 每批 20-30 条帖子一次调用，输出结构化数组，字段见 §5 的 `ai` 块 + `title_zh`/`summary_zh`。提取、翻译、打分在同一次调用完成，不做两段式；质量不足时只改 config 模型名为 `Agnes 2.5 Pro`，零代码改动。
- 失败处理：无重试风暴、无兜底分支——批内任一批失败则本次运行整体报错退出（Action 变红），数据不写入；未写入的记录下轮会重新采集，不丢失。

## 7. 面板功能

默认按评分降序；筛选（来源 / 类别 / 日期范围）；关键词搜索（中文标题+需求句）；每条卡片显示中文标题、需求句、评分、付费意愿徽章、来源徽章、原文外链；点开看英文原文与摘要；localStorage 标记已读/感兴趣；移动端可读。

## 8. 错误处理

- 三源各自独立 try，单源失败记录到运行日志但继续其余源；仅当 LLM 分析失败或写数据失败才整体失败。
- 所有密钥缺失在启动时显式报错并提示缺哪个。
- 不写 fallback 路径、不吞错、不静默重试。

## 9. 测试

- pytest 覆盖：各源响应解析（用录制的 fixture JSON）、去重合并逻辑、config 校验。
- LLM 调用在测试中 mock；不打真实 API。
- 冒烟：`python -m collector run --dry-run` 只采集+打印统计，不写文件不调 LLM。

## 10. 安全

- 密钥（`AGNES_API_KEY`、`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`PH_TOKEN`）只存在于 GitHub Secrets 与本地 `.env`（gitignore），绝不入库、绝不进日志。
- 用户在对话中提供过的 Agnes key 同样只落 Secrets/.env。

## 11. 上线步骤

代码侧（AI 用 gh CLI 代办）：git init、建 GitHub 私有仓库并推送、配 Secrets、开启 GitHub Pages（部署根目录）、跑首次采集验证。

用户侧仅两件（一次性，AI 提供逐步指引）：
1. Reddit 注册一个 "script" 类型 app，拿 client_id / client_secret；
2. Product Hunt 申请 developer token。

## 12. 明确不做（v1 非目标）

X/Twitter（API 不可用）、中文平台硬逆向（法律风险）、语义/embedding 去重（v1 按 id 即可）、用户系统与登录、服务端、两段式 LLM 管道、数据库。

## 13. 调研依据（2026-09）

- 数据源约束：HN Algolia/Firebase API 免费免 key；Reddit 官方 API 免费档 100 QPM、禁商用但个人使用可，无凭据 `.json` 端点已大面积 403；X 免费档基本只写不读；Product Hunt GraphQL 免费（6250 points/15min）；GummySearch 因 Reddit API 政策于 2025-11 关停（单一平台依赖风险的前车之鉴）。
- 赛道：GitHub 无高星标杆（最高 idea-validation-agents ≈468★，为 agent skill 而非自动管道），开源处于空窗期；成熟模式为「抓取→清洗→LLM 提取/打分→输出」四层管道；小模型批量初筛是业界共识省成本做法。
