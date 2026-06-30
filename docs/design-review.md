# ChatBI MVP 设计评审稿

> 版本：V1.0 | 日期：2026-06-30 | 状态：待评审

---

## 1. 项目概述

### 1.1 要解决的问题

做一个面向**B站创作者（UP主）** 的视频数据分析 ChatBI。用户用自然语言提问（如"最近7天各分区播放量怎么样"），系统自动将其转为 SQL 查询数据库，并生成可视化图表和 AI 解读。

### 1.2 核心挑战

| 挑战 | 传统方案 | 本项目方案 |
|------|---------|-----------|
| NL2SQL 幻觉 | LLM 直接生成物理 SQL，容易编造表名/字段 | **语义层隔离**：LLM 只生成业务名 SQL（S2SQL），确定性翻译器转物理 SQL |
| 术语多样性 | "播放量"=views，"观看量"=views，用户输入不可控 | **双索引 RAG**：Trie（精确/别名匹配）+ Embedding（语义兜底） |
| 复杂查询 | 追问、指标切换、下钻 | **上下文持久化**：保存完整 SemanticParseInfo，LLM 改写多轮问题 |
| 零部署验证 | 需要 MySQL、向量数据库等外部服务 | **全本地栈**：SQLite + FAISS + bge-small-zh，仅需 DeepSeek API Key |

---

## 2. 架构决策

### 2.1 语义层隔离（核心决策）

```
传统 NL2SQL:
  "最近播放量" → LLM → SELECT SUM(views) FROM video_stats  ← LLM 直接碰物理表名

本项目 S2SQL:
  "最近播放量" → LLM → SELECT SUM(views) FROM video_stats  ← 只生成 bizName
              → Translator(确定性代码) → SELECT SUM(v.views) FROM bilibili_demo.video_stats v
```

**为什么做这个决策**：
- LLM 可能编造物理表名和列名（幻觉的主要来源）
- 指标公式（如互动率 = `(点赞+投币+收藏)/播放量`）由 Translator 确定性计算，不依赖 LLM
- 数据库迁移时只改 Translator 配置，不改 LLM Prompt
- 同一 S2SQL 可以翻译到 MySQL/PG/ClickHouse 不同方言

**代价**：
- 需要维护语义模型定义（dataset.yaml）
- 新增指标/维度需要配置，不能"自动识别"

### 2.2 规则优先 + LLM 兜底

```
用户查询 → [Trie 匹配] → 成功(80%) → 规则解析 → S2SQL
              ↓ 失败
         [Embedding 匹配] → 成功(15%) → LLM 解析 → S2SQL
              ↓ 失败
         [返回"无法理解"]
```

**为什么**：
- 简单查询（"各分区播放量"）占大多数，规则解析零延迟、零成本、零幻觉
- 复杂查询（"对比知识区和生活区的投币率"）才需要 LLM
- 规则解析结果可作为 LLM few-shot 的参考

### 2.3 插件链架构

```yaml
# config.yaml — 唯一注册点
pipeline:
  mappers: [KeywordMapper, EmbeddingMapper]       # 可以加新的 mapper
  parsers: [RuleSqlParser, LLMSqlParser]          # 可以换 LLM
  correctors: [SchemaCorrector, GrammarCorrector, TimeCorrector]
  processors: [DataInterpretProcessor]            # 后续加 RatioCalc, DrillDown...
```

**优势**：增删功能只改配置不碰核心代码。后续加环比计算、下钻推荐只需新增 Processor。

### 2.4 全本地栈（零依赖服务）

| 组件 | 选型 | 零安装理由 |
|------|------|-----------|
| 数据库 | SQLite | `import sqlite3`（Python 标准库） |
| 向量库 | FAISS in-memory | `pip install faiss-cpu`，无服务进程 |
| Embedding | bge-small-zh-v1.5 | 24MB，本地运行，免费离线 |
| 分词 | jieba | `pip install jieba`，无词典服务 |
| SQL 解析 | sqlglot | `pip install sqlglot`，纯 Python |

**唯一外部依赖**：DeepSeek API（¥1/百万 token），可替换为任何 OpenAI 兼容 API。

---

## 3. 技术选型依据

### 3.1 后端：Python/FastAPI（而非 Java/SpringBoot）

| 维度 | Python | Java（SuperSonic 原版） |
|------|--------|------------------------|
| AI 生态 | LangChain 最成熟 | LangChain4j 功能落后 |
| 开发速度 | 3x | 1x |
| 依赖安装 | `pip install` | Maven + JDK + Spring |
| 对新手友好 | 是 | 否 |
| 性能 | 单用户足够 | 多用户场景更优 |

**结论**：MVP 阶段 Python 速度优势压倒一切。性能瓶颈在 LLM API 调用而非框架。

### 3.2 LLM：DeepSeek V3（而非 GPT-4o）

| 维度 | DeepSeek | GPT-4o |
|------|----------|--------|
| 中文质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 价格 | ¥1/M tokens | $2.5/M tokens (~¥18) |
| SQL 生成能力 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| API 兼容性 | OpenAI 兼容 | 原生 |
| 国内访问 | 直连 | 需要代理 |

**结论**：中文性价比最优。SQL 生成场景不需要 GPT-4o 级别的推理能力。

### 3.3 前端：React + Ant Design + ECharts

| 需求 | 选型 | 理由 |
|------|------|------|
| 聊天界面 | Ant Design | 成熟组件库，Message/Bubble/Input 开箱即用 |
| 图表 | ECharts | 国内最成熟，中文文档，支持渐变/动态 |
| 状态管理 | zustand | 比 Redux 轻 10x，适合中型状态 |
| 构建 | Vite | 比 Webpack 快 10x |

### 3.4 Embedding：本地 bge-small-zh（而非 OpenAI API）

| 维度 | bge-small-zh-v1.5 (本地) | text-embedding-3-small (API) |
|------|--------------------------|------------------------------|
| 成本 | 免费 | ~$0.02/百万 token |
| 速度 | < 50ms | ~200ms（网络延迟） |
| 中文质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 离线可用 | ✅ | ❌ |
| 模型大小 | 24MB | N/A |

**结论**：几百条 Schema 元素的向量化，24MB 模型绰绰有余。离线能力让演示零风险。

---

## 4. 数据模型设计

### 4.1 核心实体关系

```
SemanticSchema (全部知识)
  └── DataSetSchema (一个数据集)
        ├── Metric[]   (指标：可聚合的数值列，如 views、interaction_rate)
        ├── Dimension[] (维度：分组列，如 category、stat_date)
        └── Term[]     (术语：业务概念，如 "三连"、"爆款")

SchemaMapInfo (RAG 匹配结果)
  └── {datasetId → [SchemaElementMatch]}
        └── {elementId, matchedWord, type, similarity}

SemanticParseInfo (一轮查询的解析结果 — 所有层的桥梁)
  ├── metrics[] + dimensions[] + filters[] + dateInfo
  ├── sqlInfo: {parsedS2SQL, correctedS2SQL, querySQL}
  └── properties (可扩展)

QueryResult (执行结果 → 前端渲染)
  ├── columns[] + rows[]
  ├── chatContext (回写多轮对话)
  ├── textSummary (LLM 解读)
  └── recommendedDimensions (下钻推荐)
```

### 4.2 数据库表

```sql
-- 业务数据（由造数脚本生成）
videos (video_id, title, category, duration, publish_time)
video_stats (video_id, stat_date, views, likes, coins, favorites, shares, danmaku, comments)  -- 事实表
fans (fan_id, gender, age_group, city, follow_time)

-- 系统数据（运行时创建）
chat_context (chat_id, query_text, parse_info JSON, updated_at)
chat_history (id, chat_id, query_text, query_result JSON, parse_info JSON, created_at)
```

---

## 5. 接口设计

### 5.1 核心 API

```
POST /api/chat/query
  Request:  { queryText: string, chatId?: string }
  Response: SSE Stream (text/event-stream)
    event: parse_info      → { type: "parse_info", data: SemanticParseInfo }
    event: query_result    → { type: "query_result", data: QueryResult }
    event: summary_chunk   → { type: "summary_chunk", text: string }  // 流式输出
    event: done            → { type: "done", queryId: string, recommendedDimensions: [...] }
```

### 5.2 为什么用 SSE 而非 WebSocket

- SSE 是单向（server→client），正好匹配 ChatBI 查询流
- 比 WebSocket 简单：HTTP 原生支持，不需要握手/心跳
- FastAPI 原生支持 `StreamingResponse`
- 前端用 `EventSource` API 零依赖

### 5.3 前端状态驱动的 API 调用

```
用户发送 → [POST /api/chat/query] → SSE 逐步渲染
  下钻点击 → [POST /api/chat/query] → 同上
  图表切换 → 纯前端，不发请求
  日期选择 → [POST /api/chat/query] → 同上
  新对话 → 前端生成新 chatId → 清空本地状态
```

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| LLM 生成错误 S2SQL | 中 | 高 | Corrector Chain（3 个正确器）+ 规则解析优先 |
| Embedding 召回偏差 | 低 | 中 | Trie 优先 + Embedding 作为兜底 + 结果按 dataset 过滤 |
| DeepSeek API 不可用 | 低 | 高 | 规则解析覆盖 80% 查询 + 错误降级提示 |
| SQLite 并发限制 | 低 | 低 | MVP 单用户场景，SQLite 足够；生产迁移 PG |
| bge-small-zh 首次下载慢 | 中 | 低 | 文档说明 + 预下载脚本 |
| 多轮上下文累积过长 | 低 | 中 | 仅保存最近 3 轮的完整 SemanticParseInfo |
| 用户输入超出 Schema 范围 | 中 | 中 | Embedding 阈值过滤 + "无法理解"友好提示 + 示例问题引导 |

---

## 7. 不做的事情（MVP 明确边界）

| 不做 | 理由 | 后续版本 |
|------|------|---------|
| 用户登录/权限 | MVP 演示用 | V0.5 |
| 多数据源切换 | 只有 B站数据 | V0.5 |
| 自一致性投票（3 次 LLM 生成取多数） | 成本 3x，收益不大 | V0.3 |
| 环比/同比自动计算 | 需要额外查询，先做 LLM 解读 | V0.4 |
| 图表导出为 PNG | 非核心链路 | V0.5 |
| 用户反馈 → 示例记忆 | 需要反馈循环积累数据 | V0.5 |
| 知识库管理 UI | 直接改 YAML | V0.4 |
| 多 Agent 并行 | 单 Agent 足够 | V0.5 |
| kubernetes/容器化 | 本地 Python 进程即可 | V0.5 |

---

## 8. 成功标准

### 8.1 功能验收

- [ ] 10 类典型 B站分析问题，≥ 8 类能正确生成 SQL 并返回结果
- [ ] 规则解析覆盖 ≥ 60% 的测试用例
- [ ] LLM 解析不编造不存在的表/列（SchemaCorrecter 捕获率 100%）
- [ ] 多轮对话 2 轮内上下文正确改写

### 8.2 性能指标

| 指标 | 目标 |
|------|------|
| Trie 匹配延迟 | < 10ms |
| Embedding 匹配延迟 | < 100ms |
| 规则解析延迟 | < 5ms |
| LLM 解析延迟 | < 3s |
| 端到端查询（简单问题） | < 1s |
| 端到端查询（LLM 问题） | < 5s |
| 前端首屏加载 | < 2s |

### 8.3 演示可用性

- [ ] `pip install -r requirements.txt && python main.py` 即可启动后端
- [ ] `npm install && npm run dev` 即可启动前端
- [ ] 不需要安装任何数据库、向量库、消息队列
- [ ] 仅需配置一个环境变量：`DEEPSEEK_API_KEY`

---

## 9. 项目结构推演

```
chatbi-demo/
├── backend/
│   ├── main.py                    # FastAPI app + SSE + CORS
│   ├── config.yaml                # 插件链注册 + 模型配置
│   ├── models.py                  # 全部 dataclass 模型
│   ├── context.py                 # 多轮对话上下文管理
│   ├── pipeline/
│   │   ├── mappers.py             # KeywordMapper, EmbeddingMapper, TimeRangeParser
│   │   ├── parsers.py             # RuleSqlParser, LLMSqlParser
│   │   ├── correctors.py          # SchemaCorrector, GrammarCorrector, TimeCorrector
│   │   ├── translator.py          # S2SQL → Physical SQL
│   │   └── executor.py            # SQLite 执行器
│   ├── rag/
│   │   ├── trie_index.py          # jieba + marisa-trie 双索引
│   │   └── embedding_store.py     # FAISS + bge-small-zh
│   └── processors/
│       ├── data_interpret.py      # LLM 解读
│       ├── metric_ratio.py        # 环比/同比（Phase 5）
│       └── dimension_recommend.py # 下钻推荐（Phase 5）
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── pages/ChatPage.tsx
│   │   ├── components/
│   │   │   ├── ChatHeader.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── UserBubble.tsx
│   │   │   ├── BotBubble.tsx
│   │   │   ├── ParseTip.tsx
│   │   │   ├── ChartPanel.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── BarChart.tsx
│   │   │   ├── LineChart.tsx
│   │   │   ├── PieChart.tsx
│   │   │   ├── DataTable.tsx
│   │   │   ├── InsightMarkdown.tsx
│   │   │   ├── DrillDownChips.tsx
│   │   │   ├── RatioBadges.tsx
│   │   │   ├── AgentTip.tsx
│   │   │   └── ConversationSidebar.tsx
│   │   ├── store.ts
│   │   ├── api.ts
│   │   ├── chart-utils.ts
│   │   └── styles/
│   │       └── variables.css       # CSS 变量（来自 ui-design-system.md）
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── scripts/
│   └── generate_data.py            # 一键造数
├── data/
│   ├── bilibili_demo.db
│   ├── dataset.yaml
│   └── exemplars.json
├── docs/
│   ├── spec.md                     # 本文件
│   └── design-review.md            # 设计评审稿
├── requirements.txt
├── .env.example
└── README.md
```

---

## 10. 异常处理 & 降级（MVP 最小版）

### 10.1 降级链

```
规则解析失败 → LLM 解析
LLM API 超时(5s) → 返回规则解析结果(如有) 或 "查询超时，请简化问题重试"
LLM API 不可用 → 仅用规则解析，前端提示 "AI 增强暂不可用，基础查询正常"
SQL 执行失败 → 返回原始 SQL + 错误信息，不做猜测性重试
Embedding 模型未就绪 → Trie 匹配独立工作，不阻塞
```

### 10.2 错误信息分级

| 级别 | 表现 | 示例 |
|------|------|------|
| 用户可见 | 前端 Toast + 聊天卡片 | "未识别到指标，试试：播放量、点赞数..." |
| 开发调试 | 后端日志 | `[Corrector] field 'view_count' not in schema, did you mean 'views'?` |

**MVP 原则**：不崩溃。任何异常都返回可读提示，不白屏、不 500。

---

## 11. 安全性（MVP 最小版）

| 事项 | 做法 | 理由 |
|------|------|------|
| API Key | `.env` 文件，不提交 git，前端不暴露 | 仅后端使用 |
| SQL 注入 | sqlite3 参数化查询，Translator 生成结构化 AST | 非字符串拼接，无注入风险 |
| 输入长度 | 限制 500 字符 | 防止滥用 + prompt 注入 |
| CORS | 仅允许 `localhost:5173` | MVP 阶段本地运行 |

**MVP 不做**：用户认证、权限控制、速率限制。

---

## 12. 测试策略（MVP 最小版）

| 层级 | 测什么 | 怎么测 |
|------|--------|--------|
| **数据** | 造数脚本生成的数据符合 schema | `python scripts/generate_data.py` 后手动 SQL 抽查 |
| **Pipeline** | 5 阶段每个阶段输入/输出正确 | 1 个 pytest 文件 `backend/test_pipeline.py`，覆盖 10 条核心查询 |
| **API** | SSE 事件顺序和内容 | curl + 浏览器手动验证 3 条查询 |
| **前端** | 组件渲染 + 交互流程 | 浏览器手动走附录 B 的 10 条验证流 |

```python
# backend/test_pipeline.py 示例结构
TEST_CASES = [
    {"query": "最近7天播放量趋势",    "expect_mode": "METRIC_TREND", "expect_metric": "views"},
    {"query": "各分区播放量排名",      "expect_mode": "METRIC_GROUPBY", "expect_dim": "category"},
    {"query": "点赞最多的5个视频",     "expect_mode": "METRIC_ORDERBY", "expect_limit": 5},
    # ... 共 10 条，与 spec 附录 B 对齐
]
def test_pipeline():
    for tc in TEST_CASES:
        result = run_pipeline(tc["query"])
        assert result is not None
```

---

## 13. 日志 & 调试（MVP 最小版）

```python
# 每个 Pipeline 阶段输出一行结构化日志
# config.yaml 中设 LOG_LEVEL=DEBUG 开启

[MAPPER]   tokens=['最近', '7天', '播放量', '趋势'] → matched=[views(1.0), stat_date(0.9)]
[PARSER]   mode=RULE, pattern=METRIC_TREND → S2SQL generated
[CORRECTOR] SchemaCorrector: 0 fixes | GrammarCorrector: added GROUP BY
[TRANSLATOR] views→SUM(v.views), stat_date→v.stat_date | JOIN videos
[EXECUTOR]  12 rows, 2 cols, 8ms
[LLM]       deepseek-chat, 234 tokens, 1.2s
```

**MVP 原则**：`logging.info()` 即可，每阶段一行，查问题够用。不引入日志框架。

---

## 14. 时序 & 依赖（MVP 关键路径）

```
Phase 1 (1天) ──┬── Phase 2 (5天) ── Phase 3 (2天) ── Phase 4 (5天) ── Phase 5 (3天)
                │                    │
                │                    └── Pipeline 各阶段可独立测试
                │                        Translator + Executor 不依赖 LLM
                │
                └── 数据就绪后，前后端可并行：
                    Phase 2-3 (后端) ∥ Phase 4 (前端 mock 数据先行)
```

**单人串行** 16 天。**两人并行**：后端做 Phase 1→2→3，前端同时 mock 做 Phase 4，最后集成 ≈ 10 天。

---

## 15. 参考

- [DeepSeek API 文档](https://platform.deepseek.com/api-docs)
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- [sqlglot](https://github.com/tobymao/sqlglot) — SQL 解析器
