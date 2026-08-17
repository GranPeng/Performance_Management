# 系统设计（Phase 0 产物，P0-001）

## 1. 系统边界
| 进入系统 | 不进入系统 |
|---|---|
| （待定义） | （待定义） |

## 2. 数据流
```
Excel(原始) → Agent ETL → Canonical Schema → 飞书 Base(计算+展示)
```

## 3. 扩展点设计
- 更多部门：Organization 表驱动，不写死部门枚举
- 更多绩效模型：Metric + 规则配置化，模型差异不进 Schema
- 更多数据来源：Canonical Schema 作为唯一入口，新来源只新增 Adapter

## 4. ADR 索引
见 memory/architecture_memory.md
