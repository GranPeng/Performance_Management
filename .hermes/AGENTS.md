# Hermes 总控规则（Agent 启动必读）

> 所有在本项目内工作的 Agent，**每次启动必须先完整阅读以下文件**，再动手：
>
> 1. `.hermes/PROJECT_RULES.md` —— 项目 20 条铁律
> 2. `context/project_context.md` —— 项目为什么这样设计
> 3. `context/decision_log.md` —— 已定决策与禁议事项
> 4. `context/business_glossary.md` —— 业务术语表
> 5. 本文件 —— 总控规则

## 项目一句话定位

建立一套**可持续运行的企业绩效管理系统**：Excel 标准输入 → AI Agent 处理 → 飞书多维表计算 → 自动化输出绩效结果。

## 核心优先级（不可颠倒）

Data First → Rule First → Automation Second → Interface Last

1. 数据模型正确
2. 业务规则正确
3. 数据流稳定
4. 自动化效率
5. 用户体验

## 三条绝对禁令（违反即返工）

1. **禁止** Agent 直接修改业务结果
2. **禁止** Excel 直接作为计算数据库
3. **禁止** 用姓名/自然语言名称作为数据库关联键

## 多 Agent 协作纪律

- 每个 Agent 严格在自己的职责域内工作（见 PROJECT_RULES.md §8），**禁止跨职责修改**
- Agent 之间只通过标准 Handoff 格式交接（见 PROJECT_RULES.md §9），禁止口头传递、禁止隐藏修改
- 所有开发任务必须走 Kanban（见 PROJECT_RULES.md §10），禁止跳过 Review、禁止未测试进入 Accepted
- 缺少 Acceptance Criteria 的任务禁止执行

## 对决策的态度

- `decision_log.md` 中标记为【已定】的决策：**执行，不重新讨论**
- 标记为【禁议】的事项：**任何人不得重开讨论**，除非 Product Owner 本人书面推翻
- 你认为某个已定决策有误时：按 Handoff 格式提交「决策复议」给 Product Owner，由人裁决，Agent 不得自行推翻
