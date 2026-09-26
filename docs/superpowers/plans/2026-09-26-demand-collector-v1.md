# 需求收集器 v1 实施计划（Demand Collector v1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天自动从海外社区抓取需求信息，AI 提炼成带评分的中文机会清单，GitHub Pages 静态面板呈现。

**Architecture:** GitHub Actions cron（或本地定时）触发 Python 采集器 → 三源（v1 先 HN）官方 API 抓最近 24h 帖子 → Agnes 3.0 Flash 批量提取/翻译/打分 → 按 id 去重合并写入 `data/opportunities.json` 提交进仓库 → Pages 静态面板读取渲染。

**Tech Stack:** Python 3.12（requests + pydantic，测试 pytest）、零构建原生 HTML/JS 面板、GitHub Actions + Pages。

**Spec:** `docs/superpowers/specs/2026-09-26-demand-collector-design.md`（本计划从 spec 出发，执行者两份都要读）

## Global Constraints

- Python 3.12（本机 3.12.10），运行依赖仅 `requests` + `pydantic`，开发依赖 `pytest`。
- 全程无兜底、无吞错、无静默重试（spec §8/§6）：错误显式抛出。
- LLM 输出字段全中文（`title_zh`/`summary_zh`/`demand_zh`/`reason_zh`），一次调用完成提取+翻译+打分。
- 每批 20-30 条（配置 `batch_size`，默认 25）；`is_demand=false` 保留在数据但不进面板。
- 数据文件仅 `data/opportunities.json`，按 `id` 去重，保留 `retention_days`（默认 90）天。
- 密钥只进 GitHub Secrets 与本地 `.env`（gitignore），绝不入代码与日志。
- 面板为单文件 `panel/index.html`，零构建、原生 JS、全中文 UI、移动端可读。

## Review Focus

1. LLM 返回的 `id` 与批次不符或缺字段 → 该批显式报错，整轮失败，数据不写入（Task 4 测试 pin）。
2. `data/opportunities.json` 损坏 → 显式报错；不存在 → 视为首次运行空数据（Task 5 测试 pin）。
3. HN 某关键词 24h 零结果 → 空列表正常继续，不报错（Task 3 测试 pin）。
4. 正文超长 → 截断 2000 字符，序列化不炸（Task 3 测试 pin）。
5. 面板数据为空 → 显示空状态文案而非白屏（Task 6 浏览器验证 pin）。

## 与 spec 的偏差（已确认的理由，执行者知悉即可）

- **v1 只实现 HN 源**：Reddit app 注册与 Product Hunt token 需要用户账号操作，用户明确不做手动步骤；两者代码延后到拿到凭据时再写（避免写无法真实验证的投机代码），`config.json` 的 `enabled_sources` 留好扩展位。
- **仓库走 public**：GitHub Pages 免费档要求 public 仓库（spec §11 写了私有，免费计划不可行；数据本就来自公开社区，密钥在 Secrets）。
- **Actions 工作流推送可能被 OAuth token 的 workflow 权限拦截**：先实测；被拒则 v1 调度改用本机定时任务推数据（Pages 随 push 自动更新），Actions 作为后续一次性浏览器授权（`gh auth refresh -s workflow`）后的升级项。

---

### Task 1: 项目脚手架

**Files:**
- Create: `requirements.txt`（`requests`、`pydantic`、`pytest`）
- Create: `collector/__init__.py`（空）、`collector/config.json`
- Create: `.gitignore`（`.env`、`__pycache__/`、`*.pyc`、`.pytest_cache/`）、`.env.example`（`AGNES_API_KEY=`）
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `collector/config.json` 结构，后续所有模块读取：`{"enabled_sources": ["hn"], "hn": {"keywords": ["pain point", "struggle", "frustrating", "wish there was", "Ask HN"], "max_per_keyword": 30}, "model": "Agnes 3.0 Flash", "batch_size": 25, "retention_days": 90}`；以及加载函数。

- [ ] **Step 1: 写失败测试** `tests/test_config.py`：`load_config()` 返回 dict 且含 `enabled_sources == ["hn"]`、`batch_size == 25`；缺文件时抛 `FileNotFoundError`。
- [ ] **Step 2: 运行确认失败** `pytest tests/test_config.py -v` → FAIL（模块不存在）
- [ ] **Step 3: 实现其余脚手架文件 + `collector/__init__.py` 内 `load_config(path=None) -> dict`**（默认路径 `collector/config.json`，`json.load`）
- [ ] **Step 4: 运行确认通过** `pytest tests/test_config.py -v` → PASS
- [ ] **Step 5: 提交** `git add -A && git commit -m "chore: 项目脚手架与配置加载"`

### Task 2: 数据模型与去重合并

**Files:**
- Create: `collector/models.py`、`collector/dedupe.py`
- Test: `tests/test_dedupe.py`

**Interfaces:**
- Produces: pydantic 模型 `AIResult`（`is_demand: bool, demand_zh: str, category: str, score: int, willingness_to_pay: Literal["strong","weak","none"], reason_zh: str`）与 `Record`（`id: str, source: str, title_en: str, title_zh: str, text_en: str, summary_zh: str, url: str, author: str, created_at: datetime, captured_at: datetime, metrics: dict, ai: AIResult | None`）；函数 `merge_records(existing: list[Record], new: list[Record], retention_days: int) -> list[Record]`（按 `id` 去重、旧记录保留原 ai、`created_at` 降序、裁掉超保留期的记录）。

- [ ] **Step 1: 写失败测试**：新增与已有 id 重复时保留已有；`created_at` 降序；91 天前记录被裁掉；空列表输入正常。
- [ ] **Step 2: 运行确认失败** `pytest tests/test_dedupe.py -v` → FAIL
- [ ] **Step 3: 实现 `models.py`（pydantic v2）与 `dedupe.py`**
- [ ] **Step 4: 运行确认通过** → PASS
- [ ] **Step 5: 提交** `git commit -am "feat: 数据模型与按id去重合并"`

### Task 3: HN 采集器

**Files:**
- Create: `collector/fetch_hn.py`
- Test: `tests/test_fetch_hn.py`

**Interfaces:**
- Consumes: `config["hn"]`（keywords、max_per_keyword）。
- Produces: `fetch_hn(config: dict, session: requests.Session | None = None) -> list[Record]`（`ai=None`，`text_en` 截断 2000 字符，`id=f"hn-{objectID}"`，`metrics={"upvotes": points, "comments": num_comments}`）；零命中返回 `[]`；单关键词请求失败抛异常（由 Task 5 决定是否中断整轮）。

- [ ] **Step 1: 写失败测试**（monkeypatch `requests.Session.get` 返回构造的 Algolia 响应 `{"hits": [...]}`）：解析出 Record 字段正确；24h 之前的帖子被过滤；零 hits 返回 `[]`；`story_text` 超 2000 字符被截断。
- [ ] **Step 2: 运行确认失败** → FAIL
- [ ] **Step 3: 实现**：`GET https://hn.algolia.com/api/v1/search_by_date`，参数 `query=<kw>&tags=story&hitsPerPage=<max>&numericFilters=created_at_i><now-86400>`，逐关键词去重 objectID。
- [ ] **Step 4: 运行确认通过** → PASS
- [ ] **Step 5: 提交** `git commit -am "feat: HN Algolia 采集器"`

### Task 4: Agnes LLM 分析器

**Files:**
- Create: `collector/analyze.py`
- Test: `tests/test_analyze.py`

**Interfaces:**
- Consumes: `list[Record]`（`ai=None` 的新记录）。
- Produces: `analyze_records(records: list[Record], config: dict) -> list[Record]`（填好 `ai`、`title_zh`、`summary_zh`，按 `batch_size` 分批调 Agnes `/chat/completions`，`response_format={"type":"json_object"}`）；API 或校验失败抛异常。

- [ ] **Step 1: 写失败测试**（monkeypatch HTTP 响应）：分批数正确（60 条 → 3 批）；返回 JSON 缺 `id` 或 id 不在批次内 → 抛 `ValueError`；正常返回时 Record 的 `ai`/`title_zh`/`summary_zh` 被填充；`AGNES_API_KEY` 缺失 → 启动即抛错并指明缺哪个变量。
- [ ] **Step 2: 运行确认失败** → FAIL
- [ ] **Step 3: 实现**：base_url `https://apihub.agnes-ai.com/v1`，模型取 `config["model"]`；system prompt 固定中文要求（提取真实需求/痛点、0-10 评分、付费意愿、翻译标题、中文摘要）。
- [ ] **Step 4: 运行确认通过** → PASS
- [ ] **Step 5: 提交** `git commit -am "feat: Agnes 批量分析器"`

### Task 5: 运行入口

**Files:**
- Create: `collector/run.py`（支持 `python -m collector run` 与 `--dry-run`）- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: Task 1-4 全部函数。
- Produces: `main(dry_run: bool = False) -> int`；流程：读 `data/opportunities.json`（不存在=空，损坏=抛错）→ 按 `enabled_sources` 采集 → 过滤掉已有 id → `analyze_records` → `merge_records` → 写回 JSON；`--dry-run` 只采集并打印各源统计，不调 LLM 不写文件。

- [ ] **Step 1: 写失败测试**（monkeypatch fetch/analyze）：新数据合并写回；已有 id 不再送分析；损坏 JSON 抛错；`--dry-run` 不写文件。
- [ ] **Step 2: 运行确认失败** → FAIL
- [ ] **Step 3: 实现**（密钥从环境变量读；缺失且仓库根有 `.env` 时自行解析 `.env` 补上，不引第三方依赖）
- [ ] **Step 4: 全量测试** `pytest -v` → 全 PASS
- [ ] **Step 5: 提交** `git commit -am "feat: 采集运行入口"`

### Task 6: 中文面板

**Files:**
- Create: `panel/index.html`（内嵌 CSS/JS，fetch 绝对路径 `/data/opportunities.json`，本地以仓库根为服务根预览）

**Interfaces:**
- Consumes: `data/opportunities.json`（§5 结构）。
- Produces: 面板页面。

- [ ] **Step 1: 实现页面**：顶部筛选（来源/类别/评分阈值/搜索框）、卡片列表（中文标题、需求句、评分徽章、付费意愿、来源、原文链接、可展开英文原文）、localStorage 已读/感兴趣、按分排序、空状态文案。
- [ ] **Step 2: 本地验证**：构造含 3 条记录的临时 JSON，`python -m http.server` 起服务，用浏览器工具截图确认中文渲染、筛选、空状态三种状态可用。
- [ ] **Step 3: 提交** `git commit -am "feat: 中文机会面板"`

### Task 7: GitHub 交付

**Files:**
- Create: `.github/workflows/daily.yml`（cron `0 22 * * *` + `workflow_dispatch`，步骤：checkout → setup-python → pip install → pytest → `python -m collector run` → commit 数据）

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 远程仓库、Secrets、Pages 在线面板、定时管道。

- [ ] **Step 1: 建仓库并推送**：`gh repo create product-discovery-tools --public --source . --push`（用完整路径 `"/c/Program Files/GitHub CLI/gh.exe"`）
- [ ] **Step 2: 配置密钥**：写入本地 `.env`（gitignored，本地真实运行用）；`gh secret set AGNES_API_KEY`（供 Actions，key 不落任何被跟踪文件）
- [ ] **Step 3: 尝试推送 workflow**：直接 `git push`；若被拒（OAuth 缺 `workflow` scope），记录偏差，改由本机定时任务承担每日调度（`delayMinutes`/cron 每日 06:00 北京时间，任务内容：`python -m collector run` → commit → push），Actions 留作后续授权升级；推送成功则继续 Step 4。
- [ ] **Step 4: 开启 Pages**：`gh api repos/chama4682-ui/product-discovery-tools/pages -X POST -f source='{"branch":"main","path":"/"}'`（或 `branch build_type=legacy`），确认返回面板 URL。
- [ ] **Step 5: 首次真实运行**：本地 `python -m collector run`（真实 HN + 真实 Agnes），确认 `data/opportunities.json` 有 `is_demand=true` 的中文记录，push 后浏览器访问 Pages URL 截图确认面板在线。

### Task 8: 收尾验证

- [ ] **Step 1: 全量测试** `pytest -v` 全 PASS
- [ ] **Step 2: verification-before-completion**：对照 spec §1 成功标准逐条核对（自动更新、中文展示、零月费、零手动操作）
- [ ] **Step 3: 最终报告**：面板 URL、运行方式、后续升级项（Reddit/PH 凭据、Actions 授权）写入会话总结
