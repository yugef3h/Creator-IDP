# ChatBI Demo - B站创作者视频数据中心

ChatBI MVP：自然语言 → SQL → 图表 + AI 解读。核心机制：LLM 生成 S2SQL（业务名）→ Translator 确定性转物理 SQL，防幻觉。

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
