# 全量修复发卡计划 · 修订附录 A01

> 本文件与 `2026-08-20_122422-performance-repair-cards.md` 一起构成完整、可执行的发卡计划。
> 本附录优先级高于主计划中所有关于 A0 后依赖、首批任务与批次编号的表述。

## 发现的前置风险

`performance-system/.hermes/AGENTS.md` 仍将项目描述为“Excel 标准输入 → AI Agent 处理 → 飞书多维表计算 → 自动化输出”。这与以下已定决策冲突：

- D-022：日常维护与计算的运行主存储为妙搭 SQL，校对只能以外部独立基线为准；
- D-023：Base 只存导入/结果/备份，不在 Base 维护数据；
- D-024：新建 Base 禁止关联表，关联改造遵循文本合同。

若未先对齐，该文件会被后续 worker 当作启动规则读取，可能把修复工作带回已经废弃的 Base 计算架构。

---

## 新增卡 A0b：对齐项目 Agent 上下文与已定架构决策

**Owner:** `system-architect`

**Objective:** 清除项目规则中会把后续 worker 带回“Base 是计算/维护层”的过时叙述，确保 D-022/D-023/D-024 成为唯一执行口径。

**Files:**
- Modify：`performance-system/.hermes/AGENTS.md`
- Review：`performance-system/context/project_context.md`
- Review：`performance-system/context/decision_log.md`

**Required changes:**
1. 将项目一句话定位和“核心优先级”中的旧链路更新为：妙搭 SQL 负责交互维护与计算；Base 只存导入/结果/备份；
2. 明确外部校对权威源是 Excel/Base 原始基线/Python 蓝本/已验收结果，SQL 不得自证；
3. 明确新建 Base 禁止关联表，关联记录改造遵循主计划 J 系列的文本合同；
4. 保留“Data First → Rule First → Automation Second → Interface Last”，但不得再写“飞书多维表计算”；
5. 仅改过时上下文描述，不改业务代码或已定决策记录。

**Acceptance Criteria:**
- `.hermes/AGENTS.md` 与 D-022/D-023/D-024 无冲突；
- 新 worker 启动时能读到 SQL 主存储、外部校对、关联文本化的正确约束；
- 独立 reviewer 对照 `decision_log.md` 完成逐条核验。

**Dependencies:** A0。

---

## 替换后的依赖图

```text
A0 → A0b → A1 → B-DEC(PO确认) ─┬→ B1 ─┐
                               └→ B2 ─┼→ Q0 → Q1(上线授权) → J0 → J1 → J2 → J3 → J4(迁移授权) → G1
A0b → C1(PO确认) → C2 → C3 ─────┤
A0b → D1(PO确认) → D2 → D3 ─────┘
```

> 主计划中 A1、C1、D1 的依赖由 `A0` 一律替换为 `A0b`。

## 替换后的推荐发卡批次

| 批次 | 可发卡 | 前提 | 说明 |
|---|---|---|---|
| 0 | A0 | 无 | 隔离旧 P3c 工作区，确保修复不会夹带未审查改动 |
| 1 | A0b | A0 | 消除过期 Agent 上下文与 D-022/D-023/D-024 的冲突 |
| 2 | A1、C1、D1、B-DEC | A0b | 测试/设计/业务合同可并行；B-DEC、C1、D1 均有 PO 决策门 |
| 3 | B1、B2、C2、D2 | PO 对 B-DEC/C1/D1 确认 | P0 主修复；B1/B2 可并行，C2/D2 按已确认合同实现 |
| 4 | C3、D3、Q0 | 批次 3 完成 | 写入/状态加固后，进行全链路独立验收 |
| 5 | Q1 | Q0 PASS + PO 上线授权 | 唯一允许创建 release 的修复批次 |
| 6 | J0→J4 | Q1 PASS + 各迁移授权 | jsonb 迁移最后执行，严格串行 |
| 7 | G1a→G1c | J4 观察期后 | 恢复试算/重算/导出 UI 功能 |
