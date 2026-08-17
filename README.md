# 绩效核算系统（performance-system）

## 定位
本目录是绩效核算系统的 **AI 开发组织层**。Hermes Kanban 不是简单任务看板，
而是驱动多 Agent 协作（Planner → Builder → Reviewer）的工作流引擎。

## 目录结构
```
.hermes/
  kanban/      # board.yaml / epics.yaml / tasks/ —— 任务驱动层
  profiles/    # 8 个 Agent Profile，各自独立上下文
  memory/      # 分层记忆：architecture / business / data / issues
data/          # input(原始) → staging(清洗) → output(标准)
docs/          # data_model / business_rules / system_design（Phase 0 产物）
scripts/       # ETL / 校验 / 飞书同步（Phase 3 产物）
```

## Agent 权限矩阵
| Profile | 读 | 写 |
|---|---|---|
| product_owner | 全部 | 需求与验收结论 |
| system_architect | 全部 | 架构文件（docs/、memory/architecture_memory.md） |
| business_analyst | 业务相关 | 规则文件（docs/business_rules.md、memory/business_memory.md） |
| finance_controller | 全部 | 财务口径审核意见 |
| data_engineer | 数据相关 | Schema、mapping（memory/data_memory.md） |
| feishu_builder | Schema | Base 设计 |
| automation_engineer | 代码/接口 | scripts/ |
| qa_reviewer | 全部 | 测试文件（memory/issues_memory.md） |

> 铁律：任何字段设计必须回答 —— 为什么需要？谁产生？谁消费？
> 架构层不写业务公式；业务公式只属于 business_analyst + finance_controller。

## 启动顺序
Phase 0 知识库 → Phase 1 冻结数据模型 → Phase 2 飞书 Base（先人工 100 条验证公式）
→ Phase 3 Agent ETL 自动化。**飞书模型未验证前不做自动化。**
