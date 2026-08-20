# Hermes 总控规则（Agent 启动必读）

> 所有在本项目内工作的 Agent，**每次启动必须先完整阅读以下文件**，再动手：
>
> 1. `.hermes/PROJECT_RULES.md` —— 项目 20 条铁律
> 2. `context/project_context.md` —— 项目为什么这样设计
> 3. `context/decision_log.md` —— 已定决策与禁议事项
> 4. `context/business_glossary.md` —— 业务术语表
> 5. 本文件 —— 总控规则

## 项目一句话定位

建立一套**可持续运行的企业绩效管理系统**：Excel/平台导入或 bot 报数 → 妙搭 SQL 交互维护 → 妙搭服务端 TypeScript 计算 → 应用内结果视图与结果书输出。

## 运行架构与校对红线

- **运行主存储**：妙搭托管 PostgreSQL。数据在系统内交互维护，TypeScript 计算引擎是唯一计算权威。
- **Base 的角色**：仅存导入基线、结果或备份；不在 Base 日常维护或核算。新建 Base 禁止关联表功能。
- **关联演进**：Base 同步遗留的关联 jsonb 采用新增文本列、回填、双读校验、切换、观察期的渐进迁移；禁止直接将 jsonb 原列强转 text，禁止逗号拼接多值关联。
- **校对权威源**：Excel、Base 原始基线、Python 计算蓝本与已验收结果基线。妙搭 SQL 是运行数据，禁止用系统自身写入/回读结果自证正确。
- **计算与校对**：规则优先代码固化；任何计算、迁移或结果修改均须与外部独立基线核对。

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
