# ChatBI - B站创作者视频数据中心

> 自然语言问数据 → SQL → 图表 + AI 解读。语义层防幻觉。

## 快速开始

### 前置

- Python 3.9+ + Node.js 18+
- DeepSeek API Key（[注册](https://platform.deepseek.com)，¥1/百万 token）

### 启动

```bash
cp .env.example .env           # 填入 DEEPSEEK_API_KEY

# 后端
pip3 install fastapi uvicorn streamlit jieba sqlglot openai python-dotenv pyyaml pandas faker
python3 generate_data.py        # 仅首次
python3 -m uvicorn backend.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev  # → http://localhost:5173
```

### 试试

- "最近7天播放量趋势"
- "各分区播放量排名"
- "点赞最多的5个视频"
- "深圳的粉丝有多少"
- "互动率怎么算"
- "最近30天新增粉丝的城市分布"

---

## 架构概览

```
用户: "最近7天各分区播放量怎么样"
         │
         ▼
┌─ Layer 3: RAG ────────────────┐  Trie 匹配 + Knowledge Q&A
│  "播放量" → views (metric)     │  术语定义直返，不执行 SQL
│  "分区"   → category (dim)    │
│  "最近7天" → DateConf{-7d}     │
└───────────────┬───────────────┘
                │
                ▼
┌─ Layer 1: NL → S2SQL → SQL ──┐  5-stage pipeline
│  MAPPING → PARSING →          │  规则解析优先，LLM 不接触物理表名
│  CORRECTING → TRANSLATING     │  Translator 确定性转物理 SQL
│  → EXECUTE                    │
└───────────────┬───────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌─ Layer 2 ───┐  ┌─ Layer 5 ──────────┐
│ 多轮对话     │  │ 智能归因             │
│ 上下文保持   │  │ LLM 解读 + 环比      │
│ + LLM 改写  │  │ + 下钻推荐           │
└──────────────┘  └─────────────────────┘
        │               │
        └───────┬───────┘
                ▼
┌─ Layer 4: Visualization ──────┐
│  自动图表 → ECharts 渲染      │
│  流式解读 · 日期修改 · 下钻   │
└───────────────────────────────┘
```

**核心防幻觉机制**：LLM 不接触物理表名/列名。它生成 S2SQL（`views`、`category` 等业务名），Translator 确定性转为物理 SQL。

---

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端框架 | FastAPI + uvicorn | Python AI 生态最成熟 |
| LLM | DeepSeek V3 (`deepseek-chat`) | ¥1/M tokens，中文最强性价比 |
| 数据库 | SQLite | Python 标准库，零配置 |
| 中文分词 | jieba | 最流行的中文分词 |
| SQL 解析 | sqlglot | 跨方言 SQL 解析/生成 |
| 前端框架 | React 18 + Vite 5 | 最快开发体验 |
| UI 组件 | Ant Design 5 | 成熟的企业级组件库 |
| 图表 | ECharts 5 | 国内最成熟的图表库 |
| 状态管理 | zustand | 轻量、TypeScript 友好 |

---

## 项目结构

```
chatbi-demo/
├── backend/
│   ├── main.py                 # FastAPI + SSE 流式
│   ├── config.yaml             # 插件链注册
│   ├── knowledge.py            # Knowledge Q&A 记忆层
│   ├── context.py              # 多轮对话上下文
│   ├── correctors.py           # Schema/Grammar/Time Corrector
│   ├── processors/             # 归因分析
│   │   ├── data_interpret.py   #   LLM 数据解读
│   │   ├── metric_ratio.py     #   环比/同比
│   │   └── dimension_recommend.py # 下钻推荐
│   └── rag/                    # 知识库（Embedding 待追加）
├── frontend/                   # React + ECharts
│   └── src/
│       ├── App.tsx             # 主界面 + 聊天 + 图表
│       ├── store.ts            # zustand 状态机
│       ├── api.ts              # SSE 客户端
│       ├── mockApi.ts          # 离线 Mock 模式
│       ├── chart-utils.ts      # 图表自动分类 + 切换
│       └── styles/             # CSS 变量
├── app.py                      # Streamlit 单文件（V0.1 演示用）
├── generate_data.py            # 一键造数
├── models.py                   # 数据模型
├── trie_index.py               # jieba 匹配
├── rule_parser.py              # 规则解析（意图分类）
├── translator.py               # S2SQL → 物理 SQL
├── executor.py                 # SQLite 执行 + 自动聚合
├── data/
│   ├── bilibili_demo.db
│   ├── dataset.yaml
│   └── exemplars.json
└── docs/
    ├── spec.md                 # 可执行规格书
    ├── design-review.md        # 设计评审稿
    ├── ui-design-system.md     # UI 设计规范
    ├── bugfixed.md             # Bug 修复记录
    └── 多Agent协作规范.md       # 协作流程
```

---

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/query` | POST | 核心查询（SSE 流式返回） |
| `/api/chat/history/{chatId}` | GET | 加载历史对话 |
| `/api/chat/history/{chatId}` | DELETE | 清除上下文 |
| `/api/health` | GET | 健康检查 |

SSE 事件流：`knowledge?` → `parse_info` → `query_result` → `summary_chunk`* → `done`

---

## 文档

- [可执行规格书](docs/spec.md) — 双版本实现清单 + 验收标准
- [设计评审稿](docs/design-review.md) — 架构决策、技术选型、风险矩阵
- [UI 设计规范](docs/ui-design-system.md) — CSS 变量、组件配方、ECharts 主题
- [Bug 修复记录](docs/bugfixed.md) — 12 个 bug 的根因与修复
- [多Agent协作规范](docs/多Agent协作规范.md) — PM + 技术校验师流程


## TODO

- 多租户隔离