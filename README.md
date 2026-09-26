# 需求雷达 Demand Radar

> 每天自动从海外社区收集真实需求与痛点，AI 提炼成带评分的中文机会清单。

**在线面板：https://chama4682-ui.github.io/product-discovery-tools/**（手机可看）

给想找产品创业机会的人用：不用自己泡论坛，每天早上打开面板，就能看到 Hacker News 上新冒出来的真实需求——每条都是中文的，带机会评分、付费意愿判断和原文链接。

## 它每天做什么

```
GitHub Actions 定时（每天北京时间 06:00）
  → 抓取 Hacker News 最近 24h 的需求信号（Algolia 官方 API）
  → AI 分析（Agnes Flash，一次调用完成）：
       判断是否真实需求 → 一句话中文需求 → 分类 → 0-10 评分
       → 付费意愿（强/弱/无）→ 标题翻译 → 中文摘要
  → 按帖去重合并进 data/opportunities.json
  → GitHub Pages 面板自动更新
```

全链路 **零服务器、零月费**：GitHub Actions（采集）+ 仓库 JSON（存储）+ GitHub Pages（面板）+ API 官方免费接口。

## 面板功能

- 按评分降序排列，评分徽章分档（绿 ≥8 / 橙 6-7 / 灰其余）
- 筛选：来源、类别、最低评分；关键词搜索（中文标题/需求句/摘要）
- 只看感兴趣 / 隐藏已读（本地记忆，标记不上传）
- 每条卡片可展开看中文摘要、评分理由、英文原文，直达原帖

## 数据源

| 源 | 状态 | 说明 |
|---|---|---|
| Hacker News | ✅ 已接入 | Algolia 官方 API，免密钥，抓热帖与 Ask HN 痛点 |
| Reddit | 🔜 预留 | 待配置 OAuth 凭据后在 `config.json` 启用 |
| Product Hunt | 🔜 预留 | 待配置开发者 token 后启用 |

关注领域在 [`collector/config.json`](collector/config.json) 里改关键词即可，下一次运行生效。

## 本地运行（可选）

日常使用只需看面板。想手动跑一次或本地开发：

```bash
pip install -r requirements.txt -r requirements-dev.txt

pytest -q                        # 全量测试
python -m collector run --dry-run   # 只采集看统计，不调 AI 不写文件
python -m collector run          # 完整采集+分析（需 AGNES_API_KEY）
```

密钥放仓库根目录 `.env`（已被 gitignore）：`AGNES_API_KEY=...`

## 设计原则

- **不兜底**：LLM 输出经 json_schema 强制结构化 + pydantic 双重校验，任何异常显式失败（运行变红），不做静默重试；未写入的数据下轮自动重采，不丢失。
- **最高抽象**：依赖仅 `requests` + `pydantic`，面板为零构建单文件 HTML，无框架无打包。
- **密钥安全**：只存 GitHub Secrets 与本地 `.env`，绝不入库、不进日志。

## 合规说明

仓库公开（GitHub Pages 免费档要求），数据均来自公开社区内容并附原文链接；AI 分析由个人非商业用途的模型服务完成。使用 Reddit/Product Hunt 等平台数据时将遵守其官方 API 条款。

---
*由 AI 全程构建：需求调研、设计、实现、测试、部署均自动化完成；使用者无需编程基础。*
