# ChatBI Demo - B站创作者视频数据中心

ChatBI MVP：自然语言 → SQL → 图表 + AI 解读。核心机制：NL → S2SQL（LLM生成bizName）→ Translator（确定性转物理SQL），防幻觉。

## 当前进度 (2026-06-30)

| 版本 | 状态 | 说明 |
|------|------|------|
| **V0.1 极简版** | ✅ 完成 | Streamlit 单文件，6/6 查询全通 |
| **V1.0 升级版** | ✅ 完成 | FastAPI + React，全部核心能力通过 |
| **文档** | ✅ 完成 | 4 份文档 |
| **数据库** | ✅ 已生成 | bilibili_demo.db，3 张表 |

## V1.0 核心能力验收

| Layer | 能力 | 状态 |
|-------|------|------|
| Layer 1 | NL2SQL 5-stage（趋势/分组/排名/分布/单值/过滤） | ✅ |
| Layer 2 | 多轮对话上下文 | ✅ |
| Layer 3 | Trie RAG + Knowledge Q&A（术语定义直返） | ✅ |
| Layer 4 | ECharts 5种图表 + 流式解读 + 日期修改 + 下钻 | ✅ |
| Layer 5 | Attribution（环比/同比 + 下钻推荐） | ✅ |
| - | 幻觉防御（未知实体安全拒绝） | ✅ |
| - | Mock 独立开发（4套 SSE mock） | ✅ |

## 快速开始

```bash
# V0.1
pip3 install streamlit jieba sqlglot openai python-dotenv pyyaml pandas faker
python3 generate_data.py && streamlit run app.py

# V1.0
pip3 install fastapi uvicorn streamlit jieba sqlglot openai python-dotenv pyyaml pandas
python3 generate_data.py && python3 -m uvicorn backend.main:app --port 8000
# 前端: cd frontend && npm install && npm run dev
```

## 关键设计

1. **语义层隔离**: LLM → S2SQL (bizName) → Translator (确定性) → Physical SQL
2. **规则优先**: 规则解析 80%场景 → LLM 兜底（V1.0 已禁用 LLM 兜底，杜绝幻觉）
3. **查询三分类**: NL2SQL / Knowledge Q&A / 拒绝，知识问答直返定义不执行 SQL
4. **意图分类**: distribution / ranking / trend / card 自动判定
5. **自动聚合**: 执行后检测粒度过细 → SUM 兜底聚合

## 文档

- [README](README.md) — 项目概览 + 双版本快速开始
- [Spec](docs/spec.md) — V0.1 + V1.0 双版本实现清单
- [Design Review](docs/design-review.md) — 架构决策 + 技术选型 + 风险
- [UI Design System](docs/ui-design-system.md) — CSS 变量 + 组件配方
- [多Agent协作规范](docs/多Agent协作规范.md) — PM + 技术校验师流程
