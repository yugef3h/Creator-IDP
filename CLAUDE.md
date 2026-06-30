# ChatBI Demo - B站创作者视频数据中心

ChatBI MVP：自然语言 → SQL → 图表 + AI 解读。核心机制：LLM 生成 S2SQL（业务名）→ Translator 确定性转物理 SQL，防幻觉。

## 当前进度 (2026-06-30)

| 模块 | 状态 | 说明 |
|---|---|---|
| **V0.1 极简版** | ✅ 完成 | 11 个文件，1441 行代码，全部可运行 |
| **V1.0 升级版** | 🟡 进行中 | backend/ 骨架，frontend/ 左右双栏布局已实现 |
| **文档** | ✅ 完成 | 4 份文档：spec / design-review / ui-design-system / 多Agent协作规范 |
| **数据库** | ✅ 已生成 | `bilibili_demo.db` (180K)，3 张表：videos / video_stats / fans |

### V0.1 各模块详情

| 文件 | 行数 | 功能 |
|---|---|---|
| `app.py` | 260 | Streamlit 主界面，含对话输入 + 图表渲染 + AI 解读 |
| `generate_data.py` | 227 | Faker 造数，生成 3 表 + dataset.yaml + exemplars.json |
| `rule_parser.py` | 281 | 5 种查询模式（排行/趋势/对比/明细/筛选）→ S2SQL |
| `translator.py` | 132 | bizName → 物理 SQL，确定性转换防幻觉 |
| `llm_parser.py` | 127 | DeepSeek few-shot prompt，规则失败时 LLM 兜底 |
| `dataset.yaml` | 139 | 语义模型：3 实体 + 12 指标 + 8 维度定义 |
| `exemplars.json` | 65 | 6 组 few-shot 示例 |
| `models.py` | 56 | QueryRequest / S2SQL / ChartConfig / QueryResult 4 个 dataclass |
| `trie_index.py` | 57 | jieba 分词 + Trie 前缀匹配，实体/指标识别 |
| `executor.py` | 38 | SQLite 执行 + pandas DataFrame 返回 |
| `start.sh` | 59 | 一键启动：检查依赖 → 造数 → 启动 Streamlit |

### V1.0 待实现

```
backend/
├── main.py               # ❌ FastAPI + SSE
├── context.py             # ❌ 多轮对话
├── correctors.py          # ❌ Schema/Grammar/Time Corrector
├── rag/embedding_store.py # ❌ FAISS + bge-small-zh
├── processors/            # ❌ LLM解读 + 环比 + 下钻
└── pipeline/              # ❌ 嵌入 V0.1 模块

frontend/                  # 🟡 5 个源文件，~400 行 TSX/CSS
├── src/App.tsx            # ✅ 左右双栏：左面板推荐问句 + 查询，右面板对话 + 图表
├── src/api.ts             # ✅ SSE 流式请求
├── src/store.ts           # ✅ zustand 状态管理
├── src/chart-utils.ts     # ✅ 图表类型自动选择
├── src/styles/variables.css # ✅ 完整 CSS 变量 + 双栏布局样式
├── src/main.tsx           # ✅ 入口
└── index.html             # ✅
```

## 双版本

| | V0.1 极简版 | V1.0 升级版 |
|---|---|---|
| **工时** | 3小时 | 14天 |
| **UI** | Streamlit 单文件 | React + ECharts |
| **后端** | 无 | FastAPI + SSE |
| **启动** | `streamlit run app.py` | `python main.py` + `npm run dev` |

## V0.1 极简版项目结构

```
chatbi-demo/
├── app.py                # Streamlit 单文件 (~200行)
├── generate_data.py      # 造数：SQLite + dataset.yaml + exemplars.json
├── models.py             # 4个 dataclass
├── trie_index.py         # jieba 分词 + 前缀匹配
├── rule_parser.py        # 5种查询模式 → S2SQL
├── llm_parser.py         # DeepSeek prompt + few-shot → S2SQL
├── translator.py         # bizName → 物理SQL（确定性）
├── executor.py           # SQLite 执行
├── dataset.yaml          # 语义模型定义
├── exemplars.json        # few-shot 示例
└── .env                  # DEEPSEEK_API_KEY
```

## V1.0 新增

```
backend/
├── main.py               # FastAPI + SSE
├── config.yaml            # 插件链注册
├── context.py             # 多轮对话
├── correctors.py          # Schema/Grammar/Time Corrector
├── rag/embedding_store.py # FAISS + bge-small-zh
├── processors/            # LLM解读 + 环比 + 下钻
└── pipeline/              # 嵌入 V0.1 模块

frontend/                  # React + Ant Design + ECharts + zustand
└── src/components/        # ChatInput, ChartPanel, ParseTip, ...
```

## 快速开始

```bash
# V0.1 极简版
pip install streamlit jieba sqlglot openai python-dotenv pyyaml
python generate_data.py && streamlit run app.py

# V1.0 升级版
pip install -r requirements.txt && python generate_data.py && python backend/main.py
cd frontend && npm install && npm run dev
```

## 关键设计决策

1. **语义层隔离**: LLM → S2SQL (bizName) → Translator (确定性) → Physical SQL
2. **双策略**: 规则解析优先 (80%) → LLM 兜底
3. **V0.1 极简栈**: Streamlit + SQLite + jieba + DeepSeek，4个 pip 包
4. **V1.0 全本地**: + FAISS + bge-small-zh，仅 DeepSeek API 一个外部依赖

## 文档索引

- [README](README.md) — 项目概览 + 双版本快速开始
- [可执行规格书](docs/spec.md) — V0.1 + V1.0 双版本实现清单
- [设计评审稿](docs/design-review.md) — 架构决策 + 技术选型 + 风险矩阵
- [UI 设计规范](docs/ui-design-system.md) — CSS变量 + 组件配方 + ECharts 主题
- [多Agent协作规范](docs/多Agent协作规范.md) — PM + 技术校验师流程
