# Canonical 数据模型（字段级定义与 ID 体系）

> 状态：**FROZEN**（2026-08-14 Product Owner 确认冻结；此后任何变更必须走规则 §17 变更流程，记录 Change ID / Date / Owner / Reason / Impact）
> 版本：v1.0（T4 产出，对应 ADR-003）
> 权威基准：V04 绩效框架（T1）、V60 预算模型（T2）、Base 审计报告（T3）、决策日志 D-001~D-008
> 最近变更：CHG-T8B-001（§4.6）、CHG-T8C-001（§1.1 Note）、CHG-T11A-001（§5.4 豁免与提成字段，2026-08-17）、CHG-T15B-001（§5.5/§5.6 提成基数与豁免范围配置化，2026-08-17）、CHG-D010-R2-001（§5.4 Exemption_Scope_ID / §5.5 Base_Rate / §5.6 Exemption_Scope，2026-08-17）、CHG-T18-001（§4.1 Employee 绩效工资/负责渠道 + §5.4 Perf_Salary_Snapshot，2026-08-18）、CHG-T18-002（§4.7 Project_Group 新实体 + §4.6 Group_ID + §5.3 小组维度/素材类型/归因预留，2026-08-18）、CHG-D010-R3-001（§5.4 营收 Actual 溯源/§5.6 营收阈值，2026-08-18）

---

## 1. 模型总则

1. 本模型是系统**唯一事实来源**（规则 §3）。Excel 字段、飞书字段、Agent 处理字段必须映射到本模型；任何新增字段必须回答三问：为什么需要 / 谁产生 / 谁消费。
2. 本模型只定义**字段与结构**。业务公式、评分逻辑、提成计算逻辑的编写属 Business Analyst 职责（规则 §8），本文件不包含任何业务公式；V04 评分标准一律以**原文文本 + 结构化容器**承载。
3. 每张表必须具备规则 §4 四要素：**Identity / Source / Timestamp / Status**。
4. 所有表间关联一律使用 ID，**禁止**姓名、部门名、岗位名、项目名、渠道名等自然语言作为关联键（规则 §5、禁议事项 2）。名称类字段仅供人读展示。
5. 期间（Period）统一为自然月，格式 `YYYY-MM`（TEXT）。V04 全部岗位评价周期为「上月整月」，V60 为自然月，模型期粒度定为月；如需更细粒度，经变更流程扩展。
6. 所有数值字段不限制业务取值范围（阈值属业务规则）；模型层只约束类型与可空语义。
7. 「不封顶」「不保底」等开放语义用显式布尔标记表达，**禁止**用 200、9999 等魔法数值冒充开放上限。

### 1.1 通用治理字段（每张表必备，逐表不再重复解释三问）

| 字段 | 类型 | 目的（为什么需要） | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|
| <实体>_ID | TEXT | 稳定唯一标识，一切关联的唯一依据 | 导入/录入流程按 §2 号段规则分配 | 全系统 | 创建时分配，终身不变，不回收不复用 |
| Source | TEXT | 数据来源追溯（满足治理四要素之 Source） | 产生该记录的流程 | 审计、QA、复核 | 创建时写入，不随业务更新改变 |
| Create_Time | DATETIME | 满足 Timestamp；支撑变更审计 | 写入流程 | 审计、排查 | 创建时写入，不变 |
| Update_Time | DATETIME | 记录最近变更，支撑冲突排查 | 写入流程 | 审计、排查 | 每次更新刷新 |
| Status | TEXT | 生命周期状态（Active / Inactive / Archived） | 维护流程 | 所有查询（默认只取 Active） | 状态迁移有记录；Archived 只读不删 |
| Note | TEXT | 可选备注：承载归并说明、作废原因、特殊标注等无法结构化的治理信息（CHG-T8C-001） | 维护流程 | 审计、QA、维护人员 | 随维护事件追加，不覆盖历史注记 |

## 2. ID 分配规则（规则 §5 落地）

### 2.1 格式与前缀

统一格式：`前缀 + 6 位十进制顺序号`，无前导分隔符，大小写敏感、全大写。

| 实体 | 字段 | 前缀 | 示例 |
|---|---|---|---|
| Employee | Employee_ID | EMP | EMP000001 |
| Organization | Org_ID | ORG | ORG000001 |
| Position | Position_ID | POS | POS000001 |
| Project | Project_ID | PROJ | PROJ000001 |
| Channel | Channel_ID | CH | CH000001 |
| Project_Member | Project_Member_ID | PM | PM000001 |
| Project_Group | Group_ID | GRP | GRP000001 |
| Metric | Metric_ID | MET | MET000001 |
| Target | Target_ID | TGT | TGT000001 |
| Actual | Actual_ID | ACT | ACT000001 |
| Performance_Result | Result_ID | RST | RST000001 |
| Commission_Tier | Commission_Tier_ID | CT | CT000001 |
| Exemption_Scope | Exemption_Scope_ID | EXS | EXS000001 |
| Import_Batch | Batch_ID | IB | IB000001 |
| Validation_Rule | Rule_ID | VR | VR000001 |
| Error_Log | Error_ID | ERR | ERR000001 |

### 2.2 号段管理方式

1. 各实体号段**相互独立**，从 000001 起严格递增。
2. 号段由写入侧流程（ETL / 录入脚本）在写入前取该实体当前最大号 +1 分配；同一批次内连续分配。禁止人工指定跳号，禁止复用已归档记录的 ID。
3. ID 一旦分配**终身不变**：HR 最终版人员数据切换（D-008）、组织调整、岗位更名均不触发换号，只更新业务字段与生效区间。
4. 关联完整性由 Validation_Rule（§5.13）中的「ID 存在性校验」保障，写入 Target/Actual/Result 等事实表前必须校验所引用的主数据 ID 存在且 Status=Active。

## 3. 实体总览与关系

| # | 实体 | 粒度（一行=） | 类别 |
|---|---|---|---|
| 1 | Employee | 一名人员 | 主数据 |
| 2 | Organization | 一个部门节点（树） | 主数据 |
| 3 | Position | 一个岗位定义 | 主数据 |
| 4 | Project | 一个业务核算项目 | 主数据 |
| 5 | Channel | 一个渠道 | 主数据 |
| 6 | Project_Member | 某人某项目某渠道的一段生效分摊 | 主数据（关系型） |
| 7 | Project_Group | 一个制作部小组（一名编导带领、覆盖一个或多个项目） | 主数据 |
| 8 | Metric | 一个岗位的一项 KPI 定义（按规则版本） | 规则定义 |
| 9 | Target | 一个期间×一个指标或预算项目×一组维度的一个目标值 | 事实（长表） |
| 10 | Actual | 一个期间×一个指标×一组维度的一个实际值 | 事实（长表） |
| 11 | Performance_Result | 一个期间×一名人员×一个指标的一条结果 | 结果（长表） |
| 12 | Commission_Tier | 一个岗位某提成来源的一档梯度 | 规则定义 |
| 13 | Exemption_Scope | 一个豁免适用范围（岗位/岗位族 × 渠道 × 豁免期阈值） | 规则定义 |
| 14 | Import_Batch | 一次导入/计算批次 | 支撑 |
| 15 | Validation_Rule | 一条校验规则定义 | 支撑 |
| 16 | Error_Log | 一条错误记录 | 支撑 |

关系（全部 ID 关联）：

```
Organization ─┬─< Employee >─ Position ─< Metric
              │                  │            │
              │                  │            ├─< Target ─┐
Project ──< Project_Member >── Employee       ├─< Actual ─┼─< Performance_Result
Channel ──┴─< Project_Member                  │           │
              Channel ──< Target/Actual       Commission_Tier >─ Position / Metric
Import_Batch ──< Target / Actual / Employee / Error_Log
Project ──< Performance_Result（§5.4 Project_ID，CHG-T11A-001）
Exemption_Scope >─ Position / Channel（§5.6，CHG-D010-R2-001）
Performance_Result ──< Exemption_Scope（§5.4 Exemption_Scope_ID，CHG-D010-R2-001）
Channel ──< Employee（§4.1 Responsible_Channel_IDs，CHG-T18-001）
Employee ──< Project_Group（§4.7 Leader_Employee_ID，CHG-T18-002）
Project_Group ──< Project_Member（§4.6 Group_ID，CHG-T18-002）
Project_Group ──< Actual（§5.3 Group_ID，CHG-T18-002）
```

## 4. 主数据实体

### 4.1 Employee（人员主数据）

职责：全系统唯一人员身份来源。花名册（82 条）为开发期模拟数据来源（D-008），HR 最终版到达后同表切换，不换 ID。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Employee_ID | TEXT | 是 | 主键 | 导入流程 | 全系统 | 见 §1.1 |
| Name | TEXT | 是 | 人读展示；**禁止作关联键** | 花名册/HR | 看板、复核界面 | 随人员主数据维护 |
| Org_ID | TEXT→Organization | 是 | 归属部门，供组织指标归属与看板筛选 | 花名册/HR 维护 | Target/Actual 归属、Performance_Result | 组织调整时更新，历史结果不改写 |
| Position_ID | TEXT→Position | 是 | 决定适用哪套 Metric/Commission_Tier | 花名册/HR 维护 | Metric 匹配、结果计算 | 调岗时更新，历史结果不改写 |
| Direct_Manager_ID | TEXT→Employee | 否 | 负责人打分路由（V04 多指标来源为部门负责人/直属主管） | 花名册/HR | 打分流程、复核看板 | 汇报线变化时更新 |
| Employment_Status | TEXT | 是 | 区分在职/离职/停用；审计发现花名册无法区分生命周期 | 花名册/HR | 核算范围圈定、Project_Member 生效判断 | 入转调离全流程 |
| Hire_Date | DATE | 是 | 在职周期、新项目/新人员豁免判断的输入 | 花名册/HR | 结果计算、复核 | 入职写入，不常变 |
| Leave_Date | DATE | 否 | 离职结算边界 | 花名册/HR | 核算范围圈定 | 离职时写入 |
| Perf_Participate_Status | TEXT | 是 | 「是否参与绩效考核」需人工确认态（待确认/确认参与/确认不参与），替代现状纯查找字段 | 人力/部门负责人确认 | 核算范围圈定 | 每期核算前可复核更新 |
| Perf_Salary | NUMBER | 条件必填 | D-013 直播中控收入「绩效工资×档位百分比」的月固定基数；属人员主数据（每人一个固定基数），非结果表派生。条件必填=岗位为直播中控/运营助理（POS000041）时；其余岗位留空（未来其他岗位引入绩效工资部分可复用，不新增同义字段） | 花名册/HR 维护 | 计算引擎（直播中控绩效工资部分取数）、复核看板 | 随花名册维护；月中变更走变更记录（Update_Time + Note 留痕），历史结果不改写；计算时快照入 Performance_Result.Perf_Salary_Snapshot（§5.4）防历史重算失真 |
| Responsible_Channel_IDs | TEXT→Channel（多值） | 否 | D-013 中控负责渠道与 D-014 运营/高级主管负责渠道的「员工-渠道」负责关系：D-013 提成部分（渠道GSV×0.001÷中控人数）的渠道归属与中控人数统计、D-014 全额计提（各自负责渠道全额，不分摊）的共同取数依据；多值承载「一高级主管多渠道」 | 花名册/HR 维护（D-013/D-014 均明确负责渠道关系在花名册维护） | 计算引擎（渠道 GSV 计提、中控人数统计）、复核看板 | 随花名册维护；月中变更走变更记录，历史结果不改写（同 Org_ID/Position_ID 语义）；未来若需按生效区间归属，经 §17 升级为独立关系表 |
| Data_Origin | TEXT | 是 | D-008 切换标记：ROSTER_MOCK（花名册模拟）/ HR_OFFICIAL（HR 最终版）/ MANUAL | 导入流程 | 审计、QA、切换验证 | HR 切换时整体迁移为 HR_OFFICIAL |
| Import_Batch_ID | TEXT→Import_Batch | 是 | 追溯来源批次 | 导入流程 | 审计、错误回溯 | 创建写入 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

D-008 切换预留：HR 最终版到达后，按「姓名+部门+入职日期」或 HR 提供的人事编号做一次性匹配映射，**在原 Employee_ID 上更新字段**，Data_Origin 置为 HR_OFFICIAL；匹配不上的新增记录按 §2 号段新增。切换映射表由 Data Engineer 在迁移任务中产出，不属于本模型实体。

> **变更记录 CHG-T18-001**（2026-08-18，Owner: Product Owner（D-013/D-014 拍板人），任务 t_112edaf5 / T18）：Employee 新增 `Perf_Salary`（绩效工资）与 `Responsible_Channel_IDs`（负责渠道，多值 link→Channel）；Performance_Result 新增 `Perf_Salary_Snapshot`（§5.4）。
> 1. 原因：D-013 直播中控收入（绩效工资×档位百分比 ＋ 渠道GSV×0.001÷中控人数）与 D-014 渠道 GSV 全额计提的字段依赖（T17 标注登记，本条为其落地）。
> 2. 承载方案决策：负责渠道关系落 **Employee 多值关联**，不复用 Project_Member、不新建「员工-渠道」关系表——① D-013/D-014 均明确「负责渠道关系在花名册维护」，Employee 是花名册承载表；② Project_Member.Project_ID 必填，渠道负责关系不必然绑定项目，复用会伪造项目归属并混淆「项目分摊」与「渠道负责」两种语义；③ 多值 link 天然承载「一高级主管多渠道」，独立关系表在当前（无生效区间需求、历史结果不改写）属过度设计，未来需要时经 §17 升级，结构不返工。
> 3. 影响面：Performance_Result 提成计算（直播中控收入、GSV 全额计提、中控人数统计）读取上述字段；`Perf_Salary_Snapshot` 随 Commission_Amount 同粒度快照（期间×人员，同 Weight 快照语义），防薪资调整后历史重算失真。纯新增字段，既有字段与数据不受影响；Base 侧需补建两字段（feishu-builder 后续任务）。

### 4.2 Organization（部门树）

职责：部门层级主数据，支撑扩展更多部门（含未来新部门），不与岗位混写。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Org_ID | TEXT | 是 | 主键 | 组织主数据维护流程 | 全系统 | 见 §1.1 |
| Org_Name | TEXT | 是 | 人读展示 | 组织维护 | 看板、筛选 | 更名时更新 |
| Parent_Org_ID | TEXT→Organization | 否 | 树形层级（一级/二级部门） | 组织维护 | 组织汇总、归属上卷 | 组织调整时更新 |
| Org_Level | INTEGER | 是 | 层级深度，便于汇总与校验 | 组织维护 | 看板、校验 | 随层级调整 |
| Effective_Start / Effective_End | DATE | 是/否 | 组织沿革（审计：现状无法判断记录是否当前有效版本） | 组织维护 | 期间归属判断 | 生效区间维护，End 空=当前有效 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

### 4.3 Position（岗位主数据）

职责：岗位定义主数据。V04 覆盖 9 个岗位为初始注册集；名称差异（如 V04「编导」vs Base「内容主管/编导」）用别名字段归一，不复制 KPI。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Position_ID | TEXT | 是 | 主键 | 组织/人力主数据维护 | Metric、Employee、Commission_Tier | 见 §1.1 |
| Position_Name | TEXT | 是 | 标准岗位名（以 V04 为准） | 岗位维护 | 展示、匹配 | 更名时更新 |
| Position_Alias | TEXT | 否 | 别名集合（解决名称口径差异，如「内容主管/编导」）；多值用顿号分隔 | 岗位维护 | 映射、迁移对照 | 发现新别名时追加 |
| Org_ID | TEXT→Organization | 是 | 岗位所属部门（岗位与部门不混写，审计 4.18） | 岗位维护 | 归属筛选 | 组织调整时更新 |
| Job_Family | TEXT | 否 | 序列（对应职级对照表的序列维度） | 岗位维护 | 薪酬带宽参考 | 随职级体系维护 |
| Grade | TEXT | 否 | 职级 | 岗位维护 | 薪酬参考 | 随职级体系维护 |
| Version | TEXT | 是 | 岗位定义版本（当前 V04） | 岗位维护 | 规则匹配 | 新版本生效时新增/更新 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

### 4.4 Project（项目主数据）

职责：业务核算单元（高个子、少年状元、骨能、美赞臣跃高等）。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Project_ID | TEXT | 是 | 主键 | 业务主数据维护 | Target/Actual/Result、Project_Member | 见 §1.1 |
| Project_Name | TEXT | 是 | 人读展示 | 业务维护 | 看板 | 更名时更新 |
| Brand | TEXT | 否 | 品牌维度（审计 4.1 项目渠道检索含品牌） | 业务维护 | 看板筛选 | 随业务维护 |
| Start_Date / End_Date | DATE | 否 | 项目生命周期；新项目机制（免责期）判断的时间输入 | 业务维护 | 规则匹配（容器） | 随项目状态维护 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

### 4.5 Channel（渠道主数据）

职责：渠道维度主数据。初始注册集 = V60 权威 9 渠道：抖音、视频号、天猫淘宝、拼多多、京东POP、京东自营、达播、私域、外部分销。Base 现状的快手、京东私域、内容/达人子渠道不得直接入库，须先映射或经确认后注册。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Channel_ID | TEXT | 是 | 主键 | 业务主数据维护 | Target/Actual/Result、Project_Member | 见 §1.1 |
| Channel_Name | TEXT | 是 | 标准渠道名（以 V60 为准） | 业务维护 | 展示 | 更名时更新 |
| Channel_Alias | TEXT | 否 | 写法别名归一（如「天猫/淘宝」↔「天猫淘宝」），多值顿号分隔 | 业务维护 | 导入映射 | 发现新写法时追加 |
| Is_V60_Authoritative | BOOL | 是 | 标记是否 V60 权威渠道，防止未确认口径渠道混入 Target | 业务维护 | 导入校验 | 注册时写入 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

### 4.6 Project_Member（项目成员分摊）

职责：人员—项目—渠道的生效分摊关系，替代「在职人员对照项目」；支撑一人多项目/多渠道与 D-007.2 项目组人数统计的数据基础。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Project_Member_ID | TEXT | 是 | 主键（审计：现状无 ID，一人多项目无法区分） | 维护流程 | 分摊、人数统计 | 见 §1.1 |
| Employee_ID | TEXT→Employee | 是 | 人员关联 | 维护流程 | 全部下游 | 生效期内稳定 |
| Project_ID | TEXT→Project | 是 | 项目关联 | 维护流程 | 全部下游 | 生效期内稳定 |
| Channel_ID | TEXT→Channel | 否 | 渠道粒度归属；空=整项目（对应 V04「渠道=整项目」场景） | 维护流程 | 指标归属 | 生效期内稳定 |
| Effective_Start / Effective_End | DATE | 占位可空/正式必填 | 生效区间（审计：现状无生效日期）；历史占位同步允许 Start 空（D-011/CHG-T8B-001，Status=待在线维护），正式维护记录必填 | 维护流程 | 期间归属判断 | End 空=当前有效 |
| Allocation_Ratio | NUMBER | 否 | 分摊比例，防重复计算 | 维护流程（业务确认） | 消耗/人数分摊 | 分摊口径变化时更新 |
| Is_Primary | BOOL | 是 | 主项目标识（审计：一人多项目缺主项目标识） | 维护流程 | 默认归属、看板 | 调整时更新 |
| Group_ID | TEXT→Project_Group | 否 | 小组归属（编导-小组-项目 / 剪辑-小组-项目关系，D-015.3）：编导「所带小组覆盖项目」= 该编导生效行挂同一 Group_ID 的 Project_ID 集合；剪辑/摄影归属小组同理；制作部「小组平均值」核算的归属关系承载（business_rules.md「制作部核算规则」章） | 维护流程（随「在职人员对照项目」在线维护同步，D-009.1） | 小组维度聚合（口径待 PO 拍板）、复核看板 | 生效期内稳定；归属调整时更新，历史结果不改写 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

数据源与维护入口（D-009.1）：本表数据以飞书在线人工维护的「在职人员对照项目」表为准；该在线表是唯一人工维护入口，系统直接消费其内容并同步入本表，岗位↔渠道/项目映射关系以该表为权威。

> **变更记录 CHG-T18-002**（2026-08-18，Owner: Product Owner（D-013~D-016 拍板人），任务 t_112edaf5 / T18）：新增 Project_Group 实体（§4.7，前缀 GRP）；本表新增 `Group_ID`（小组归属）；Actual 新增 `Group_ID` / `Material_Type` / `Owner_Employee_ID` / `Material_First_Run_Date`（§5.3）。
> 1. 原因：D-015.3 制作部「小组平均值」核算（当月项目总消耗、项目组剪辑人数、编导所带小组覆盖项目）与 D-016 打分/提成双口径（打分=总消耗、提成=近90天成片）的模型层缺口（T17 标注登记，本条为其落地）。
> 2. 承载方案决策：① D-014 渠道负责关系**不复用本表** Channel_ID 非空行承载，改由 Employee.Responsible_Channel_IDs 承载（见 §4.1 CHG-T18-001，理由：本表 Project_ID 必填且语义为「项目分摊」，与「渠道负责」不同义）；② 小组维度采用「新实体 Project_Group + 本表 Group_ID 归属」而非「Project_ID + 小组属性派生」——小组是跨项目的团队实体（一编导带一小组覆盖多项目），派生方案无法表达「编导-小组-项目」三级归属；③ 项目组剪辑人数仍按本表 Project_ID + 岗位（剪辑）生效行计数（D-007.2 AUTO_COMPUTE 路径），Group_ID 不替代项目粒度聚合。
> 3. 范围约束：仅建模（建表/字段），**不实现小组核算逻辑**——聚合口径、90 天锚点定义、分母口径、组织变更规则均为评审意见书搁置项（`docs/业务规则评审意见书_编导消耗口径_D016.md` 四件事），PO 拍板前任何实现不得消费小组维度做核算（同 T17 标注「不得按编造的小组粒度实现」）。
> 4. 影响：纯新增实体与可选字段，既有字段、181 条结果数据与既有公式不受影响；Base 侧需补建 Project_Group 表与各 Group_ID 关联字段（feishu-builder 后续任务）。

> **变更记录 CHG-T8B-001**（2026-08-15，Owner: Product Owner，见决策日志 D-011）：`Effective_Start` 必填约束调整为「历史占位同步可空 / 正式维护必填」。原因：历史数据源无生效日期且禁止以导入日期伪造，占位记录（`Status=待在线维护`）由在线维护入口补齐。影响：仅放宽 §4.6 占位场景约束，其余字段约束不变。

### 4.7 Project_Group（制作部小组/项目组）

职责：制作部「小组」主数据。一个小组由一名编导带领、覆盖一个或多个项目，是编导「所带小组覆盖项目」聚合与制作部「小组平均值」核算的团队维度（D-015.3，business_rules.md「制作部核算规则」章）。**仅建模，不承载任何核算公式**；小组核算口径（聚合/均摊逻辑）待 PO 拍板后由 BA 落文。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Group_ID | TEXT | 是 | 主键（§2 前缀 GRP） | 主数据维护流程 | 全系统 | 见 §1.1 |
| Group_Name | TEXT | 是 | 人读展示；**禁止作关联键** | 制作部/HR 维护 | 看板、复核界面 | 更名时更新 |
| Leader_Employee_ID | TEXT→Employee | 是 | 小组负责编导：「编导-小组」归属锚点，编导「所带小组覆盖项目」关系由此出发（编导 → 本表 → Project_Member.Group_ID → 覆盖项目集） | 制作部/HR 维护 | 小组聚合路由、复核看板 | 换编导时更新，历史结果不改写 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

关系承载说明：小组-项目覆盖与小组-成员归属**不存本表**，由 Project_Member.Group_ID（§4.6）承载（带生效区间，支持人员调整留痕）；小组粒度实际值由 Actual.Group_ID（§5.3）承载。本表只定义小组身份与负责编导。

## 5. 规则与事实实体

### 5.1 Metric（绩效指标定义）

职责：KPI 定义表。初始注册集 = V04 的 9 岗位 × 45 项 KPI（T1 产出）。**只存定义与原文，不存计算实现**；分档细则的结构化拆解由 Business Analyst 任务填充到容器字段。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Metric_ID | TEXT | 是 | 主键 | V04 迁移流程 | Target/Actual/Result/Commission_Tier | 见 §1.1 |
| Position_ID | TEXT→Position | 是 | 岗位关联（禁止岗位名关联） | V04 迁移 | 全部下游 | 规则版本内稳定 |
| Metric_Number | TEXT | 是 | V04 源编号（含空编号标记，如客服 B11「邀请好评」） | V04 迁移 | 追溯、对账 | 规则版本内稳定 |
| Dimension | TEXT | 是 | 评价维度（组织指标/岗位指标/个人指标） | V04 迁移 | 计算路由、看板 | 规则版本内稳定 |
| Metric_Name | TEXT | 是 | 指标名称 | V04 迁移 | 展示 | 规则版本内稳定 |
| Weight | NUMBER | 是 | 指标权重 | V04 迁移 | 结果计算 | 规则版本内稳定；改版走变更流程 |
| Target_Description | TEXT | 否 | 目标描述原文 | V04 迁移 | 看板解释 | 规则版本内稳定 |
| Calc_Rule_Text | TEXT | 否 | 计算口径**文本原文**（如「达成率=实际GSV达成/预算目标GSV达成」）；仅存档展示，不作为可执行公式 | V04 迁移 | 可解释性、复核 | 规则版本内稳定 |
| Unit | TEXT | 否 | 单位（%、/、万元等） | V04 迁移 | 展示、校验 | 规则版本内稳定 |
| Scoring_Type | TEXT | 是 | 评分类型枚举：ACHIEVEMENT_RATE（达成率/进度型）/ QUALITATIVE（定性等级型）/ THRESHOLD_COUNT（次数阈值型）/ DEDUCTION（扣分制）/ REWARD_PENALTY（奖惩制）——V04 出现的全部五类 | V04 迁移（技术分类，非新增业务规则） | 计算引擎路由 | 规则版本内稳定 |
| Scoring_Standard_Text | TEXT | 是 | 评分标准**原文**（分档、封顶、保底、豁免、奖惩描述一律以原文存档） | V04 迁移 | 可解释性、BA 结构化依据 | 规则版本内稳定 |
| Score_Cap_Value | NUMBER | 否 | 封顶值结构化（如 150/120/110）；从原文转写，不推断 | V04 迁移 | 计算引擎 | 规则版本内稳定 |
| Score_Cap_Is_Open | BOOL | 是 | 不封顶语义显式标记（默认 false）；禁止用魔法数值冒充 | V04 迁移 | 计算引擎 | 规则版本内稳定 |
| Score_Floor_Value | NUMBER | 否 | 保底值结构化；无保底为空 | V04 迁移 | 计算引擎 | 规则版本内稳定 |
| Reward_Condition_Text | TEXT | 否 | 奖励条件原文（客服岗奖励/处罚金额口径存档位，未经确认不进计算） | V04 迁移 | BA 确认、复核 | 规则版本内稳定 |
| Penalty_Condition_Text | TEXT | 否 | 处罚条件原文 | V04 迁移 | BA 确认、复核 | 规则版本内稳定 |
| Scoring_Rule_Payload | TEXT(JSON) | 否 | 分档明细结构化容器；**由 Business Analyst 按三方确认后的规则填充**，模型只定义容器 | Business Analyst | 计算引擎 | 随规则版本演进 |
| Data_Source_Text | TEXT | 是 | V04 数据来源原文（平台数据/云视频管家/部门负责人等） | V04 迁移 | 采集路由 | 规则版本内稳定 |
| Evaluation_Period_Text | TEXT | 是 | 评价周期原文（核算时间+取值范围） | V04 迁移 | 采集与核算窗口 | 规则版本内稳定 |
| Target_Source_Type | TEXT | 是 | D-007 承载：目标来源策略枚举 BUDGET_V60（预算导入）/ PLATFORM_IMPORT（平台导入表）/ AUTO_COMPUTE（自动计算，如项目组人数）/ MANUAL（人工维护）/ TBD（先搭框架后补数） | 迁移+BA/PO 确认 | ETL 路由、校验 | 来源策略确认时更新 |
| Budget_Field_Ref | TEXT | 否 | D-005/D-006 承载：映射的 V60 预算字段名及源行（如「主营业务收入@行3」「广告投流费@行11」）；D-005.2 签收 ROI 派生路径标注「主营业务收入÷广告投流费（D-005 派生）」 | T2 映射+PO 确认 | Target 导入、对账 | 口径确认后写入，改版走变更 |
| Source_Sheet / Source_Cell | TEXT | 是 | V04 源工作表/源单元格定位 | V04 迁移 | 追溯、审计 | 不变 |
| Source_SHA256 | TEXT | 是 | 源文件哈希（V04: 5342d3dd…3250） | V04 迁移 | 权威源校验（D-001） | 换源文件版本时更新 |
| Rule_Version | TEXT | 是 | 规则版本（当前 V04） | V04 迁移 | 结果可回溯 | 新版本生效新增记录，旧版本归档不删 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

V04 评分规则承载位置小结：分档→Scoring_Standard_Text（原文）+ Scoring_Rule_Payload（结构化容器）；封顶/保底→Score_Cap_Value / Score_Cap_Is_Open / Score_Floor_Value；奖惩→Reward/Penalty_Condition_Text；评分类型路由→Scoring_Type；特殊规则（新项目免责提成、达成激励等）→Position 级特殊规则文本暂存 Metric.Scoring_Standard_Text 所属岗位版本的迁移附件说明，正式结构化属 BA 职责，列入待确认清单 §8。

### 5.2 Target（目标值长表）

职责：统一目标值事实表，替代「预算目标导入 + 四个项目预算副本」。一行 = 一个 Period × 一个指标或预算项目 × 一组维度的一个目标值。初始全量 = V60 的 9 渠道 × 12 月 × 57 预算项目 = 6,156 个渠道月度值。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Target_ID | TEXT | 是 | 主键 | V60 导入流程 | 达成率计算、结果 | 见 §1.1 |
| Metric_ID | TEXT→Metric | 条件必填 | 绩效目标标识；与 Budget_Item 二选一（见下行约束） | 导入+映射 | 结果计算 | 映射确认后写入 |
| Budget_Item_Name | TEXT | 条件必填 | 非 KPI 预算项目标识（V60 57 项中多数非 KPI）；与 Metric_ID 二选一，二者必居其一，可同时填写表示已建立映射 | V60 导入 | 预算分析、对账 | 规则版本内稳定 |
| V60_Source_Row | INTEGER | 否 | V60 源行号（如主营业务收入=3、广告投流费=11），D-005/D-006 口径定位 | V60 导入 | 追溯、对账 | 不变 |
| Period | TEXT(YYYY-MM) | 是 | 期间 | V60 导入 | 全部下游 | 不变 |
| Channel_ID | TEXT→Channel | 条件必填 | 渠道维度；V60 渠道级目标必填 | V60 导入+渠道映射 | 达成率计算 | 不变 |
| Project_ID | TEXT→Project | 否 | 项目归属（ID 关联，禁文本包含匹配） | 映射确认 | 项目维度核算 | 映射确认后写入 |
| Org_ID | TEXT→Organization | 否 | 部门归属 | 映射确认 | 组织维度核算 | 映射确认后写入 |
| Target_Value | NUMBER | 是 | 目标值 | V60 导入 | 达成率计算 | 改版走变更流程，历史不覆盖 |
| Unit | TEXT | 是 | 单位（万元/比例） | V60 导入 | 展示、校验 | 不变 |
| Source_File / Source_Sheet / Source_Cell | TEXT | 是 | 源文件、工作表（总表-渠道二维汇总）、单元格定位 | V60 导入 | 逐值追溯 | 不变 |
| Source_Formula | TEXT | 否 | 源单元格原公式存档（含 #REF! 原样保留，只记录不修复） | V60 导入 | 审计、差异排查 | 不变 |
| Source_Cached_Value | NUMBER | 否 | 源缓存值（与 Target_Value 对照，发现口径漂移） | V60 导入 | 对账 | 不变 |
| Source_SHA256 | TEXT | 是 | 源文件哈希（V60: 65d3c2a6…5943），D-001 权威源校验 | V60 导入 | 审计 | 换源版本时新批次 |
| Import_Batch_ID | TEXT→Import_Batch | 是 | 批次追溯 | 导入流程 | 审计、错误回溯 | 不变 |
| Import_Status | TEXT | 是 | 导入状态（成功/失败/待确认） | 导入流程 | 校验、看板 | 导入时写入 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

### 5.3 Actual（实际达成长表）

职责：实际值事实层。**只存实际值与采集证据，不写绩效结论**。一行 = 一个 Period × 一个 Metric × 一组维度的一个实际值。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Actual_ID | TEXT | 是 | 主键 | 采集/导入流程 | 达成率计算、结果 | 见 §1.1 |
| Metric_ID | TEXT→Metric | 是 | 指标关联 | 采集流程 | 结果计算 | 不变 |
| Period | TEXT(YYYY-MM) | 是 | 期间 | 采集流程 | 全部下游 | 不变 |
| Employee_ID | TEXT→Employee | 条件必填 | 个人粒度实际值；Employee/Org/Project/Channel/Group 五类主体至少填一类（第五类 Group_ID 由 CHG-T18-002 引入） | 采集流程 | 个人指标计算 | 不变 |
| Org_ID / Project_ID / Channel_ID | TEXT | 条件必填 | 组织/项目/渠道粒度实际值（如团队 GSV、渠道消耗） | 采集流程 | 组织指标计算 | 不变 |
| Group_ID | TEXT→Project_Group | 条件必填 | 小组粒度实际值（第五类主体，D-015.3）：制作部「当月项目总消耗/项目组剪辑总产出」等小组聚合的输入；与既有四类主体并列，至少填一类的约束同步涵盖 | 采集/导入流程 | 小组维度聚合（口径待 PO 拍板，见 §4.6 CHG-T18-002 范围约束）、复核看板 | 不变 |
| Actual_Value | NUMBER | 是 | 实际值 | 采集流程 | 达成率计算 | 修正走补录新记录或状态流转，不静默改数 |
| Unit | TEXT | 是 | 单位 | 采集流程 | 校验、展示 | 不变 |
| Material_Type | TEXT | 否 | 素材类型标识（D-016 打分/提成双口径的行级区分依据）：NEW_MATERIAL（新素材/近90天成片）/ HISTORICAL_MATERIAL（历史素材）；打分口径=总消耗（两类合计）、提成口径=近90天成片（NEW_MATERIAL 筛选），空=不适用（非素材类实际值） | 平台导入流程（视频管理系统/云视频管家，导入时按素材首投口径标注；D-007 路径1 导入表） | 计算引擎（打分/提成口径分离）、复核看板 | 导入时写入，不变 |
| Owner_Employee_ID | TEXT→Employee | 否 | 素材主责人归因预留（评审意见书 §5：主责编导/协作编导中的主责方）；90 天锚点与归因规则为搁置项，**当前不产生值、不被消费** | 平台导入流程（预留，暂不实现取数） | 未来归因/归属判定逻辑（评审意见书搁置项，PO 拍板后启用） | 口径拍板前留空；启用后导入时写入，不变 |
| Material_First_Run_Date | DATE | 否 | 素材首投日期预留：D-016 提成口径「近90天成片」的 90 天锚点载体（评审意见书 §5：首次投放日期必须唯一可追溯）；锚点定义（如「首投日 ∈（考核月末−90天, 考核月末]」）为搁置项，**不实现判定逻辑** | 平台导入流程（预留，暂不实现取数） | 未来 90 天锚点判定、Material_Type 自动标注 | 口径拍板前留空；启用后导入时写入，不变 |
| Source_Type | TEXT | 是 | 来源类型枚举：MANUAL_REPORT（业务员对话上报，D-003）/ PLATFORM_IMPORT（平台数据导入）/ MANUAL_ENTRY（人工补录）/ AUTO_COMPUTE（自动计算） | 采集流程 | 路由、审计 | 不变 |
| Source_Ref | TEXT | 否 | 来源说明（平台名、对话批次、备注） | 采集流程 | 复核证据 | 不变 |
| Collected_By | TEXT→Employee | 是 | 上传人/登记人 | 采集流程 | 复核、追责 | 不变 |
| Collected_Time | DATETIME | 是 | 采集时间 | 采集流程 | 复核、时序排查 | 不变 |
| Validation_Status | TEXT | 是 | 校验状态（待校验/通过/驳回） | 校验流程 | 计算准入 | 校验后流转 |
| Import_Batch_ID | TEXT→Import_Batch | 是 | 批次追溯 | 采集流程 | 审计 | 不变 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

来源注明（D-009.2）：素材 90 天归因数据来源为视频管理系统自动下载数据，绩效核算直接套数出结果；该来源走 Source_Type=PLATFORM_IMPORT（D-007 路径1：建导入表）。

> **【已落地 / CHG-T18-002，2026-08-18】** 原 D-015.3 项目组/小组维度【待模型变更】标注已落地：`Group_ID`（小组粒度，实体见 §4.7 Project_Group）、`Material_Type`（D-016 打分/提成双口径素材区分）、`Owner_Employee_ID` 与 `Material_First_Run_Date`（主责人归因 / 90 天锚点预留，取数与判定逻辑**不实现**，评审意见书搁置项）。
> 1. 摄影师「个人发布工单数/工单任务数」属工单粒度数据，本次**未建模**——工单实体（或 Actual 扩展）待 PO 口径后另走 §17 变更。
> 2. D-015 广告投放「导入即最终」约束不变：Actual 无筛选/拆分逻辑，`Material_Type` 仅为行级标识，不构成系统内筛选动作；广告投放消耗行 Material_Type 恒为 NEW_MATERIAL 语义（导入前已按近90天成片筛选），制作为空不填亦可，由导入模板约定。
> 3. 素材级主数据实体（素材ID、协作编导、退款/冲正等，评审意见书 §5）属搁置项，本次仅落行级标识与归因预留字段，不建素材实体。

### 5.4 Performance_Result（绩效结果长表）

职责：按人员×期间×指标粒度保存最终结果，承载完整解释链 Target → Actual → Achievement Rate → Weight → Score（规则 §7）。**由飞书计算引擎产生；Agent 禁止直接修改**。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Result_ID | TEXT | 是 | 主键 | 计算引擎 | 提成结算、复核 | 见 §1.1 |
| Period | TEXT(YYYY-MM) | 是 | 期间 | 计算引擎 | 全部下游 | 不变 |
| Employee_ID | TEXT→Employee | 是 | 人员关联 | 计算引擎 | 全部下游 | 不变 |
| Metric_ID | TEXT→Metric | 是 | 指标关联 | 计算引擎 | 解释链 | 不变 |
| Target_ID | TEXT→Target | 否 | 解释链：目标溯源（定性指标无 Target，可空） | 计算引擎 | 复核、审计 | 不变 |
| Actual_ID | TEXT→Actual | 否 | 解释链：实际值溯源（负责人打分指标可空） | 计算引擎 | 复核、审计 | 不变 |
| Achievement_Rate | NUMBER | 否 | 达成率（解释链环节；定性/扣分/奖惩类可空） | 计算引擎 | 解释、复核 | 重算时整批重出 |
| Weight | NUMBER | 是 | 计算时权重快照（防 Metric 改版后历史失真） | 计算引擎（取自 Metric） | 解释链 | 随批次固定 |
| Auto_Score | NUMBER | 否 | 自动计算单项得分 | 计算引擎 | 结果汇总 | 重算时整批重出 |
| Manual_Score | NUMBER | 否 | 负责人打分（定性指标输入） | 部门负责人/直属主管 | 结果汇总 | 打分截止后锁定 |
| Final_Score | NUMBER | 是 | 最终单项得分 | 计算引擎 | 绩效总分、提成 | 重算时整批重出 |
| Rule_Version | TEXT | 是 | 计算所用规则版本快照 | 计算引擎 | 可回溯 | 随批次固定 |
| Calc_Batch_ID | TEXT→Import_Batch | 是 | 计算批次（Batch_Type=CALC），整批重算追溯 | 计算引擎 | 审计、重算管理 | 不变 |
| Review_Status | TEXT | 是 | 复核状态（待复核/已复核/已确认/有异议） | 复核流程 | 结算准入 | 复核流程流转 |
| Project_ID | TEXT→Project | 否 | 项目关联：新项目豁免判断（Q-10-01）与提成基数归属都需要结果行的项目维度 | 计算引擎（按 Project_Member 生效关系解析，默认取 Is_Primary；一人多项目归属口径待 BA） | 豁免判断、提成结算、复核 | 随计算批次写入，重算整批重出 |
| Project_Run_Days | NUMBER（Base 侧 formula） | 否 | 项目运行天数：豁免判断的时间输入；基准日 = Period 对应自然月最后一日（不用 TODAY()，保证历史期间可回溯） | 计算引擎公式（由 Project.Start_Date 推导；Start_Date 缺失时留空，不伪造日期） | Is_Exempt、复核 | 公式派生，随 Period / Start_Date 变化 |
| Revenue_Actual_ID | TEXT→Actual | 否 | 当月营收（退货后 GSV）Actual 溯源；避免把缺失营收静默视为 0 | 计算引擎按项目+渠道+期间匹配 GSV Actual 写入 | Monthly_Revenue、Is_Exempt、复算审计 | 随计算批次重算；无匹配留空并标记待确认 |
| Monthly_Revenue | NUMBER（Base 侧 formula） | 否 | 从 Revenue_Actual_ID 读取当月退货后 GSV；统一单位为元（CNY） | Base 公式（FIRST(Revenue_Actual_ID.Actual_Value)） | Is_Exempt、复核看板 | 公式派生；空=营收未知【待确认】，不得按 0 判定 |
| Is_Exempt | BOOL（Base 侧 formula） | 否 | 新项目豁免标志：`Project_Run_Days < Max_Project_Run_Days AND Monthly_Revenue ≤ Max_Monthly_Revenue` | Base 公式读取 Exemption_Scope 配置与 Monthly_Revenue | 提成结算准入、复算审计 | 公式派生；任一输入缺失则留空（营收未知【待确认】），不擅自判定 |
| Exemption_Scope_ID | TEXT→Exemption_Scope | 否 | 豁免适用范围命中记录：结果行按岗位/岗位族 × 渠道匹配到哪条豁免配置（D-010-R2 配置化）。未命中留空 | 计算引擎（按 Exemption_Scope 配置匹配写入，CHG-D010-R2-001） | Is_Exempt 展示、审计复算、复核看板 | 随计算批次重算，整批重出 |
| Commission_Base_Type | TEXT | 否 | 提成基数类型枚举（GSV / 个人消耗 / 个人营收，D-009 / 2026-08-17）：决定 Commission_Base 的取数口径 | 计算引擎按岗位类型写入快照（岗位→基数类型映射待 T11b BA 结构化） | 提成计算、复核 | 随计算批次写入 |
| Commission_Base | NUMBER | 否 | 提成基数金额（Q-10-02）：提成金额 = 基数 × 比例的基数项 | 计算引擎（按 Commission_Base_Type 口径取数，T11b 落公式后启用） | 提成金额计算、复核 | 重算时整批重出 |
| Commission_Ratio | NUMBER | 否 | 提成比例快照：留痕用，防梯度/比例改版后历史失真（同 Weight 快照语义） | 计算引擎（取自 Commission_Tier，T11b） | 提成复算、审计 | 随批次固定 |
| Commission_Amount | NUMBER | 否 | 提成金额产出（Q-10-02 承载字段）；模型层只定义容器，计算公式属 BA 职责（规则 §8） | 计算引擎（T11b 落公式） | 提成结算、复核看板 | 重算时整批重出 |
| Perf_Salary_Snapshot | NUMBER | 否 | 计算时绩效工资快照（CHG-T18-001）：直播中控收入「绩效工资×档位百分比」的取数留痕，防薪资调整后历史重算失真（同 Weight / Commission_Ratio 快照语义）；非直播中控岗位留空 | 计算引擎（取自 Employee.Perf_Salary，直播中控收入公式实现任务写入） | 提成结算、复算审计、复核看板 | 随计算批次固定，重算整批重出 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1（Source 固定为 CALC_ENGINE） | — | — | — |

提成字段粒度注明（CHG-T11A-001）：本表粒度为「期间×人员×指标」，而提成四字段（Commission_Base_Type / Commission_Base / Commission_Ratio / Commission_Amount）业务粒度为「期间×人员」；同一 Employee_ID + Period 的各行取值相同（沿用 Monthly_Total 既有冗余模式），提成结算消费方须按 Employee_ID + Period 去重读取，禁止逐行累加。

> **变更记录 CHG-T11A-001**（2026-08-17，Owner: Product Owner，任务 t_455dcc0b / T11a）：Performance_Result 新增 7 个可选字段——Project_ID、Project_Run_Days、Is_Exempt、Commission_Base_Type、Commission_Base、Commission_Ratio、Commission_Amount。原因：QA 阻断项 Q-10-01（新项目 <90 天豁免无法计算）与 Q-10-02（无提成金额产出）的模型层缺口，落地 D-009（2026-08-17）提成基数口径。影响：纯新增可选字段，既有 161 条结果数据与全部既有公式不受影响；提成计算公式与岗位→基数映射的业务实现属 T11b（BA）范围，本变更只提供模型容器。

双部分结构注明（D-009.3）：结果模型 = 自动计算部分 + 负责人填写部分，合计出最终结果（参照现有「绩效得分结果（负责人打分）」表结构），已由 Auto_Score / Manual_Score / Final_Score 三字段承载。电商客服奖励/处罚金额不进入自动计算规则，由客服主管手动录入，走 Manual_Score 字段。

### 5.5 Commission_Tier（提成梯度定义）

职责：提成梯度规则表。初始注册集 = V04 的 42 条梯度；非 V04 的 41 条进入历史参考区，不进正式表。只存梯度定义与原文，不写计算实现。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Commission_Tier_ID | TEXT | 是 | 主键 | V04 迁移流程 | 提成计算 | 见 §1.1 |
| Position_ID | TEXT→Position | 是 | 岗位关联（禁职务名模糊匹配） | V04 迁移 | 提成计算 | 规则版本内稳定 |
| Metric_ID | TEXT→Metric | 否 | 提成来源可关联到指标时填写（如运营店铺 GSV→团队 GSV 指标） | 迁移+BA 确认 | 提成计算 | 映射确认后写入 |
| Commission_Source_Text | TEXT | 是 | 提成来源原文（运营店铺GSV/投放账户广告消耗/个人直播时段GSV 等） | V04 迁移 | 解释、对账 | 规则版本内稳定 |
| Tier_Level | INTEGER | 是 | 档位序号 | V04 迁移 | 计算、展示 | 规则版本内稳定 |
| Score_Lower | NUMBER | 是 | 得分下限（含） | V04 迁移 | 梯度匹配 | 规则版本内稳定 |
| Score_Upper | NUMBER | 否 | 得分上限（不含）；不封顶时为空 | V04 迁移 | 梯度匹配 | 规则版本内稳定 |
| Upper_Is_Open | BOOL | 是 | 「不封顶」开放上限显式语义（替代现状固定写 200 的错误做法） | V04 迁移 | 梯度匹配 | 规则版本内稳定 |
| Coefficient | NUMBER | 否 | 系数比例（L 列数值） | V04 迁移 | 提成计算 | 规则版本内稳定 |
| Ratio_Text | TEXT | 否 | 提成比例原文（含公式文本如「=$K$12*L14」「绩效工资*80%」「0.1%/中控人数」，原样存档，不自行重排） | V04 迁移 | 解释、BA 结构化依据 | 规则版本内稳定 |
| Ratio_Value | NUMBER | 否 | 纯数值比例的结构化值（如 0.001）；混合表达式时为空 | V04 迁移 | 提成计算 | 规则版本内稳定 |
| Base_Rate | NUMBER | 否 | 岗位族固定提成基数比例（D-010-R2 配置化，CHG-D010-R2-001）：当前运营族=0.003（源 V04 运营 K12 / 高级主管 M12）。冗余在所属岗位族各梯度行；读取取该岗位任一 Active 梯度行。正常路径 `Ratio = Base_Rate × Coefficient`，豁免路径 `Ratio = Base_Rate`。**禁止在公式/脚本内嵌 0.003** | 规则维护（BA+PO 确认后回填/更新） | 提成计算、豁免提成、复算审计 | 改配置即生效（更新后重跑批次）；规则版本内稳定，改版走 §17 |
| Applicable_Scope | TEXT | 否 | 适用范围结构化承载（D-006：消耗分奖金仅限抖音、视频号两平台内容制作团队；存渠道/团队范围描述，ID 化待映射确认） | V04 迁移+PO 确认 | 提成计算准入 | 口径确认后写入 |
| Rule_Note | TEXT | 否 | 规则说明原文（人数相关口径、绩效工资比例口径等未确认项只结构化存储） | V04 迁移 | 解释、待确认跟踪 | 规则版本内稳定 |
| Source_Sheet / Source_Cell | TEXT | 是 | V04 源工作表/单元格 | V04 迁移 | 追溯 | 不变 |
| Source_SHA256 | TEXT | 是 | 源文件哈希 | V04 迁移 | 权威源校验 | 换源版本时更新 |
| Rule_Version | TEXT | 是 | 规则版本（当前 V04） | V04 迁移 | 可回溯 | 新版本新增，旧版归档 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

梯度匹配兜底规则（D-009.5）：得分超出有上限梯度的最高分档时，按最高一档处理。该兜底语义与 Upper_Is_Open 的「不封顶」语义不同：前者针对有上限梯度被超出时的取值规则，后者针对 V04 原文即不设上限的梯度，两者不得混用。

### 5.6 Exemption_Scope（豁免适用范围配置表）

职责：豁免规则的可配置适用范围（D-010-R3，CHG-D010-R3-001）。一行 = 一个「岗位/岗位族 × 渠道 × 运行天数阈值 × 当月营收阈值」组合；引擎按结果行岗位 + 渠道匹配，且运行天数与营收同时合格才豁免。**新增范围 = 新增一行，禁止在公式/脚本写死单一岗位或阈值。**

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Exemption_Scope_ID | TEXT | 是 | 主键 | 规则维护 | 引擎匹配、Performance_Result.Exemption_Scope_ID 关联 | 见 §1.1 |
| Position_ID | TEXT→Position | 条件必填 | 岗位绑定（精确匹配）；与 Position_Family 至少填一 | 规则维护 | 引擎匹配 | 规则版本内稳定 |
| Position_Family | TEXT | 条件必填 | 岗位族绑定（运营/内容部/主播…）：支撑「其他渠道运营岗」按族扩展，不写死单一岗位；与 Position_ID 至少填一 | 规则维护 | 引擎匹配 | 规则版本内稳定 |
| Channel_ID | TEXT→Channel | 否 | 渠道绑定（抖音=CH000001）；空 = 全部渠道 | 规则维护 | 引擎匹配 | 规则版本内稳定 |
| Max_Project_Run_Days | NUMBER | 是 | 豁免期阈值（当前 90，V04 新项目免责期，QA Q-10-01） | 规则维护 | 引擎匹配（Is_Exempt 判定） | 规则版本内稳定 |
| Max_Monthly_Revenue | NUMBER（CNY 元） | 是 | 当月退货后 GSV 豁免上限（当前 1,000,000 元）；与天数条件构成 AND，统一以元存储避免万元/元歧义 | 规则维护 | Is_Exempt 判定、独立复算 | 规则版本内稳定；改配置后重跑计算批次 |
| Rule_Version | TEXT | 是 | 规则版本（EXS000001 当前 `V04+D-010-R3`；其 R2 来源保留于 Note 与变更日志） | 规则维护 | 可回溯 | 新版本新增；历史版本不静默覆盖 |
| Note | TEXT | 否 | 说明（如「D-010-R1 当前范围：仅抖音兴趣电商运营岗」） | 规则维护 | 解释、审计 | 变更时更新 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1（Status=Active/Inactive，停用即回滚手段，不删除记录） | — | — | — |

匹配语义：范围命中 =（Position_ID 匹配 **或** Position_Family 匹配）**且**（Channel_ID 空 **或** 匹配结果行渠道）**且** Status=Active；豁免成立 = 范围命中 **且** Project_Run_Days < Max_Project_Run_Days **且** Monthly_Revenue ≤ Max_Monthly_Revenue。Position_ID 精确匹配优先于 Position_Family 匹配；同 Position+Channel 不得两条 Active（Validation_Rule）。当月营收来源 = `Revenue_Actual_ID → Actual.Actual_Value`，由项目+渠道+期间匹配的退货后 GSV 写入；缺 Actual/值时为「营收未知【待确认】」，Is_Exempt 留空，不按豁免或不豁免处理。结果行渠道解析路径 = Project_ID → Project_Member（Employee+Project 生效关系，D-009.1）→ Channel_ID，一人多项目取 Is_Primary；渠道无法解析视为不匹配（不豁免）。

种子配置（当前生效）：EXS000001 = {Position_ID=POS000013（兴趣电商运营）、Position_Family=运营、Channel_ID=CH000001（抖音）、Max_Project_Run_Days=90、Max_Monthly_Revenue=1000000（元）、Rule_Version=V04+D-010-R3、Status=Active}。其 R2 来源为 `V04+D-010-R2`，保留在 Base 的 `Note` 与 CHG-D010-R3-001 变更日志中；回滚时可恢复为 R2 值，禁止静默改写。

> **变更记录 CHG-D010-R3-001**（2026-08-18，Owner: Product Owner（D-010-R3 拍板人），实施任务 t_5c9c1f08 / T23）：Exemption_Scope 新增 `Max_Monthly_Revenue`（NUMBER，统一单位 CNY 元）；Performance_Result 新增 `Revenue_Actual_ID` 与 `Monthly_Revenue`，并将 Is_Exempt 更新为天数与营收双条件 AND。原因：D-010-R3 明确项目运行不足 90 天且当月营收不超过 100 万才豁免。影响：既有业务结果不直接改写；缺失营收 Actual 时留空并标记待确认，禁止静默以 0 替代。模拟验证来源 `SIMULATED_T23_D010_R3`，精确回滚清单见 `data/output/T23_D010_R3回滚清单.json`。

> **追溯修正 CHG-D010-R3-001-TRACE**（2026-08-18，T23 复核返工）：EXS000001 的 `Rule_Version` 更新为 `V04+D-010-R3`，字段说明同步指向当前 R3；R2 来源信息不删除，保留于该记录 `Note` 与本节 CHG-D010-R2-001。可逆回滚值、Base 读回快照和验证结果见 `data/output/T23_D010_R3追溯修正计划.json`、`data/output/T23_D010_R3追溯修正执行结果.json`；该修正只修正规则追溯元数据，不变更营收阈值或历史计算结果。

> **变更记录 CHG-D010-R2-001**（2026-08-17，Owner: Product Owner，任务 t_124c9981 / D-010-R2）：新增 Exemption_Scope 表（§5.6）；Commission_Tier 新增 Base_Rate 字段（§5.5）；Performance_Result 新增 Exemption_Scope_ID 字段（§5.4）。原因：D-010-R2 要求提成基数（当前 0.003）与豁免适用范围（当前仅抖音兴趣电商运营岗）可配置化、改配置即生效、不得硬编码进公式或写死单一岗位。影响：三个结构在 Base 已存在（CHG-T15B-001 遗留，未入模型/未回填/未实现），本次正式化模型并定义读取规则；纯新增字段/表，既有 181 条结果与既有公式不受影响；计算公式不内嵌任何配置值。

## 6. 支撑实体

### 6.1 Import_Batch（导入/计算批次）

职责：所有写入链路（预算导入、达成导入、人员导入、计算批次）的统一批次追踪，满足「任何失败必须可追踪」。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Batch_ID | TEXT | 是 | 主键 | 写入流程 | 审计、Error_Log | 见 §1.1 |
| Batch_Type | TEXT | 是 | 批次类型：BUDGET / ACTUAL / EMPLOYEE / MASTER_DATA / CALC | 写入流程 | 路由、统计 | 不变 |
| Source_Type | TEXT | 是 | 来源类型（Excel 文件/对话上报/平台接口/计算引擎） | 写入流程 | 审计 | 不变 |
| Source_File | TEXT | 否 | 来源文件名 | 写入流程 | 追溯 | 不变 |
| Source_SHA256 | TEXT | 否 | 来源文件哈希（D-001 权威源一致性核验） | 写入流程 | 审计 | 不变 |
| Import_Time | DATETIME | 是 | 批次时间 | 写入流程 | 时序排查 | 不变 |
| Operator | TEXT | 是 | 操作者（人或 Agent 流程标识） | 写入流程 | 追责 | 不变 |
| Total_Count / Success_Count / Fail_Count | INTEGER | 是 | 数量校验（如 V60 迁移须核对 6,156；V04 核对 45 KPI、42 梯度） | 写入流程 | 校验、对账 | 批次结束时写入 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1（Status：Running/Success/Partial/Failed） | — | — | — |

### 6.2 Validation_Rule（校验规则定义）

职责：校验规则注册表，供 ETL 与计算准入统一执行。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Rule_ID | TEXT | 是 | 主键 | 架构/数据工程定义 | 校验流程 | 见 §1.1 |
| Target_Entity | TEXT | 是 | 校验对象（16 实体之一；第 15 实体 Exemption_Scope 由 CHG-D010-R2-001、第 16 实体 Project_Group 由 CHG-T18-002 引入） | 定义方 | 校验流程 | 稳定 |
| Rule_Type | TEXT | 是 | 校验类型：必填 / ID 存在性 / 期间合法性 / 值类型 / 渠道映射 / 指标映射 / 数量对账 | 定义方 | 校验流程 | 稳定 |
| Rule_Expression | TEXT | 是 | 校验口径文本描述（结构化表达式由 Data Engineer 实现任务定义） | 定义方 | 校验流程、Data Engineer | 随实现完善 |
| Severity | TEXT | 是 | 严重级别（BLOCKER 阻断入库 / WARNING 告警） | 定义方 | 校验流程 | 稳定 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1（Status=启用/停用） | — | — | — |

### 6.3 Error_Log（错误日志）

职责：规则 §15「任何失败必须生成 Error Log，禁止静默失败」的承载表。

| 字段 | 类型 | 必填 | 为什么需要 | 谁产生 | 谁消费 | 生命周期 |
|---|---|---|---|---|---|---|
| Error_ID | TEXT | 是 | 主键 | 校验/写入流程 | 运维、Data Engineer | 见 §1.1 |
| Batch_ID | TEXT→Import_Batch | 是 | 归属批次 | 产生流程 | 批次对账 | 不变 |
| Object_Type / Object_ID | TEXT | 是 | 出错对象定位 | 产生流程 | 修复 | 不变 |
| Error_Type | TEXT | 是 | 错误分类（对应 Validation_Rule.Rule_Type） | 产生流程 | 统计、修复 | 不变 |
| Error_Content | TEXT | 是 | 错误详情 | 产生流程 | 修复 | 不变 |
| Process_Status | TEXT | 是 | 处理状态（待处理/处理中/已解决/已忽略需说明） | 处理人 | 跟踪 | 流转 |
| Handler / Handle_Time | TEXT / DATETIME | 否 | 处理人与时间 | 处理人 | 追责 | 处理时写入 |
| Source / Create_Time / Update_Time / Status | — | 是 | 见 §1.1 | — | — | — |

## 7. 决策落实对照（D-001~D-009）

| 决策 | 落实方式 |
|---|---|
| D-001 权威数据源为本地文件 | 各表 Source_SHA256 / Source_File / Source_Sheet / Source_Cell 字段承载权威源定位与一致性校验；Target 保留 Source_Formula 与 Source_Cached_Value 双轨 |
| D-002 从 0 重建 | 本模型不含任何旧 Base 遗留字段；旧 20 表仅作字段参考，不进入模型 |
| D-003 系统形态与边界 | Actual.Source_Type 含 MANUAL_REPORT（业务员对话上报）与 AUTO_COMPUTE；Kanban 不进模型 |
| D-004 分批发卡 | 与数据模型无关（开发管理决策），本模型一次设计、分批实现 |
| D-005 口径映射 | Metric.Budget_Field_Ref 承载「主营业务收入@行3=退货后 GSV」；签收 ROI 派生路径标注于 Budget_Field_Ref（D-005 派生），派生目标值入 Target 时 Source_Formula 记录推导路径 |
| D-006 消耗口径与平台限制 | Metric.Budget_Field_Ref=「广告投流费@行11」承载消耗口径；「仅抖音/视频号内容制作团队分奖金」由 Commission_Tier.Applicable_Scope 承载 |
| D-007 无预算字段指标策略 | Metric.Target_Source_Type 枚举承载四类去路（PLATFORM_IMPORT / AUTO_COMPUTE / MANUAL / TBD）；AUTO_COMPUTE 所需项目组人数由 Project_Member 提供数据基础 |
| D-008 花名册模拟数据 | Employee.Data_Origin 标记 ROSTER_MOCK / HR_OFFICIAL；切换按 §4.1 预留方案在原 ID 上更新，不换号 |
| D-009 5 项口径确认 | ① 岗位↔渠道/项目映射：Project_Member 数据源与维护入口=在线人工维护的「在职人员对照项目」表（§4.6 注）；② 90 天归因来源：Actual.Source_Type 注明视频管理系统自动下载、直接套数（§5.3 注，走 D-007 路径1 导入表）；③ 客服奖惩：不进自动规则，客服主管手动录入走 Performance_Result.Manual_Score，双部分结构已承载（§5.4 注）；④ 新项目免责提成：HR 人工评判走人工部分不进公式（§8 第3条部分关闭）；⑤ 超梯度上限：按最高一档处理，兜底规则注明于 §5.5 梯度匹配语义 |
| D-009 提成基数口径（2026-08-17） | Performance_Result 新增 Commission_Base_Type / Commission_Base / Commission_Ratio / Commission_Amount 四字段承载（§5.4，CHG-T11A-001）；岗位→基数类型映射与各岗提成比例由 T11b（BA）从 V04 提成梯度表提取并结构化 |
| D-010-R1 豁免口径（2026-08-17） | Is_Exempt 保留为时间资格标记；豁免期提成=提成基数×达成GSV、跳过梯度/系数；打分照常（Auto_Score/Weighted_Score 正常计算，T14 已验证） |
| D-010-R2 提成基数与豁免范围可配置化（2026-08-17） | Commission_Tier.Base_Rate 承载岗位族固定基数（当前 0.003，不硬编码）；Exemption_Scope 表承载豁免适用范围（岗位/岗位族×渠道×阈值，新增范围=新增行）；Performance_Result.Exemption_Scope_ID 记录命中（§5.4/§5.5/§5.6，CHG-D010-R2-001） |
| D-013 直播中控收入（2026-08-17） | 收入 = 绩效工资×档位百分比（80%/90%/100%/110%）＋ 渠道GSV×0.001÷中控人数。绩效工资=Employee.Perf_Salary（§4.1，CHG-T18-001 已落地）、负责渠道=Employee.Responsible_Channel_IDs（§4.1，多值）、计算时快照=Performance_Result.Perf_Salary_Snapshot（§5.4）；档位百分比映射见 business_rules.md「直播中控收入规则」章；关闭 QA Q-T15-04 与待确认清单第1条 |
| D-014 渠道 GSV 多人分摊（2026-08-17） | 运营/高级主管按各自负责渠道全额计提，无分摊公式；负责渠道关系=Employee.Responsible_Channel_IDs（§4.1，CHG-T18-001 已落地；经评估不复用 §4.6 Project_Member 承载，理由见该节变更记录）；关闭待确认清单第4条 |
| D-015 广告投放消耗与制作部方向（2026-08-17） | 广告投放消耗达成值=导入即最终（Actual 无筛选逻辑，§5.3 注）；制作部「小组平均值」核算规则落文 business_rules.md「制作部核算规则」章，Actual 小组维度=§5.3 Group_ID + §4.7 Project_Group + §4.6 Project_Member.Group_ID（CHG-T18-002 已建模，核算逻辑不实现） |
| D-016 编导消耗达成率口径（2026-08-17） | 编导「团队产出消耗金额」打分=项目组总消耗÷预算目标消耗值（G8 公式，总消耗口径无 90 天区分，F8 近90天成片原意作废）；提成=个人近90天成片消耗×档位比例（打分与提成分离）；双口径行级区分=Actual.Material_Type（§5.3，CHG-T18-002），90 天锚点载体=Actual.Material_First_Run_Date（预留不实现）；爆款激励不受影响。规则见 business_rules.md「制作部核算规则」章；关闭差异标注 3 与待确认清单第 5 条 |
| D-017 广告投放提成口径+摄影师评分边界（2026-08-17） | 广告投放提成按 V04 原文「投放账户广告消耗」口径推进（4 档 0.001），GSV 口径待 HR 复核（确认前不更改）；摄影师「个人素材数量」评分：达成率<100%→0 分、≥100%→100 分。关闭差异标注 4 与 D-006 范围关系（广告投放按 Applicable_Scope 注记执行）；新增待确认清单第 12 条 |

## 8. 待确认清单（业务歧义，不自行裁断）

1. 项目组人数 AUTO_COMPUTE 的具体口径（是否按 Project_Member 生效期去重、是否含停用人员）——待 BA 定义。
2. 【已关闭 2026-08-14 / D-009.1】Position 与负责渠道/负责项目的正式映射关系（修复建议 P2-2.3）：以在线人工维护的「在职人员对照项目」表为准，系统直接消费；Project_Member 数据源与维护入口见 §4.6 注。Commission_Tier.Applicable_Scope 的 ID 化映射仍按原口径推进。
3. V04 岗位级特殊规则的结构化表达方式：「新项目免责提成 ×0.8」【已关闭 2026-08-14 / D-009.4：无法完全数字化，由 HR 人工评判，走负责人填写/人工部分，不进公式】；「达成激励 3% 项目利润」「视频号/少年状元/骨能考核方式」保留待确认——待 BA + PO 确认。
4. Target 中非 KPI 预算项目未来是否升级为独立 Budget_Item 实体（当前以 Budget_Item_Name + V60_Source_Row 承载，不影响 6,156 值迁移）。
5. 【已关闭 2026-08-14 / D-009.5】超出梯度上限得分的处理（修复建议 P2-2.7）：按最高一档处理，不外推；兜底规则与 Upper_Is_Open 语义区分见 §5.5 注。
6. 【已关闭 2026-08-14 / D-009.3】电商客服奖励/处罚金额是否属正式绩效规则（修复建议 P2-2.5）：不进入自动计算规则，由客服主管手动录入走 Performance_Result.Manual_Score，见 §5.4 注；Reward/Penalty_Condition_Text 原文继续存档。
7. 【已关闭 2026-08-14 / D-009.2】素材 90 天归因窗口的数据来源与字段扩展：来源为视频管理系统自动下载、绩效核算直接套数（D-007 路径1 导入表），Actual.Source_Type 注明见 §5.3 注；归因窗口字段如需扩展走变更流程。
8. 「编导」与「内容主管/编导」是否归一为同一 Position_ID——当前用 Position_Alias 承载，待 PO 确认。
9. 【已关闭 2026-08-18 / CHG-T18-001】D-013 直播中控收入所需 Employee 新增字段：`Perf_Salary`（绩效工资）、`Responsible_Channel_IDs`（负责渠道，多值 link→Channel）已落地（§4.1），计算时快照 `Performance_Result.Perf_Salary_Snapshot`（§5.4）；Base 侧建字段由 feishu-builder 后续任务执行。
10. 【已关闭 2026-08-18 / CHG-T18-002】D-015.3 制作部「小组平均值」核算所需小组维度：Project_Group 实体（§4.7）+ Project_Member.Group_ID（§4.6）+ Actual.Group_ID/Material_Type/归因预留字段（§5.3）已建模。残留待确认（不阻塞，属评审意见书搁置项）：① 小组聚合口径、90 天锚点定义、分母口径、组织变更规则待 PO 拍板（拍板前禁止消费小组维度做核算）；② 摄影师工单粒度（工单数/工单任务数）未建模，待口径后另走 §17。
11. 【已关闭 2026-08-18 / D-017】广告投放消耗提成与 D-006「仅抖音/视频号内容制作团队分奖金」范围的关系：广告投放按 V04 原文「投放账户广告消耗」口径推进提成（4 档 0.001），`Applicable_Scope` 注记「不适用D-006消耗分奖金范围」成立（business_rules.md §2.5/§5 第5条已关闭）。
12. 【待 HR 复核（D-017，2026-08-18）】广告投放提成是否应为 GSV 口径——PO 2026-08-17 口述将与 HR 确认；确认前按「投放账户广告消耗」口径执行不更改（business_rules.md §5 第6条）。

## 9. 扩展性说明

- 更多部门：Organization 树形自关联 + 生效区间，新增部门不改结构。
- 更多绩效模型：Metric / Commission_Tier 以 Rule_Version 区分版本，新绩效模型 = 新规则版本记录，旧版本归档可回溯；Scoring_Rule_Payload 容器容纳新评分类型。
- 更多数据来源：Actual.Source_Type 与 Import_Batch.Batch_Type 枚举可扩展；新平台数据 = 新 Source_Type + 新导入批次类型，不改表结构。
- 更细期间粒度：Period 当前为月；如需周/日粒度，经变更流程扩展 Period 格式约束。

## 10. 与审计报告 §5.1 缺表清单对照

| 审计缺表项 | 本模型承载 |
|---|---|
| 缺独立 Channel 维度表 | Channel（§4.5） |
| 缺独立 Position 主数据表 | Position（§4.3） |
| 缺标准化 Metric 表 | Metric（§5.1） |
| 缺标准化 Target 长表 | Target（§5.2） |
| 缺标准化 Actual 长表 | Actual（§5.3） |
| 缺标准化 Performance_Result 长表 | Performance_Result（§5.4） |
| 缺导入错误日志表和计算批次表 | Error_Log（§6.3）+ Import_Batch（§6.1，Batch_Type=CALC 承载计算批次） |

另：Employee / Organization / Project / Project_Member / Commission_Tier 对应审计「缺字段、口径不符」项的结构重建；Validation_Rule 承载 §5.2 缺字段类别的校验落地。14 张表与缺表清单一一对应，无遗漏。
