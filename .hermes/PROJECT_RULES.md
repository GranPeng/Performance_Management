# Performance System AI Development Rules

- Version: 1.0
- Project: AI Assisted Performance Calculation System

## Purpose

建立一套基于 Excel 标准数据输入、AI Agent 自动处理、飞书多维表计算、自动化输出绩效结果的企业绩效核算系统。

---

## 1. Core System Philosophy

本项目不是开发一个简单的数据处理工具。

本项目目标：建立一个可持续运行的企业绩效管理系统。

核心原则：Data First / Rule First / Automation Second / Interface Last

优先级：

1. 数据模型正确
2. 业务规则正确
3. 数据流稳定
4. 自动化效率
5. 用户体验

禁止：为了快速实现功能，牺牲数据结构和业务一致性。

---

## 2. System Architecture Rules

系统固定架构：

```
Excel Input
↓
Data Validation
↓
Agent ETL Pipeline
↓
Canonical Data Model
↓
Feishu Base
↓
Calculation Engine
↓
Performance Result
```

所有开发必须遵守。

禁止：Agent 直接修改业务结果。

禁止：Excel 直接作为计算数据库。

---

## 3. Canonical Data Model Rule

Canonical Data Model 是系统唯一事实来源。

所有：Excel 字段、飞书字段、Agent 处理字段，必须映射到 Canonical Model。

任何新增字段必须说明：

1. 字段目的
2. 数据来源
3. 数据消费者
4. 生命周期

禁止：重复字段。

禁止：同一业务含义多个字段。

---

## 4. Data Governance Rules

所有数据必须具有：Identity / Source / Timestamp / Status

例如 Employee 必须包含：Employee_ID / Source / Create_Time / Status

禁止：使用姓名作为唯一识别。

---

## 5. ID Management Rules

所有核心实体必须拥有唯一 ID。

格式：

- Employee: EMP000001
- Organization: ORG000001
- Project: PROJ000001
- Metric: MET000001

禁止：使用自然语言名称作为关联键。例如禁止用「市场部」「张三」「618活动」作为数据库关联字段。

---

## 6. Business Rule Management

所有绩效计算规则必须存储在 `/docs/business_rules.md`。

任何计算逻辑修改必须经过：Business Analyst / Finance Controller / Product Owner 三方确认。

禁止：直接修改公式。

---

## 7. Calculation Rule

所有绩效计算必须：可解释 / 可追溯 / 可复核。

每个结果必须能够回答：为什么得到这个分数？

计算链：

```
Target → Actual → Achievement Rate → Weight → Score
```

---

## 8. Agent Responsibility Rules

每个 Agent 拥有明确职责。禁止跨职责修改。

### System Architect

负责：架构、数据模型、技术决策。
禁止：修改业务规则。

### Business Analyst

负责：KPI 定义、指标体系、计算逻辑。
禁止：修改系统架构。

### Finance Controller

负责：财务口径、成本收入规则、ROI 逻辑。
禁止：直接开发。

### Data Engineer

负责：Excel 处理、数据清洗、Mapping。
禁止：改变业务含义。

### Feishu Builder

负责：Base 设计、Relation、Formula、Automation。
禁止：绕过 Canonical Model。

### Automation Engineer

负责：ETL、API、Workflow。
禁止：直接修改业务结果。

### QA Reviewer

负责：测试、风险发现、验证。
禁止：自行修复问题。

---

## 9. Agent Communication Rules

Agent 之间必须通过标准 Handoff。

格式：

```
## Completed Task
任务名称:
## Decision
做出的决定:
## Change
修改内容:
## Impact
影响模块:
## Risk
潜在风险:
## Next Step
下一Agent:
```

禁止：口头传递。禁止：隐藏修改。

---

## 10. Kanban Rules

所有开发必须进入 Kanban。

任务状态：

```
BACKLOG → ANALYSIS → DESIGN → IMPLEMENTATION → REVIEW → TESTING → ACCEPTED → ARCHIVED
```

禁止：跳过 Review。禁止：未测试进入 Accepted。

---

## 11. Task Definition Rules

每个 Task 必须包含：

- Title
- Owner
- Objective
- Input
- Output
- Dependency
- Acceptance Criteria
- Risk

缺少 Acceptance Criteria 的任务禁止执行。

---

## 12. Documentation Rules

任何重大修改必须同步更新 `docs/`，包括：data_model.md / business_rules.md / system_design.md

代码不是唯一成果。文档必须先于复杂开发。

---

## 13. Excel Rules

Excel 仅作为 Input Layer。

必须：标准字段、固定格式、数据验证。

禁止：人工隐藏逻辑。禁止：复杂公式作为核心计算。

---

## 14. Feishu Rules

飞书作为 Calculation Layer + Visualization Layer。

负责：关联、计算、展示。

不负责：数据清洗。

---

## 15. Automation Rules

所有自动化必须具备：Input / Processing / Validation / Output / Log

任何失败必须生成 Error Log。

禁止：静默失败。

---

## 16. Testing Rules

测试必须覆盖：Normal Case / Boundary Case / Exception Case / Historical Case

必须包含：人工计算结果与系统计算结果进行对比。

---

## 17. Change Management

任何修改必须记录：Change ID / Date / Owner / Reason / Impact

重大修改必须更新 Memory。

---

## 18. Memory Management

Memory 分为：

- `architecture_memory.md` —— 系统设计决策
- `business_memory.md` —— 业务规则
- `data_memory.md` —— 数据处理规则
- `issues_memory.md` —— 问题和解决方案

禁止：删除历史决策。

---

## 19. Development Priority

- P0：数据模型、业务规则
- P1：飞书结构、数据处理
- P2：自动化
- P3：优化体验

---

## 20. Final Acceptance Standard

系统上线必须满足：

- [ ] 数据模型稳定
- [ ] KPI 规则确认
- [ ] 飞书计算正确
- [ ] Agent 流程稳定
- [ ] 异常可追踪
- [ ] 结果可人工复核
- [ ] 文档完整

---

## Final Principle

本系统的核心不是自动计算，而是建立一个可信赖、可解释、可持续迭代的绩效管理系统。

所有 Agent 必须优先保护：数据一致性 / 业务准确性 / 系统可维护性。
