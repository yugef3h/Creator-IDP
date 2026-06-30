# ChatBI 可执行规格书

> 业务：B站创作者视频数据分析 | 架构：NL → S2SQL → Physical SQL | 技术栈：React + FastAPI + SQLite + DeepSeek

---

## 版本总览

| | ChatBI |
|---|------|
| **UI** | React + Ant Design + ECharts |
| **后端** | FastAPI + SSE 流式 |
| **RAG** | Trie 匹配 + Knowledge Q&A |
| **解析** | 规则优先，禁用 LLM 兜底防幻觉 |
| **纠正** | Corrector Chain（Schema / Grammar / Time） |
| **多轮对话** | ✅ 上下文保持 |
| **归因分析** | ✅ LLM解读 + 环比 + 下钻推荐 |
| **图表** | ECharts 5 种图表 + 自动分类 + 切换 |

---

## 核心模块

| 文件 | 说明 |
|------|------|
| `generate_data.py` | 造数：SQLite + dataset.yaml + exemplars.json |
| `models.py` | 4 个 dataclass |
| `trie_index.py` | jieba 分词 + 倒排索引 |
| `rule_parser.py` | 意图分类 + 5 种查询模式 → S2SQL |
| `translator.py` | bizName → 物理列名/表达式 + JOIN + LIMIT（确定性） |
| `executor.py` | SQLite 执行 + 自动聚合兜底 |
| `backend/main.py` | FastAPI + SSE 流式 |
| `backend/knowledge.py` | Knowledge Q&A 记忆层 |
| `backend/correctors.py` | Schema / Grammar / Time Corrector |
| `backend/context.py` | 多轮对话持久化 |
| `backend/processors/` | LLM 解读 + 环比 + 下钻推荐 |

---

## 实现阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 数据底座：造数 + 语义模型 | ✅ |
| Phase 2 | 后端服务：FastAPI + SSE + 插件链 + Corrector | ✅ |
| Phase 3 | 增强：Knowledge Q&A + 多轮对话 + 归因分析 | ✅ |
| Phase 4 | 前端：React + ECharts + SSE 流式 | ✅ |
| Phase 5 | 联调打磨：流式解读 + 日期修改 + 下钻 + 图表切换 | ✅ |

---

## Phase 1：数据底座

**文件**：`generate_data.py`

**输出**：`bilibili_demo.db`（3 张表）+ `dataset.yaml` + `exemplars.json`

**数据表**：
- `videos`：50 条视频，8 个分区
- `video_stats`：≥2500 行，覆盖 90 天
- `fans`：2000 条粉丝画像

**语义模型**：9 个指标（含 2 个派生指标）+ 7 个维度 + 3 个术语

---

## Phase 2：FastAPI 后端

### API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/query` | POST | 核心查询（SSE 流式） |
| `/api/chat/history/{chatId}` | GET | 加载历史 |
| `/api/chat/history/{chatId}` | DELETE | 清除上下文 |
| `/api/health` | GET | 健康检查 |

SSE 事件：`knowledge?` → `parse_info` → `query_result` → `summary_chunk`* → `done`

### 插件链

```yaml
pipeline:
  mappers: [KeywordMapper]
  parsers: [RuleSqlParser]
  correctors: [SchemaCorrector, GrammarCorrector, TimeCorrector]
  processors: [DataInterpretProcessor]
```

### Corrector Chain

| Corrector | 职责 |
|-----------|------|
| SchemaCorrector | 字段名校验 + 编辑距离修正 + 表名保护 |
| GrammarCorrector | 聚合函数 + GROUP BY 一致性 |
| TimeCorrector | 日期 WHERE 缺失时补充 |

---

## Phase 3：增强

### Knowledge Q&A（记忆层）

文件：`backend/knowledge.py`

- 知识类模式：`是什么`、`怎么算`、`的定义`、`公式`
- 术语定义直返，不执行 SQL
- 指标定义含 formula + default_agg

### 多轮对话

文件：`backend/context.py`

- SQLite 持久化 SemanticParseInfo
- LLM 改写融合历史上下文

### 归因分析

| Processor | 文件 | 职责 |
|-----------|------|------|
| DataInterpret | `processors/data_interpret.py` | LLM 流式解读 |
| MetricRatioCalc | `processors/metric_ratio.py` | 环比/同比 |
| DimensionRecommend | `processors/dimension_recommend.py` | 下钻推荐 |

---

## Phase 4：React 前端

### 技术栈

Vite 5 + React 18 + TypeScript + Ant Design 5 + ECharts 5 + zustand

### 组件树

```
<ChatPage>
  <ChatHeader />                    # 标题
  <MessageContainer>
    <UserBubble />                  # 用户消息
    <ParseTip />                    # 意图解析卡片
    <ChartPanel>                    # ECharts 5 种图表 + 切换
    <InsightMarkdown />             # LLM 流式解读
    <RatioBadges />                 # 环比标签
    <DrillDownChips />              # 下钻按钮
  </MessageContainer>
  <ChatInput />                     # 输入框
</ChatPage>
```

### 关键交互

| 交互 | 行为 |
|------|------|
| 发送消息 | POST /api/chat/query → SSE 流式渲染 |
| 图表切换 | 纯前端，柱状/饼图/折线/表格 |
| 日期修改 | 点击 parse-tip 日期 → DatePicker → 就地更新 |
| 下钻 | 组装完整 NL → 重新查询 |
| 新对话 | 生成新 chatId，清空上下文 |

---

## 附录 A：环境变量

```bash
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DB_PATH=./data/bilibili_demo.db
```

## 附录 B：端到端验证

1. "最近7天播放量趋势" → 折线图 + 流式解读
2. "各分区播放量排名" → 柱状图
3. "点赞最多的5个视频" → 表格
4. "深圳的粉丝有多少" → 大数字
5. "最近30天新增粉丝的城市分布" → 柱状图
6. "三连是什么" → Knowledge Q&A 直返定义
7. "互动率怎么算" → Knowledge Q&A 直返定义
8. "刘德华的播放量" → 安全拒绝
9. 点击日期标签 → 修改范围 → 就地更新
10. 点击下钻维度 → 重新查询
