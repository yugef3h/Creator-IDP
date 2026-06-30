# ChatBI - B站创作者视频数据中心

> 自然语言问数据 → SQL → 图表 + AI 解读。语义层防幻觉。

两个版本：**V0.1 极简版**（3小时，Streamlit 一把梭）和 **V1.0 升级版**（React + FastAPI 完整产品）。

---

## V0.1 极简版（3分钟启动）

### 前置

- Python 3.10+
- DeepSeek API Key（[注册](https://platform.deepseek.com)，¥1/百万 token）

### 启动

```bash
cp .env.example .env           # 填入 DEEPSEEK_API_KEY
pip install streamlit jieba sqlglot openai python-dotenv pyyaml
python generate_data.py        # 仅首次
streamlit run app.py           # → http://localhost:8501
```

### 试试

- "最近7天播放量趋势"
- "各分区播放量排名"
- "点赞最多的5个视频"
- "互动率是多少"
- "对比知识区和生活区的投币率"

---

## V1.0 升级版（完整产品）

### 前置

- Python 3.10+ + Node.js 18+
- DeepSeek API Key

### 启动

```bash
# 后端
pip install -r requirements.txt
python scripts/generate_data.py
python backend/main.py            # → http://localhost:8000

# 前端
cd frontend && npm install && npm run dev  # → http://localhost:5173
```

---

## 架构概览

```
用户: "最近7天各分区播放量怎么样"
         │
         ▼
┌─ RAG (Layer 3) ──────────────┐  Trie + Embedding 双索引
│  "播放量" → views (metric)    │  V0.1: 仅 Trie
│  "分区"   → category (dim)    │  V1.0: + Embedding
│  "最近7天" → DateConf{-7d}     │
└───────────────┬───────────────┘
                │
                ▼
┌─ NL2SQL (Layer 1) ───────────┐
│  Mapping → Parsing →          │  LLM 生成 S2SQL（业务名）
│  Correcting → Translating    │  V0.1: prompt约束替代Corrector
│  → Execute                    │  V1.0: Corrector Chain
└───────────────┬───────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌─ Layer 2 ───┐  ┌─ Layer 5 ──────────┐
│ 多轮对话     │  │ 智能归因             │
│ V0.1: ❌    │  │ V0.1: ❌            │
│ V1.0: ✅    │  │ V1.0: ✅            │
└──────────────┘  └─────────────────────┘
        │               │
        └───────┬───────┘
                ▼
┌─ Visualization (Layer 4) ─────┐
│  V0.1: Streamlit 原生图表     │
│  V1.0: ECharts 5 种图表       │
└───────────────────────────────┘
```

**核心防幻觉机制**：LLM 不接触物理表名/列名。它生成 S2SQL（`views`、`category` 等业务名），Translator 确定性转为物理 SQL。

---

## 版本对比

| | V0.1 极简版 | V1.0 升级版 |
|---|---|---|
| **工时** | 3小时 / 1人 | 14天 / 1人 |
| **启动** | `streamlit run app.py` | `python main.py` + `npm run dev` |
| **文件数** | ~10 | ~40 |
| **UI** | Streamlit | React + Ant Design + ECharts |
| **后端** | 无 | FastAPI + SSE |
| **RAG** | Trie 精确匹配 | Trie + Embedding 双索引 |
| **多轮对话** | ❌ | ✅ |
| **归因分析** | ❌ | ✅ |
| **流式输出** | ❌ | ✅ SSE |
| **图表切换** | ❌ | ✅ 5 种 + 切换 |

## V0.1 文件清单

```
chatbi-demo/
├── app.py                # Streamlit 单文件
├── generate_data.py      # 造数
├── models.py             # 数据模型
├── trie_index.py         # jieba 匹配
├── rule_parser.py        # 5 种查询模式
├── llm_parser.py         # DeepSeek 兜底
├── translator.py         # bizName→物理SQL
├── executor.py           # SQLite 执行
├── .env
└── dataset.yaml          # 语义模型（生成）
```

## V1.0 新增

```
chatbi-demo/
├── backend/               # FastAPI + SSE
│   ├── main.py
│   ├── config.yaml
│   ├── context.py
│   ├── pipeline/          # 嵌入 V0.1 模块
│   ├── rag/
│   │   └── embedding_store.py  # 新增 FAISS
│   ├── correctors.py      # 新增
│   └── processors/        # 新增 3 个
└── frontend/              # React + ECharts
    └── src/components/    # 12 个组件
```

---

## 升级路线

| 版本 | 内容 | 基础 |
|------|------|------|
| **V0.1** | 单轮 NL2SQL + 图表，Streamlit 一把梭 | 从零 |
| **V1.0** | FastAPI + React 完整产品 | V0.1 核心模块复用 |
| V1.1 | 多轮对话 | V1.0 |
| V1.2 | 归因分析（解读/环比/下钻） | V1.0 |
| V2.0 | PostgreSQL + Docker 部署 | V1.2 |

---

## 文档

- [可执行规格书](docs/spec.md) — V0.1 + V1.0 双版本实现清单 + 验收标准
- [设计评审稿](docs/design-review.md) — 架构决策、技术选型、风险矩阵、降级策略
- [UI 设计规范](docs/ui-design-system.md) — CSS 变量、组件配方、ECharts 主题
