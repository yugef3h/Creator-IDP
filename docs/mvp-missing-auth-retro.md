# MVP 遗漏"权限/租户"能力复盘

> 日期：2026-07-03 | 触发：README.md + ori-mvp Skill 对照分析

---

## 一、发生了什么

ChatBI MVP 的 5 层核心能力（NL2SQL、多轮对话、RAG、可视化、归因分析）全部来自 `ori-mvp` Skill。但 **权限控制** 和 **租户隔离** 没有出现在 MVP 计划中，仅在 README.md 末尾 TODO 写了"多租户隔离"，design-review.md §7 明确标记为"不做"。

复盘发现：这不是漏做，而是 **ori-mvp Skill 本身的架构视角偏差**导致的系统性盲区。

---

## 二、直接原因

`design-review.md` §7 "不做的事情"：

| 不做 | 理由 | 后续版本 |
|------|------|---------|
| 用户登录/权限 | MVP 演示用 | V0.5 |

`design-review.md` §11 "安全性"：

> MVP 不做：用户认证、权限控制、速率限制。

这是一个**有意识的排除决策**，但这个决策本身是错的。理由见下文。

---

## 三、根因分析

### 根因 1：ori-mvp Skill 的"技术架构提取"视角

ori-mvp 定义的 5 层核心能力全部来自 SuperSonic 的 **NL2SQL 技术架构**：

| Layer | 能力 | 来源 |
|-------|------|------|
| Layer 1 | NL2SQL Pipeline (5-stage) | SuperSonic ChatWorkflowEngine |
| Layer 2 | 多轮对话上下文 | SuperSonic ChatContextService |
| Layer 3 | RAG 知识库 (Trie + Embedding) | SuperSonic KnowledgeBaseService |
| Layer 4 | ECharts 可视化 | SuperSonic 前端 |
| Layer 5 | 归因分析（解读 + 环比 + 下钻） | SuperSonic Processor Chain |

SuperSonic 作为一个完整的 **Java + Spring Boot** 企业产品，权限/租户是 **Spring Security 基础设施层** 的东西，不属于 "NL2SQL 核心引擎"。Skill 作者提取时，忠实地还原了"有趣的技术挑战"，跳过了"无聊但必须的基础设施"。

**对照：SuperSonic 有但没有被 Skill 提取的能力**：

| 基础设施 | SuperSonic 实现 | MVP 缺失 |
|----------|----------------|---------|
| 用户认证 | Spring Security + JWT | ❌ 无 |
| 租户隔离 | domain_id 字段 + 中间件 | ❌ TODO |
| API 鉴权 | @AuthenticationPrincipal | ❌ 无 |
| 请求日志（含用户维度） | AOP 切面 | ❌ 仅技术日志 |
| 角色/权限模型 | RBAC | ❌ 无 |

### 根因 2："演示用 MVP" 的自我欺骗

> "用户登录/权限 | MVP 演示用 | V0.5"

这个判断隐含了一个错误假设：**演示 = 不需要权限**。

实际上：
- 如果你想演示给**多个 UP 主**看，他们各自的数据必须隔离
- 如果你想演示给**投资人/客户**看，数据安全是基本信任
- 如果你想从 Demo 演进到**生产**，权限是第一个要补的课 —— 且它涉及全栈改造（API 层 + 数据层 + 前端）
- 一个没有租户隔离的 ChatBI，任何一个用户都能查询所有用户的数据 —— 这在数据产品中是**安全基线问题**，不是功能问题

### 根因 3：缺少"产品能力清单"，只有"技术能力清单"

`mvp-plan.md` 的 4 周计划全部是技术里程碑。真正缺的是一张**产品能力完整性检查表**：

| 维度 | 技术能力（有） | 产品能力（缺） |
|------|-------------|-------------|
| 查询 | NL2SQL 5-stage ✅ | 谁能查什么数据 ❌ |
| 数据 | SQLite 本地库 ✅ | 多用户数据怎么隔离 ❌ |
| 对话 | 多轮上下文 ✅ | 不同用户的对话怎么隔离 ❌ |
| 可视化 | ECharts 5 种 ✅ | 不同用户看到不同仪表盘 ❌ |
| 安全 | SQL 参数化防注入 ✅ | 用户认证 + API 鉴权 ❌ |

### 根因 4：MVP 优先级倒置

对比真正的优先级排序：

| 优先级 | 能力 | 本项目 | 理由 |
|--------|------|--------|------|
| P0（没有不能上线） | NL2SQL、数据查询、**租户隔离** | NL2SQL ✅ / 租户 ❌ | 安全基线 |
| P1（核心体验） | 可视化图表、多轮对话 | ✅ | 用户价值 |
| P2（锦上添花） | RAG 术语、归因分析、下钻 | ✅ | 体验增强 |

Layer 5（归因分析）在 MVP 范围内，租户隔离在 TODO —— **P0 和 P2 倒置**。

---

## 四、改进措施

### 措施 1：给 ori-mvp Skill 增加"产品完整性检查表"

在 Skill 的 `mvp-plan.md` 开头或独立文件中增加：

```markdown
## MVP 能力完整性检查表（编码前必查）

### 安全基线（缺一则不可部署）
- [ ] 用户认证（谁在提问？）
- [ ] 数据隔离/租户（用户只能看到自己的数据）
- [ ] API 鉴权（未登录不能调接口）
- [ ] 输入校验（防注入、防滥用、长度限制）

### 功能基线（缺一则不可用）
- [ ] NL2SQL 核心链路（规则 + LLM）
- [ ] 结果可视化（图表 + 表格）
- [ ] 错误降级提示（不白屏、不 500）

### 运维基线（缺一则不可维护）
- [ ] 请求日志（含用户标识）
- [ ] 健康检查端点
- [ ] 配置管理（环境变量 / 配置文件分离）
```

### 措施 2：强制区分"技术演示"和"产品 MVP"

在 Skill 中增加决策节点：

```
你做的 MVP 属于哪种？
  A. 技术 Demo
     - 内部评审用
     - 单用户场景
     - 不存档真实数据
     → 可以跳过权限，但必须在 README 中显式声明"单用户/Demo 专用"
  B. 产品 MVP
     - 给用户试用
     - 有多用户场景
     - 存真实数据
     → 权限和租户是 P0，不可跳过
```

### 措施 3：用"部署阻碍分析"替代"不做列表"

不再使用 `design-review.md` §7 那种被动排除式列表。改为每个 Phase 结束后追问：

> **如果现在就要把这个系统部署给 3 个真实用户试用，还缺什么？**

这个问题的答案会立刻暴露：缺登录、缺数据隔离、缺 API 鉴权、缺用户维度的日志。

### 措施 4：Skill 中补全基础设施对照表

在 ori-mvp Skill 的 `mvp-plan.md` "SuperSonic → MVP 技术对照"表中，增加基础设施行：

```markdown
| 用户认证 | Spring Security + JWT | FastAPI Depends + 简单 token |
| 租户隔离 | domain_id + 中间件 | SQLite 分离或 WHERE tenant_id |
| API 鉴权 | @AuthenticationPrincipal | Depends(get_current_user) |
| 请求日志 | AOP 切面 | logging.info(user_id, query) |
| 角色权限 | RBAC (5 角色) | MVP 先做 owner/viewer 两种 |
```

---

## 五、核心教训

> **"技术架构提取" ≠ "产品能力建模"**

ori-mvp Skill 忠实地还原了 SuperSonic 的 NL2SQL 技术架构，但漏掉了 SuperSonic 依赖的 Spring Security 基础设施层 —— 不是因为不重要，而是因为"不有趣"。

做一个能用的数据产品，**安全基线（权限/租户/鉴权）的优先级高于体验增强（归因/下钻/流式）**。下次规划 MVP 时，先用"产品完整性检查表"过一遍，再排技术 Roadmap。
