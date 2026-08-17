# Base 正式库建表记录（T5）

> 状态：2026-08-14 完成（Kanban T5, task t_a876a68c）
> 依据：docs/data_model.md（FROZEN v1.0）· 决策日志 D-001~D-009 · .hermes/PROJECT_RULES.md
> Base：组织信息库 https://jv8fym591u8.feishu.cn/base/FCxObLU6yao5jgsciZfcWHKwnjh
> 身份：lark-cli --as user

## 一、交付说明

1. 在 Base「组织信息库」内新建 **14 张 Canonical 正式表**（英文表名，与旧 20 张中文原型表明确区分），仅结构与字段，**未写入任何业务数据**（全部 records=0，空表交付）。
2. 旧 20 张表**原样保留、只读未动**（未修改、未删除、未加字段）。Base 当前共 34 张表。
3. 每张表严格按 data_model.md 字段名 / 类型 / 必填逐字段建立；所有模型关联字段（TEXT→实体）落为飞书**关联字段（link）**指向目标表；BOOL 落为**复选框（checkbox）**；DATE/DATETIME 落为**日期（datetime）**；INTEGER 落为**数字（precision=0）**；TEXT(JSON)/TEXT(YYYY-MM) 保持文本。
4. 每张表均含 §1.1 通用治理字段：`<实体>_ID`（主键，text，主字段）/ Source / Create_Time / Update_Time / Status。
5. 字段级「必填」语义：飞书字段本身无必填开关，已在字段 description 标注「必填 · / 可选 ·」；运行期必填约束由 Validation_Rule 表承载（§6.2 校验类型=必填）。
6. 自关联字段（Organization.Parent_Org_ID、Employee.Direct_Manager_ID）因建表时目标表尚未存在，采用「建表后补建」完成，已核验指向自身表。

## 二、表清单与字段明细

### Employee（人员主数据）— tblc59aB4EnSxkQv
模型依据：data_model.md §4.1 · 表内字段数：15

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Org_ID | 关联 → tblc6rU0d2bHMVnZ | link | 必填 · 归属部门 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Employee_ID | 文本 | text | 必填 · 主键，EMP 号段 |
| Direct_Manager_ID | 关联 → tblc59aB4EnSxkQv | link | 可选 · 直属主管（负责人打分路由） |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Data_Origin | 文本 | text | 必填 · ROSTER_MOCK / HR_OFFICIAL / MANUAL（D-008） |
| Import_Batch_ID | 关联 → tblHV3JoVR9AEETw | link | 必填 · 来源批次 |
| Leave_Date | 日期时间 | datetime | 可选 · 离职日期 |
| Position_ID | 关联 → tbldzvsg9Op6pK29 | link | 必填 · 岗位 |
| Name | 文本 | text | 必填 · 人读展示，禁止作关联键 |
| Employment_Status | 文本 | text | 必填 · 在职/离职/停用 |
| Hire_Date | 日期时间 | datetime | 必填 · 入职日期 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Perf_Participate_Status | 文本 | text | 必填 · 是否参与绩效考核（待确认/确认参与/确认不参与） |

### Organization（部门树）— tblc6rU0d2bHMVnZ
模型依据：data_model.md §4.2 · 表内字段数：10

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Effective_Start | 日期时间 | datetime | 必填 · 生效开始日期 |
| Effective_End | 日期时间 | datetime | 可选 · 生效结束日期，空=当前有效 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Parent_Org_ID | 关联 → tblc6rU0d2bHMVnZ | link | 可选 · 上级部门（树形自关联） |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Org_ID | 文本 | text | 必填 · 主键，ORG 号段 |
| Org_Level | 数字 | number | 必填 · 层级深度 |
| Org_Name | 文本 | text | 必填 · 部门名称，人读展示，禁止作关联键 |

### Position（岗位主数据）— tbldzvsg9Op6pK29
模型依据：data_model.md §4.3 · 表内字段数：11

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Position_ID | 文本 | text | 必填 · 主键，POS 号段 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Org_ID | 关联 → tblc6rU0d2bHMVnZ | link | 必填 · 岗位所属部门 |
| Job_Family | 文本 | text | 可选 · 序列 |
| Version | 文本 | text | 必填 · 岗位定义版本（当前 V04） |
| Position_Name | 文本 | text | 必填 · 标准岗位名（以 V04 为准） |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Position_Alias | 文本 | text | 可选 · 别名集合，多值顿号分隔 |
| Grade | 文本 | text | 可选 · 职级 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |

### Project（项目主数据）— tbl1GO2vR9ZAqPbr
模型依据：data_model.md §4.4 · 表内字段数：9

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Brand | 文本 | text | 可选 · 品牌维度 |
| Project_ID | 文本 | text | 必填 · 主键，PROJ 号段 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Start_Date | 日期时间 | datetime | 可选 · 项目开始日期 |
| End_Date | 日期时间 | datetime | 可选 · 项目结束日期 |
| Project_Name | 文本 | text | 必填 · 项目名称，人读展示 |

### Channel（渠道主数据）— tblqOGJknsD2H3bt
模型依据：data_model.md §4.5 · 表内字段数：8

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Is_V60_Authoritative | 复选框（BOOL 适配） | checkbox | 必填 · 是否 V60 权威渠道（BOOL→复选框） |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Channel_Alias | 文本 | text | 可选 · 写法别名，多值顿号分隔 |
| Channel_ID | 文本 | text | 必填 · 主键，CH 号段 |
| Channel_Name | 文本 | text | 必填 · 标准渠道名（以 V60 为准） |

### Project_Member（项目成员分摊）— tblcUUz0oq9MxNLu
模型依据：data_model.md §4.6 · 表内字段数：12

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Project_ID | 关联 → tbl1GO2vR9ZAqPbr | link | 必填 · 项目关联 |
| Effective_End | 日期时间 | datetime | 可选 · 生效结束，空=当前有效 |
| Is_Primary | 复选框（BOOL 适配） | checkbox | 必填 · 主项目标识（BOOL→复选框） |
| Employee_ID | 关联 → tblc59aB4EnSxkQv | link | 必填 · 人员关联 |
| Effective_Start | 日期时间 | datetime | 必填 · 生效开始 |
| Project_Member_ID | 文本 | text | 必填 · 主键，PM 号段 |
| Allocation_Ratio | 数字 | number | 可选 · 分摊比例 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Channel_ID | 关联 → tblqOGJknsD2H3bt | link | 可选 · 渠道粒度；空=整项目 |

### Metric（绩效指标定义）— tbldKtdIVv8nnTyX
模型依据：data_model.md §5.1 · 表内字段数：29

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Calc_Rule_Text | 文本 | text | 可选 · 计算口径文本原文（仅存档展示） |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Unit | 文本 | text | 可选 · 单位（%/、/万元等） |
| Score_Cap_Is_Open | 复选框（BOOL 适配） | checkbox | 必填 · 不封顶显式标记（BOOL→复选框） |
| Scoring_Type | 文本 | text | 必填 · 评分类型枚举（五类） |
| Metric_Number | 文本 | text | 必填 · V04 源编号 |
| Metric_ID | 文本 | text | 必填 · 主键，MET 号段 |
| Reward_Condition_Text | 文本 | text | 可选 · 奖励条件原文 |
| Source_Sheet | 文本 | text | 必填 · V04 源工作表 |
| Source_Cell | 文本 | text | 必填 · V04 源单元格 |
| Position_ID | 关联 → tbldzvsg9Op6pK29 | link | 必填 · 岗位关联 |
| Penalty_Condition_Text | 文本 | text | 可选 · 处罚条件原文 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Scoring_Standard_Text | 文本 | text | 必填 · 评分标准原文 |
| Evaluation_Period_Text | 文本 | text | 必填 · 评价周期原文 |
| Metric_Name | 文本 | text | 必填 · 指标名称 |
| Target_Source_Type | 文本 | text | 必填 · 目标来源策略枚举（D-007） |
| Budget_Field_Ref | 文本 | text | 可选 · V60 预算字段映射（D-005/D-006） |
| Rule_Version | 文本 | text | 必填 · 规则版本（当前 V04） |
| Target_Description | 文本 | text | 可选 · 目标描述原文 |
| Dimension | 文本 | text | 必填 · 评价维度：组织/岗位/个人指标 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Score_Cap_Value | 数字 | number | 可选 · 封顶值结构化 |
| Data_Source_Text | 文本 | text | 必填 · V04 数据来源原文 |
| Source_SHA256 | 文本 | text | 必填 · 源文件哈希（V04: 5342d3dd…3250） |
| Scoring_Rule_Payload | 文本 | text | 可选 · 分档结构化容器 TEXT(JSON)，BA 填充 |
| Weight | 数字 | number | 必填 · 指标权重 |
| Score_Floor_Value | 数字 | number | 可选 · 保底值结构化 |

### Target（目标值长表）— tblydZkf17kmzrO0
模型依据：data_model.md §5.2 · 表内字段数：22

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Source_Cell | 文本 | text | 必填 · 源单元格 |
| Source_Cached_Value | 数字 | number | 可选 · 源缓存值（对账） |
| Target_ID | 文本 | text | 必填 · 主键，TGT 号段 |
| Import_Batch_ID | 关联 → tblHV3JoVR9AEETw | link | 必填 · 批次追溯 |
| Channel_ID | 关联 → tblqOGJknsD2H3bt | link | 可选 · 渠道维度（V60 渠道级目标必填） |
| Source_File | 文本 | text | 必填 · 源文件 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Target_Value | 数字 | number | 必填 · 目标值 |
| Unit | 文本 | text | 必填 · 单位（万元/比例） |
| Period | 文本 | text | 必填 · 期间 YYYY-MM（自然月） |
| Metric_ID | 关联 → tbldKtdIVv8nnTyX | link | 可选 · 绩效目标标识；与 Budget_Item_Name 二选一 |
| Project_ID | 关联 → tbl1GO2vR9ZAqPbr | link | 可选 · 项目归属 |
| Source_Sheet | 文本 | text | 必填 · 源工作表 |
| Source_Formula | 文本 | text | 可选 · 源单元格原公式存档（#REF! 原样保留） |
| Source_SHA256 | 文本 | text | 必填 · 源文件哈希（V60: 65d3c2a6…5943） |
| Org_ID | 关联 → tblc6rU0d2bHMVnZ | link | 可选 · 部门归属 |
| V60_Source_Row | 数字 | number | 可选 · V60 源行号 |
| Import_Status | 文本 | text | 必填 · 导入状态：成功/失败/待确认 |
| Budget_Item_Name | 文本 | text | 可选 · 非 KPI 预算项目标识；与 Metric_ID 二选一 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |

### Actual（实际达成长表）— tbli9VhcUFjVDeNd
模型依据：data_model.md §5.3 · 表内字段数：19

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Actual_ID | 文本 | text | 必填 · 主键，ACT 号段 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Collected_Time | 日期时间 | datetime | 必填 · 采集时间 |
| Metric_ID | 关联 → tbldKtdIVv8nnTyX | link | 必填 · 指标关联 |
| Unit | 文本 | text | 必填 · 单位 |
| Employee_ID | 关联 → tblc59aB4EnSxkQv | link | 可选 · 个人粒度实际值（四类主体至少一类） |
| Actual_Value | 数字 | number | 必填 · 实际值 |
| Channel_ID | 关联 → tblqOGJknsD2H3bt | link | 可选 · 渠道粒度实际值 |
| Validation_Status | 文本 | text | 必填 · 待校验/通过/驳回 |
| Import_Batch_ID | 关联 → tblHV3JoVR9AEETw | link | 必填 · 批次追溯 |
| Source_Ref | 文本 | text | 可选 · 来源说明（平台名/对话批次/备注） |
| Project_ID | 关联 → tbl1GO2vR9ZAqPbr | link | 可选 · 项目粒度实际值 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Org_ID | 关联 → tblc6rU0d2bHMVnZ | link | 可选 · 组织粒度实际值 |
| Collected_By | 关联 → tblc59aB4EnSxkQv | link | 必填 · 上传人/登记人 |
| Source_Type | 文本 | text | 必填 · MANUAL_REPORT/PLATFORM_IMPORT/MANUAL_ENTRY/AUTO_COMPUTE |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Period | 文本 | text | 必填 · 期间 YYYY-MM |

### Performance_Result（绩效结果长表）— tbl6tFtVKExFUTWo
模型依据：data_model.md §5.4 · 表内字段数：18

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Period | 文本 | text | 必填 · 期间 YYYY-MM |
| Achievement_Rate | 数字 | number | 可选 · 达成率（解释链环节） |
| Final_Score | 数字 | number | 必填 · 最终单项得分 |
| Review_Status | 文本 | text | 必填 · 待复核/已复核/已确认/有异议 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Rule_Version | 文本 | text | 必填 · 计算所用规则版本快照 |
| Target_ID | 关联 → tblydZkf17kmzrO0 | link | 可选 · 目标溯源（定性指标可空） |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Result_ID | 文本 | text | 必填 · 主键，RST 号段 |
| Calc_Batch_ID | 关联 → tblHV3JoVR9AEETw | link | 必填 · 计算批次（Batch_Type=CALC） |
| Employee_ID | 关联 → tblc59aB4EnSxkQv | link | 必填 · 人员关联 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Weight | 数字 | number | 必填 · 权重快照（防改版失真） |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Actual_ID | 关联 → tbli9VhcUFjVDeNd | link | 可选 · 实际值溯源（负责人打分可空） |
| Auto_Score | 数字 | number | 可选 · 自动计算单项得分 |
| Metric_ID | 关联 → tbldKtdIVv8nnTyX | link | 必填 · 指标关联 |
| Manual_Score | 数字 | number | 可选 · 负责人打分（客服奖惩走此字段，D-009.3） |

### Commission_Tier（提成梯度定义）— tblkZUoHYwBIvDYe
模型依据：data_model.md §5.5 · 表内字段数：21

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Commission_Tier_ID | 文本 | text | 必填 · 主键，CT 号段 |
| Metric_ID | 关联 → tbldKtdIVv8nnTyX | link | 可选 · 提成来源可关联指标时填写 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Upper_Is_Open | 复选框（BOOL 适配） | checkbox | 必填 · 不封顶开放上限显式语义（BOOL→复选框） |
| Ratio_Value | 数字 | number | 可选 · 纯数值比例结构化值（混合表达式为空） |
| Tier_Level | 数字 | number | 必填 · 档位序号 |
| Position_ID | 关联 → tbldzvsg9Op6pK29 | link | 必填 · 岗位关联 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Source_Sheet | 文本 | text | 必填 · V04 源工作表 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Source_Cell | 文本 | text | 必填 · V04 源单元格 |
| Ratio_Text | 文本 | text | 可选 · 提成比例原文（原样存档） |
| Rule_Version | 文本 | text | 必填 · 规则版本（当前 V04） |
| Score_Lower | 数字 | number | 必填 · 得分下限（含） |
| Applicable_Scope | 文本 | text | 可选 · 适用范围（D-006 消耗分奖金仅限抖音/视频号内容制作团队） |
| Commission_Source_Text | 文本 | text | 必填 · 提成来源原文 |
| Source_SHA256 | 文本 | text | 必填 · 源文件哈希 |
| Coefficient | 数字 | number | 可选 · 系数比例（L 列数值） |
| Score_Upper | 数字 | number | 可选 · 得分上限（不含）；不封顶为空 |
| Rule_Note | 文本 | text | 可选 · 规则说明原文 |

### Import_Batch（导入/计算批次）— tblHV3JoVR9AEETw
模型依据：data_model.md §6.1 · 表内字段数：14

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Fail_Count | 数字 | number | 必填 · 失败量 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Success_Count | 数字 | number | 必填 · 成功量 |
| Batch_Type | 文本 | text | 必填 · 批次类型：BUDGET/ACTUAL/EMPLOYEE/MASTER_DATA/CALC |
| Total_Count | 数字 | number | 必填 · 总量（如 V60=6156） |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Import_Time | 日期时间 | datetime | 必填 · 批次时间 |
| Operator | 文本 | text | 必填 · 操作者（人或 Agent 流程标识） |
| Batch_ID | 文本 | text | 必填 · 主键，IB 号段 |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Source_Type | 文本 | text | 必填 · 来源类型：Excel文件/对话上报/平台接口/计算引擎 |
| Source_File | 文本 | text | 可选 · 来源文件名 |
| Source_SHA256 | 文本 | text | 可选 · 来源文件哈希（D-001） |

### Validation_Rule（校验规则定义）— tblnc4m0jV47DKna
模型依据：data_model.md §6.2 · 表内字段数：9

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |
| Rule_ID | 文本 | text | 必填 · 主键，VR 号段 |
| Rule_Expression | 文本 | text | 必填 · 校验口径文本描述 |
| Target_Entity | 文本 | text | 必填 · 校验对象（14 实体之一） |
| Rule_Type | 文本 | text | 必填 · 必填/ID存在性/期间合法性/值类型/渠道映射/指标映射/数量对账 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Severity | 文本 | text | 必填 · BLOCKER / WARNING |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |

### Error_Log（错误日志）— tbl4ZpuuOxZacWgj
模型依据：data_model.md §6.3 · 表内字段数：13

| 字段 | 飞书类型 | 模型映射 | description |
|---|---|---|---|
| Batch_ID | 关联 → tblHV3JoVR9AEETw | link | 必填 · 归属批次 |
| Update_Time | 日期时间 | datetime | 必填 · 最近变更时间，每次更新刷新 |
| Handle_Time | 日期时间 | datetime | 可选 · 处理时间 |
| Object_Type | 文本 | text | 必填 · 出错对象类型 |
| Error_Type | 文本 | text | 必填 · 错误分类（对应 Rule_Type） |
| Process_Status | 文本 | text | 必填 · 待处理/处理中/已解决/已忽略 |
| Status | 文本 | text | 必填 · 生命周期状态：Active / Inactive / Archived |
| Error_Content | 文本 | text | 必填 · 错误详情 |
| Source | 文本 | text | 必填 · 数据来源追溯（治理四要素） |
| Handler | 文本 | text | 可选 · 处理人 |
| Error_ID | 文本 | text | 必填 · 主键，ERR 号段 |
| Object_ID | 文本 | text | 必填 · 出错对象 ID |
| Create_Time | 日期时间 | datetime | 必填 · 创建时间，写入后不变 |

## 三、与 FROZEN 模型的对照确认

| 检查项 | 结果 |
|---|---|
| 14 张表全部建成 | ✅ table_id 清单见上 |
| 字段名与模型零偏差 | ✅ 无缺失、无多余字段（脚本核验 ALL_OK） |
| 关联字段指向正确 | ✅ 所有 link 指向目标表（含 2 个自关联） |
| 旧 20 表未被改动 | ✅ 只读保留，未修改/删除 |
| 空表交付 | ✅ 14 张表 records=0 |
| 通用治理字段齐备 | ✅ 每表含 <实体>_ID + Source/Create_Time/Update_Time/Status |

## 四、字段类型适配映射（模型 → 飞书）

| 模型类型 | 飞书类型 | 说明 |
|---|---|---|
| TEXT | 文本 | 含 TEXT(YYYY-MM)、TEXT(JSON) |
| TEXT→实体 | 关联（link） | 指向目标表；Organization/Employee 自关联后补建 |
| NUMBER | 数字 | precision 按需；INTEGER→precision=0 |
| BOOL | 复选框（checkbox） | Is_V60_Authoritative / Is_Primary / Score_Cap_Is_Open / Upper_Is_Open |
| DATE | 日期时间（datetime yyyy-MM-dd） | Hire_Date / Leave_Date / Effective_* / Start_Date 等 |
| DATETIME | 日期时间（datetime yyyy-MM-dd HH:mm） | Create_Time / Update_Time / Collected_Time / Import_Time / Handle_Time |

## 五、后续提示

- 主字段均为 `<实体>_ID`（文本），满足 ID 关联铁律；名称类字段仅供人读展示。
- 模型 §5.2/§5.3 的「条件必填」（Metric_ID 与 Budget_Item_Name 二选一；Actual 四类主体至少一类）为业务约束，由 Validation_Rule 承载，本阶段仅结构落地。
- 下一阶段（T6+）迁移数据时：先注册 Validation_Rule 必填/ID 存在性规则，再按 Import_Batch 批次写入。

— feishu-builder (T5)