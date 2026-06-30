# Bug 修复记录

## #1 Bot 单行回复未水平居中

**日期**: 2026-06-30

**现象**: Chat 回答只有一行时，文本左贴边撑满整行，视觉空旷。

**根因**: `.bot-bubble` 无 `width: fit-content` + `max-width`，始终撑满右侧面板宽度。

**修复**: `frontend/src/styles/variables.css` — `.bot-bubble` 添加 `width: fit-content; max-width: 85%; margin-right: auto`。

**影响**: `variables.css`

---

## #2 饼图从未被渲染

**日期**: 2026-06-30

**现象**: 用户说"用饼图展示"或系统自动选饼图，实际渲染仍是柱状图。

**根因**: `ChartView` 中 `METRIC_PIE` 和 `METRIC_BAR` 共用一个 `type: 'bar'` 的 ECharts 配置。

**修复**: `frontend/src/App.tsx` — 拆分饼图/柱状图为独立分支。饼图用环形布局 + 图例 + 百分比标签 + 10 色调色板。

**影响**: `App.tsx`

---

## #3 下钻维度标签不匹配 Trie

**日期**: 2026-06-30

**现象**: 点击下钻"每天"/"按时长"后返回"抱歉，我无法理解这个问题"。

**根因**: jieba 分词 "每天"→`["每天"]` 不匹配 stat_date 别名；"按时长"→`["按时","长"]` 不匹配 duration 别名。Trie 只匹配到指标无维度 → `_has_unrecognized_content` 拒绝。

**修复（双重保障）**:
1. 前端: `每天`→`按日期`，`按时长`→`按视频时长`，让 jieba 能切出匹配词
2. 后端: 新增 `_is_dimension_hint()`，维度修饰词不视为未识别内容

**影响**: `App.tsx`, `rule_parser.py`

---

## #4 指标知识问答只返定义不返数据

**日期**: 2026-06-30

**现象**: 问"什么是弹幕"只返回文字定义，没有弹幕数据。

**根因**: `classify_query` 将知识关键词+匹配指标分类为 `knowledge`，直接 return 不继续 NL2SQL。

**修复**: knowledge 事件加 `willQuery` 标记。匹配到 METRIC → 继续 NL2SQL；仅 TERM → 直接结束。前端用 `knowledgeText` 独立存储定义文本。

**影响**: `main.py`, `store.ts`, `api.ts`, `App.tsx`

---

## #5 lookup_knowledge 匹配精度

**日期**: 2026-06-30

**现象**: "投币率怎么算"返回"投币"定义而非"投币率"。

**根因**: `lookup_knowledge` 取 `candidates[0]`，coins 排在 coin_rate 前。"投币率"和"投币"都被匹配到但取了先匹配的。

**修复**: 按别名在查询中的匹配长度降序排列，"投币率"(3字) > "投币"(2字)。

**影响**: `rule_parser.py`
