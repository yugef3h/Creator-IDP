# NL → SQL 完整流程

ChatBI 自然语言转 SQL 的完整链路，从用户输入到 SQLite 执行，共 5 个阶段。

```
用户输入 → Trie匹配 → 规则解析 → Translator翻译 → SQLite执行
                         ↓ 失败
                      LLM兜底
```

入口：`app.py:107` `process_query()`

---

## 阶段 1：Trie 索引匹配 — 识别指标/维度

**文件：** `trie_index.py`

将用户输入中的中文别名匹配到 Schema 元素（指标/维度）。

```
用户输入 "最近7天播放量趋势"
    ↓ jieba 分词
["最近", "7", "天", "播放量", "趋势"]
    ↓ 倒排索引查找
匹配到: [{biz_name: "views", alias: "播放量,播放数", element_type: "METRIC"}]
```

- `build_index()` (`trie_index.py:13`) — 对所有 Schema 元素的 `biz_name` 和 `alias` 做 jieba 分词，构建 `{token → [元素列表]}` 倒排索引。过滤单字和高频通用词（"分布"、"排名"等）
- `match()` (`trie_index.py:32`) — 用户 query 分词后，逐个 token 查索引，支持精确匹配 + 前缀/后缀模糊匹配。指标始终匹配，维度仅补充匹配

---

## 阶段 2：规则解析 — 生成 S2SQL（业务名 SQL）

**文件：** `rule_parser.py`

核心模块，覆盖 80% 的查询。入口 `parse()` (`rule_parser.py:131`)。

### 5 种查询模式

| 模式 | 触发条件 | 示例 |
|---|---|---|
| `METRIC_TREND` | 有日期 + 无维度 | "最近7天播放量趋势" |
| `METRIC_GROUPBY` | 有维度 + 有指标 | "各分区播放量" |
| `METRIC_ORDERBY` | 有维度 + TopN 关键词 | "点赞最多的5个视频" |
| `METRIC_FILTER` | 有维度 + 过滤条件 | "深圳的粉丝有多少" |
| `METRIC_CARD` | 单指标 + 无维度无日期 | "总播放量是多少" |

### 处理步骤

1. **意图分类** (`rule_parser.py:34`) — 关键词匹配判断意图（分布/排名/趋势/单值/明细）
2. **日期提取** (`rule_parser.py:171-183`) — 正则匹配"最近N天"、"上个月"、"本周"等，转为具体日期范围
3. **维度过滤** (`rule_parser.py:186-227`) — 识别城市名、分区名等值过滤条件
4. **TopN 提取** (`rule_parser.py:230-233`) — "最多的5个" → `LIMIT 5`
5. **幻觉检测** (`rule_parser.py:106-128`) — 检查是否有未识别实义词，有则拒绝，交给 LLM
6. **S2SQL 拼接** (`rule_parser.py:252-364`) — 根据模式拼接 SELECT/FROM/WHERE/GROUP BY/ORDER BY/LIMIT

### S2SQL 示例

生成的 S2SQL 使用 **bizName**（业务名），不是物理列名：

```sql
-- 用户问"最近7天播放量趋势"
SELECT stat_date, SUM(views)
FROM video_stats
WHERE stat_date BETWEEN '2026-06-23' AND '2026-06-30'
GROUP BY stat_date
ORDER BY stat_date

-- 用户问"各分区播放量排名"
SELECT video_category, SUM(views)
FROM video_stats
JOIN videos ON video_stats.video_id = videos.video_id
GROUP BY video_category
ORDER BY SUM(views) DESC

-- 用户问"深圳的粉丝有多少"
SELECT SUM(followers_count)
FROM fans
WHERE city = '深圳'
```

---

## 阶段 3：LLM 兜底（规则失败时）

**文件：** `llm_parser.py`

规则解析返回 `None` 时触发。将 Schema 定义 + few-shot 示例注入 prompt，让 DeepSeek 生成 S2SQL。

```python
# llm_parser.py:76 — prompt 模板
prompt = f"""#Role: You are a data analyst experienced in SQL languages.
#Task: Convert natural language to SQL query using ONLY the schema elements provided.

#Rules:
1. Use ONLY metrics and dimensions listed in the Schema section below
2. Reference columns by their exact bizName shown in Schema (e.g. "views", "category")
3. ALWAYS apply an aggregate function to metric columns unless user asks for raw detail
4. Put date filters in WHERE clause using stat_date
5. DO NOT invent table names or column names
6. If the question cannot be answered, output CANNOT_PARSE
7. Output ONLY the SQL, no explanation
...
```

- `_format_schema_string()` (`llm_parser.py:24`) — 将 dataset.yaml 格式化为紧凑的 schema 字符串注入 prompt
- `_select_exemplars()` (`llm_parser.py:51`) — 从 exemplars.json 选 few-shot 示例
- LLM 只接触 bizName，永远不知道物理表名/列名

> **注意：** 当前 V0.1 的 `app.py:115` 实际关掉了 LLM 兜底，纯规则解析。规则失败直接返回"无法理解"。

---

## 阶段 4：Translator 翻译 — S2SQL → 物理 SQL（防幻觉核心）

**文件：** `translator.py`

**确定性代码**，不经 LLM，是防幻觉的关键设计。入口 `translate()` (`translator.py:29`)。

### 翻译对照

```
S2SQL（bizName）                         物理 SQL
─────────────────────────────────    ─────────────────────────────────
SUM(views)                           SUM(views)              — 普通指标，同名
SUM(interaction_rate)                SUM((likes+comments+    — 派生指标，展开表达式
                                      shares)*1.0/views)
category                             video_category          — 维度替换物理列名
                                     JOIN videos ON ...      — 自动添加跨表 JOIN
stat_date (FROM fans)                follow_time             — fans 表日期字段修正
```

### 7 个处理步骤

1. **替换 `AGG(bizName)`** (`translator.py:56-74`) — 派生指标展开 expression，普通指标换物理名
2. **替换裸 bizName** (`translator.py:77-92`) — 未被聚合包裹的指标加默认聚合
3. **替换维度 bizName** (`translator.py:95-98`) — 维度业务名 → 物理列名
4. **修复 fans 表日期** (`translator.py:101-103`) — fans 表的日期字段是 `follow_time`，不是 `stat_date`
5. **收集 JOIN** (`translator.py:106-110`) — 跨表维度自动加 JOIN（查 `join_table` / `join_key`）
6. **处理 FROM + JOIN** (`translator.py:114-126`) — 拼接完整 FROM 子句（video_stats ↔ videos ↔ fans）
7. **添加 LIMIT** (`translator.py:128-130`) — 兜底 `LIMIT 1000`

---

## 阶段 5：执行器

**文件：** `executor.py`

`execute()` (`executor.py:67`) — SQLite 执行物理 SQL，返回 `QueryResult`。

额外能力：
- **列类型推断** (`executor.py:10`) — 根据列名和值自动推断 DATE / NUMERIC / CATEGORY
- **自动聚合兜底** (`executor.py:23-64`) — 检测到粒度过细（同一维度值重复出现），自动按维度 GROUP BY + SUM 聚合

---

## 数据模型串联

**文件：** `models.py`

```
SchemaElement (指标/维度元数据)
    → Trie 匹配时识别（trie_index.py）
    → rule_parser 中判断主表、JOIN、日期字段
    → 封装到 SemanticParseInfo 中

SemanticParseInfo (解析结果，所有层的桥梁)
    → rule_parser 产出 .s2sql（业务名 SQL）
    → translator 消费 .s2sql，产出 .query_sql（物理 SQL）
    → executor 执行 .query_sql

QueryResult (执行结果)
    → ColumnInfo[] + rows → 前端图表渲染
```

---

## 完整调用链路（app.py）

```python
# app.py:107 process_query()
def process_query(query):
    # 1. Trie 匹配
    matched = match(query, INDEX)                    # trie_index.py

    # 2. 规则解析 → S2SQL
    parse_info = rule_parse(query, matched, TRIE_KEYS)  # rule_parser.py

    # 3. 翻译 → 物理 SQL
    physical_sql = translate(parse_info.s2sql)       # translator.py

    # 4. 执行
    result = execute(physical_sql)                    # executor.py
```

---

## 关键设计决策

1. **语义层隔离** — LLM 只接触 bizName，永远不知道物理表名/列名 → 无法产生幻觉 SQL
2. **双策略** — 规则优先（80%，快且确定）→ LLM 兜底（处理灵活表达）
3. **Translator 纯代码** — JOIN、派生指标展开、日期字段修正全部硬编码，零幻觉风险
4. **Trie 索引** — jieba 分词 + 倒排索引，O(1) 匹配中文别名到 Schema 元素
5. **自动聚合兜底** — executor 检测粒度过细自动聚合，防止返回海量明细行
