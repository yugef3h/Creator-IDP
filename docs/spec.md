# ChatBI MVP 可执行规格书

> 业务：B站创作者视频数据分析 | 架构：NL → S2SQL → Physical SQL | 双版本：极简演示 + 完整产品

---

## 版本总览

| | V0.1 极简版 | V1.0 升级版 |
|---|---|---|
| **目标** | 3小时跑通核心链路，可演示 | 完整产品形态 |
| **UI** | Streamlit 单文件 | React + Ant Design + ECharts |
| **后端** | 无（Streamlit 内嵌） | FastAPI + SSE 流式 |
| **RAG** | Trie 精确匹配 | Trie + Embedding 双索引 |
| **解析** | 规则优先 + LLM 兜底 | 规则优先 + LLM 兜底 |
| **纠正** | LLM prompt 约束 | Corrector Chain（3个正确器） |
| **多轮对话** | ❌ | ✅ 上下文保持 + LLM 改写 |
| **归因分析** | ❌ | ✅ LLM解读 + 环比 + 下钻推荐 |
| **图表** | Streamlit 原生 + matplotlib 兜底 | ECharts 5 种图表 + 自动分类 |
| **文件数** | ~10 个 | ~40 个 |

---

## 共享基础：两个版本通用的模块

以下模块 V0.1 和 V1.0 完全共用，一次写好两个版本都能用：

| 文件 | 行数 | 说明 | 并行 |
|------|------|------|------|
| `generate_data.py` | ~80 | 造数：SQLite + dataset.yaml + exemplars.json | 独立 |
| `models.py` | ~50 | 4 个 dataclass（SchemaElement, SemanticParseInfo, QueryResult...） | 独立 |
| `trie_index.py` | ~60 | jieba 分词 + 前缀/后缀匹配 | 依赖 models |
| `rule_parser.py` | ~100 | 5 种查询模式匹配 → S2SQL 生成 | 依赖 models |
| `translator.py` | ~80 | bizName → 物理列名/表达式 + JOIN + LIMIT | 依赖 models |
| `executor.py` | ~30 | sqlite3 执行 → 返回 QueryResult | 独立 |
| `llm_parser.py` | ~60 | DeepSeek prompt + few-shot → S2SQL | 依赖 trie_index |

**关键**：这 7 个模块约 460 行，是系统的核心引擎。V0.1 用 Streamlit 把它们粘起来；V1.0 把它们嵌入 FastAPI 插件链。

---

# V0.1 极简版（3小时）

## V0.1 目标

```
用户输入 "最近7天各分区播放量"
  → Streamlit 聊天框
  → Trie 匹配到 views + category + DateConf
  → 规则解析生成 S2SQL
  → Translator 转物理 SQL
  → SQLite 执行
  → Streamlit 显示柱状图 + 表格
```

## V0.1 文件清单

```
chatbi-demo/
├── app.py                # Streamlit 单文件 (~200行)，集成所有模块
├── generate_data.py      # 造数脚本
├── models.py             # 数据模型
├── trie_index.py         # Trie 匹配
├── rule_parser.py        # 规则解析（5模式）
├── llm_parser.py         # LLM 解析（兜底）
├── translator.py         # S2SQL → 物理SQL
├── executor.py           # SQLite 执行
├── dataset.yaml          # 语义模型（造数时生成）
├── exemplars.json        # few-shot（造数时生成）
├── .env                  # DEEPSEEK_API_KEY
└── README.md
```

## V0.1 时间分配

### 第1小时：数据 + 核心模块（可 3 人并行）

| 分钟 | 人A | 人B | 人C |
|------|-----|-----|-----|
| 0-20 | `generate_data.py` 造数 | `trie_index.py` | `translator.py` + `executor.py` |
| 20-40 | `models.py` | `llm_parser.py` | 调试 translator |
| 40-60 | `rule_parser.py` | 调试 llm_parser | 联调 A 的 parser |

> 人B、人C 在 0-20 分钟可先用硬编码的 models 桩开始写，等人A交出 models.py 后替换。

### 第2小时：集成 + LLM 兜底

| 分钟 | 人A | 人B | 人C |
|------|-----|-----|-----|
| 0-30 | `app.py` Streamlit UI 骨架 | 联调 rule_parser + trie_index | 联调 translator + executor |
| 30-60 | app.py 集成规则解析路径 | 集成 LLM 解析路径 | 准备 5 条演示查询 + 端到端测试 |

### 第3小时：打磨 + 演示

| 分钟 | 全员 |
|------|------|
| 0-20 | 走 5 条演示查询，修 bug |
| 20-40 | UI 优化（错误提示、示例问题、加载状态） |
| 40-60 | README + 录屏/截图 |

> **单人开发**：按 A→B→C 顺序串行，约 4-5 小时。关键路径是 造数→模型→解析→集成。

## V0.1 砍掉清单

| 砍掉 | 理由 | 怎么弥补 |
|------|------|---------|
| ❌ Embedding / FAISS | 首次下载 bge 模型 10 分钟 | 把全部 schema 元数据注入 LLM prompt，24 个元素不超过 500 token |
| ❌ 多轮对话 | 需要上下文持久化 + LLM 改写 | 用户每次输入完整问题 |
| ❌ Corrector Chain | 3 个正确器开发量大 | LLM prompt 强约束："必须用聚合函数、GROUP BY 维度必须在 SELECT 中" |
| ❌ React 前端 | npm install 5分钟 + 写组件半天 | Streamlit 原生 `st.chat_input` + `st.bar_chart` + `st.dataframe` |
| ❌ SSE 流式 | 需要 FastAPI + EventSource | `st.spinner("查询中...")` + 一次性返回 |
| ❌ 归因分析 | LLM解读/环比/下钻均需额外开发 | 用户直接看图表+表格，自己判断 |
| ❌ 自一致性投票 | 3 次 LLM 调用 | 单次调用 + temperature=0.1 |

## V0.1 各模块要点

### generate_data.py（与人B、人C并行，先写）

```python
# 精简到 3 张表、1000 行事实数据即可（3小时演示够用）
# 输出：bilibili_demo.db + dataset.yaml + exemplars.json
# 50 视频 × 8 分区 × 30 天 = 足够演示
```

### models.py（20分钟，人A交付给人B和人C）

```python
@dataclass
class SchemaElement:
    biz_name: str       # "views"
    name: str           # "views"（物理列名）
    alias: str          # "播放量,播放数"
    data_type: str      # "NUMERIC" | "DATE" | "CATEGORY"
    default_agg: str    # "SUM" | "COUNT" | "AVG"
    expression: str     # 派生指标公式，如 "(likes+coins)/NULLIF(views,0)"
    join_table: str     # 跨表维度用，如 "videos"
    join_column: str    # 跨表维度用，如 "category"

@dataclass
class SemanticParseInfo:
    metrics: list[SchemaElement]
    dimensions: list[SchemaElement]
    filters: list[dict]     # [{biz_name, operator, value}]
    date_info: dict         # {start, end}
    s2sql: str              # LLM/规则生成的语义SQL
    query_sql: str           # 翻译后的物理SQL
    query_mode: str          # "RULE" | "LLM"

@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    sql: str                # 执行的物理SQL（显示用）
    parse_info: SemanticParseInfo
```

### trie_index.py（人B，不依赖造数）

```python
# 简化版：不做 marisa-trie，直接用 dict + jieba
def build_index(elements: list[SchemaElement]) -> dict:
    """{token: [SchemaElement]} """
    index = {}
    for el in elements:
        for alias in el.alias.split(","):
            for token in jieba.lcut(alias.strip()):
                index.setdefault(token, []).append(el)
    return index

def match(query: str, index: dict) -> list[SchemaElement]:
    tokens = jieba.lcut(query)
    matched = []
    for t in tokens:
        if t in index:
            matched.extend(index[t])
    return list(set(matched))  # 按 element id 去重
```

### rule_parser.py（人A，依赖 models.py）

```python
# 5 种模式，按优先级匹配：
PATTERNS = [
    ("METRIC_GROUPBY",  r"各.+的?(.+)" ),          # "各分区播放量"
    ("METRIC_FILTER",   r"(.+)的(.+)排名" ),        # "知识区的播放量排名"
    ("METRIC_ORDERBY",  r"(.+)最[多高]的?(\d+)?个" ),# "点赞最多的5个视频"
    ("METRIC_TREND",    r"最近(\d+)天(.+)趋势" ),    # "最近7天播放量趋势"
    ("METRIC_CARD",     r"(.+)是多少" ),            # "播放量是多少"
]
# 匹配到就生成 S2SQL，没匹配到返回 None → 走 LLM
```

### llm_parser.py（人B）

```python
# 把 Trie 匹配结果 + 全部 schema + few-shot 注入 prompt
# prompt 强约束：
#   1. 只用 Schema 中列出的 bizName
#   2. 每个指标必须加聚合函数
#   3. GROUP BY 的维度必须在 SELECT 中
#   4. 日期过滤放 WHERE
#   5. 只输出 SQL，不要解释
```

### translator.py（人C，独立）

```python
def translate(s2sql: str, schema: dict) -> str:
    # 1. 替换 bizName → 物理名
    # 2. 处理派生指标表达式
    # 3. 添加 JOIN（跨表维度）
    # 4. 添加 LIMIT 1000
    # 使用 sqlglot 解析 AST 或简单正则替换
    # 确定性代码，不经过 LLM
```

### app.py（第2小时，人A集成）

```python
import streamlit as st

st.title("B站创作数据中心")

query = st.chat_input("输入你的问题...")
if query:
    # 1. Trie 匹配
    matched = trie.match(query, index)
    
    # 2. 解析
    parse_info = rule_parser.parse(query, matched) or llm_parser.parse(query, matched)
    
    # 3. 翻译
    physical_sql = translator.translate(parse_info.s2sql)
    
    # 4. 执行
    result = executor.execute(physical_sql)
    
    # 5. 展示
    st.write(f"```sql\n{physical_sql}\n```")  # 展示 SQL
    if len(result.rows[0]) == 2 and is_numeric(result.rows[0][1]):
        st.bar_chart(result.rows)              # 柱状图
    else:
        st.dataframe(result.rows)              # 表格
```

## V0.1 验收（5 条演示查询）

| # | 输入 | 期望 |
|---|------|------|
| 1 | 最近7天播放量趋势 | 折线图（日期×播放量） |
| 2 | 各分区播放量排名 | 柱状图（分区×播放量） |
| 3 | 点赞最多的5个视频 | 表格（视频名×点赞数） |
| 4 | 互动率是多少 | 大数字（单值） |
| 5 | 对比知识区和生活区的投币率 | 柱状图（两个分区的投币率） |

**一键启动**：
```bash
pip install streamlit jieba sqlglot openai python-dotenv pyyaml
python generate_data.py
streamlit run app.py
```

---

# V1.0 升级版

> 在 V0.1 基础上增量构建。所有 V0.1 模块复用，新增 FastAPI 后端 + React 前端。

## V1.0 新增内容

| 阶段 | 内容 | 工期 | 依赖 |
|------|------|------|------|
| Phase 1 | 数据底座：复用 V0.1 造数 | - | 已完成 |
| Phase 2 | 后端服务：FastAPI + SSE + 插件链 + Embedding | 3天 | V0.1 模块 |
| Phase 3 | 核心增强：Corrector Chain + 多轮对话 + 归因分析 | 3天 | Phase 2 |
| Phase 4 | 前端界面：React + ECharts | 5天 | Phase 2 |
| Phase 5 | 打磨：流式解读 + 下钻 + 图表切换 | 3天 | Phase 4 |

## V1.0 vs V0.1 差异

| 文件 | V0.1 | V1.0 |
|------|------|------|
| `app.py` | Streamlit 单文件 | 删除，替换为 FastAPI + React |
| `models.py` | 复用 | 不变 |
| `trie_index.py` | 复用 | 不变 |
| `rule_parser.py` | 复用 | 不变 |
| `llm_parser.py` | 复用 | 增强：self-consistency 可选 |
| `translator.py` | 复用 | 增强：多表 JOIN + 方言支持 |
| `executor.py` | 复用 | 增强：连接池 |
| **新增** `embedding_store.py` | ❌ | ✅ FAISS + bge-small-zh |
| **新增** `correctors.py` | ❌ | ✅ Schema/Grammar/Time Corrector |
| **新增** `context.py` | ❌ | ✅ 多轮对话持久化 |
| **新增** `processors/` | ❌ | ✅ 3 个归因 Processor |
| **新增** `backend/main.py` | ❌ | ✅ FastAPI + SSE |
| **新增** `frontend/` | ❌ | ✅ React + ECharts 全套 |

## Phase 2：后端服务

### 2.1 FastAPI + SSE

**文件**：`backend/main.py`

```python
# POST /api/chat/query  →  SSE 流式
#   event: parse_info  →  {metrics, dimensions, dateInfo}
#   event: result      →  {columns, rows, sql}
#   event: done        →  {queryId}
```

### 2.2 插件链注册

**文件**：`backend/config.yaml`

```yaml
pipeline:
  mappers: [KeywordMapper, EmbeddingMapper]     # V0.1 Trie + 新增 Embedding
  parsers: [RuleSqlParser, LLMSqlParser]        # 复用 V0.1
  correctors: [SchemaCorrector, GrammarCorrector, TimeCorrector]  # 新增
  processors: [DataInterpretProcessor]           # 新增
```

### 2.3 Embedding 双索引

**文件**：`backend/rag/embedding_store.py`

- 首次启动下载 bge-small-zh-v1.5（24MB）
- 对每个 schema element 生成向量：`"{biz_name} | {description} | {alias}"`
- 存入 FAISS IndexFlatIP
- 用户查询时 top-5 检索，作为 Trie 的补充

## Phase 3：核心增强

### 3.1 Corrector Chain

| Corrector | 做什么 | 文件 |
|-----------|--------|------|
| SchemaCorrector | 修正 LLM 编造的字段名 → 最近的合法 bizName | `correctors.py` |
| GrammarCorrector | SELECT 非聚合字段必须在 GROUP BY | `correctors.py` |
| TimeCorrector | 有 dateInfo 但 SQL 无 WHERE → 补充 | `correctors.py` |

### 3.2 多轮对话

**文件**：`backend/context.py`

```
Q1: "上周播放量趋势"        → 折线图，保存 SemanticParseInfo
Q2: "按分区分开"            → Llm改写为 "上周各分区播放量趋势" → 重新查询
Q3: "只看知识区"            → LLM改写 + filter → 重新查询
```

### 3.3 归因分析

**文件**：`backend/processors/`

| Processor | 做什么 |
|-----------|--------|
| DataInterpret | 问题 + top-20行 → LLM 生成 2-4 句中文解读 |
| MetricRatioCalc | 查询上一周期 → 计算环比/同比 |
| DimensionRecommend | 根据当前查询的维度，推荐未使用的关联维度 |

## Phase 4：React 前端

### 4.1 技术栈

Vite 5 + React 18 + TypeScript + Ant Design 5 + ECharts 5 + zustand

### 4.2 组件树

```
<ChatPage>
  <ChatHeader />                    # "B站创作数据中心"
  <MessageContainer>
    <UserBubble />                  # 用户消息
    <ParseTip />                    # 意图解析卡片（metrics/dims/date）
    <ChartPanel>                    # SSE 逐步渲染
      <LineChart />                 # METRIC_TREND
      <BarChart />                  # METRIC_BAR
      <PieChart />                  # METRIC_PIE
      <MetricCard />                # 大数字
      <DataTable />                 # 表格
    </ChartPanel>
    <InsightMarkdown />             # LLM 解读（流式输出）
    <DrillDownChips />              # 下钻维度
  </MessageContainer>
  <ChatInput />                     # 输入框
  <ConversationSidebar />           # 历史对话
</ChatPage>
```

### 4.3 图表自动分类

```typescript
// frontend/src/chart-utils.ts
function getChartType(cols, rows): ChartType {
  if (单行单数值) return 'METRIC_CARD'
  if (日期列+多行) return 'METRIC_TREND'
  if (分类列+单数值+≤10行) return 'METRIC_PIE'
  if (分类列+单数值+≤50行) return 'METRIC_BAR'
  return 'TABLE'
}
```

### 4.4 UI 规范

详见 [ui-design-system.md](ui-design-system.md)。

## Phase 5：打磨

- SSE 流式 LLM 解读（逐字输出）
- 图表/表格一键切换
- 折线⇔柱状 / 饼图⇔柱状切换
- 下钻维度点击 → re-query
- 日期选择器 → re-query

---

## 附录：环境变量

```bash
# .env（两版本共用）
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DB_PATH=./data/bilibili_demo.db
```

## 附录：端到端验证清单

### V0.1 极简版（5条）

1. "最近7天播放量趋势" → 折线图
2. "各分区播放量排名" → 柱状图
3. "点赞最多的5个视频" → 表格
4. "互动率是多少" → 大数字
5. "对比知识区和生活区的投币率" → 双柱

### V1.0 升级版（追加5条）

6. "弹幕最多的10个视频" → 表格 + LLM 解读
7. "最近30天新增粉丝的城市分布" → 饼图
8. "上周播放量趋势" → "按分区分开" → 多轮改写
9. 点击下钻维度 → 新查询
10. 图表/表格切换 → 视图切换
