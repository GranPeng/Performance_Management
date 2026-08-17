# Architecture Memory（所有 Agent 可读，仅 system_architect 可写）

## ADR-001：技术路线
**决策**：Excel → Agent ETL → 飞书 Base
**原因**：避免前期开发 Web 系统，用低代码承载计算与展示
**影响**：所有数据必须经过 Canonical Schema，禁止业务表直连飞书
**风险**：飞书 Base 公式能力上限；数据量大时需评估迁移路径

## ADR-002：Base 现状不作为正式绩效核算库
**决策**：将 Base「组织信息库」当前 20 张表判定为原型参考库；正式绩效核算库必须先按 Canonical Data Model 重建主数据、指标、目标、实际值和结果表，再迁移或重写现有公式链路。
**原因**：Base 预算目标只覆盖单月、4 个项目、3 类指标，未对齐 V60 的 9 渠道 × 12 月 × 57 项目；绩效框架为 75 条而 V04 为 45 条；提成梯度为 81 条而 V04 为 42 条；当前链路普遍使用姓名、部门名、岗位名、项目名关联，且缺少 Identity / Source / Timestamp / Status。
**影响**：后续不能只在现有 Base 上补字段或补公式；需要先冻结 Employee / Organization / Position / Project / Channel / Metric / Target / Actual / Performance_Result 及 ID 体系，再按 V04/V60 迁移权威数据。现有表可作为字段参考和历史原型参考。
**风险**：业务侧可能已在当前 Base 维护单月数据；旧表被公式和视图引用，直接删除会破坏现有原型，应先建新模型、切换验证、再只读归档。

## ADR-003：Canonical 数据模型冻结（14 实体 + ID 体系）
**决策**：正式库按 11 核心实体（Employee / Organization / Position / Project / Channel / Project_Member / Metric / Target / Actual / Performance_Result / Commission_Tier）+ 3 支撑表（Import_Batch / Validation_Rule / Error_Log）重建，详见 `docs/data_model.md`（状态 FROZEN-PENDING，PO 确认后转 FROZEN）。ID 统一为「前缀+6 位顺序号」（EMP/ORG/POS/PROJ/CH/PM/MET/TGT/ACT/RST/CT/IB/VR/ERR），各实体号段独立、终身不变、不回收复用。每表必备 Identity/Source/Timestamp/Status 四要素；一切关联用 ID，禁用自然语言名称。V04 评分规则以「原文文本 + 结构化容器（Scoring_Rule_Payload）」承载，模型层不写业务公式；「不封顶」用 Upper_Is_Open 布尔显式表达，禁用魔法数值。D-005~D-007 口径映射由 Metric.Budget_Field_Ref / Target_Source_Type / Commission_Tier.Applicable_Scope 承载；D-008 花名册模拟数据由 Employee.Data_Origin 标记，HR 最终版在原 ID 上切换。
**原因**：当前 Base 普遍用姓名/部门名/岗位名关联且缺四要素（审计报告 §5），继续补丁式修复会把错误口径固化为系统规则；先冻结模型是全部后续迁移与公式重写的前提（修复建议 P0-1）。
**影响**：后续所有迁移（V60→Target 6,156 值、V04→Metric 45 项/梯度 42 条）、主数据建设、Actual/Result 链路重写必须严格按本模型执行；模型冻结后变更须走规则 §17 变更流程。
**风险**：① 8 项业务歧义列入待确认清单（data_model.md §8），确认前相关字段只存原文不计算；② 非 KPI 预算项目以 Budget_Item_Name+V60_Source_Row 承载，未来可能需升级独立实体；③ 模型冻结可能暴露 V04/V60 未覆盖场景，须靠变更流程而非绕过模型解决。

**补充（2026-08-14，D-009）**：D-009 五项口径已落入 data_model.md——§4.6 Project_Member 数据源=在线维护「在职人员对照项目」、§5.3 Actual.Source_Type 注明 90 天归因=视频管理系统自动下载（PLATFORM_IMPORT）、§5.4 双部分结构注明客服奖惩走 Manual_Score、§5.5 注明超梯度上限按最高档兜底（与 Upper_Is_Open 区分）、§7 对照表追加 D-009 行；§8 待确认清单第 2/5/6/7 条关闭、第 3 条部分关闭，模型字段结构零改动。

## ADR-004：正式库 14 表落地（T5 建表）
**决策**：2026-08-14 在 Base「组织信息库」（FCxObLU6yao5jgsciZfcWHKwnjh）内按 FROZEN data_model.md v1.0 新建 14 张英文名正式表（Employee / Organization / Position / Project / Channel / Project_Member / Metric / Target / Actual / Performance_Result / Commission_Tier / Import_Batch / Validation_Rule / Error_Log），仅结构字段、空表交付（records=0）。旧 20 张中文原型表原样只读保留，未修改/删除；Base 现共 34 张表。
**原因**：ADR-002/003 要求正式绩效核算库按 Canonical Model 重建，先建结构再迁移数据。
**影响**：
- table_id 清单与字段明细见 `docs/Base正式库建表记录.md`（T5 交付物）。
- 字段类型适配：TEXT→text；TEXT→实体→关联字段（link）指向目标表；NUMBER/INTEGER→number（INTEGER precision=0）；BOOL→checkbox（Is_V60_Authoritative/Is_Primary/Score_Cap_Is_Open/Upper_Is_Open）；DATE→datetime(yyyy-MM-dd)；DATETIME→datetime(yyyy-MM-dd HH:mm)；TEXT(YYYY-MM)/TEXT(JSON)→text。
- 自关联字段（Organization.Parent_Org_ID、Employee.Direct_Manager_ID）建表时目标表未存在，采用建表后补建完成。
- 字段级必填语义：飞书字段无必填开关，已在 description 标注「必填 ·/可选 ·」，运行期必填约束由 Validation_Rule 表承载。
- 主字段均为 `<实体>_ID`（text），满足 ID 关联铁律。
**风险**：下一阶段（T6+ 数据迁移）必须先注册 Validation_Rule 必填/ID 存在性规则，再按 Import_Batch 批次写入；模型 §5.2/§5.3 条件必填（Metric_ID 与 Budget_Item_Name 二选一、Actual 四类主体至少一类）由校验规则承载。

## T9b 记录：Performance_Result V04 计算链公式落地（2026-08-17，feishu-builder 执行）
- **公式字段**（Performance_Result，tbl6tFtVKExFUTWo）：Achievement_Rate / Auto_Score / Final_Score / Weight（formula）+ 辅助公式 Weighted_Score / Monthly_Total / Commission_Tier_Level；Weight 用 `FIRST([Metric_ID].[Weight])` lookup（任务 Output 要求），注意模型 Weight 原设计为「计算时快照」，当前 lookup 实现与快照语义略有差异，Rule_Version 固定 V04 下等价，改版需评审。
- **评分参数快照**：新增辅助列 Rate_T1~T3 / Score_T1~T3 / Score_Cap / Score_Floor / Deduct_Per / Target_Value_Snapshot，从 V04 原文转写填充（Metric.Score_Cap_Value 等结构化容器仍为空，BA 未填充，见 docs/计算链公式说明.md L2）。
- **5 类模板**：达成率/进度型（IFS + MIN(rate×100, cap) 封顶）、次数阈值型（阈值分档）、扣分制（MAX(100−n×5, 0)）、定性等级型/奖惩制（Auto_Score 留空，Manual_Score 人工录入，D-009.3 双部分）。
- **提成梯度匹配**：Commission_Tier_Level 公式按 Position_ID + Score_Lower ≤ Monthly_Total 取最高档（SORTBY desc + FIRST），天然覆盖 D-009.5 超上限按最高档；Upper_Is_Open 由 FILTER 条件涵盖。
- **验证**：161 条模拟结果（Batch IB-T9B-CALC-20260817-01，RST000001~161），93 条需 Actual 中 90 条 Auto_Score 与 T9a 预期一致；3 条 LIVE-003 差异 = T9a 模拟简化（80 分）vs V04 原文（60 分），公式按原文实现（L1）。
- **已知限制（报 PO）**：L1 T9a LIVE-003 档位差异；L2 Metric 分档参数未结构化（BA 待填）；L3 Commission_Tier LIVE 岗位梯度边界疑似 T6 迁移错位（lower=60/80/100/150 vs 原文 0/60/80/100），直播中控 42 条总分 20~38 无法命中；L4 客服岗位无分数梯度（人工奖惩，None 预期）；L5 定性/奖惩 68 条待 Manual_Score 录入后总分才完整。
- **Base 公式能力经验**：BLANK() 在运行时会使公式整体返回空（创建成功但计算失败），留空需用 `""` 或 IF(cond, val) 省略 false 分支（返回 false）；FIRST(link 字段访问) 对空 link 会出错，需 ISBLANK([link]) 分支保护。

## ADR-005：Performance_Result 豁免与提成字段补丁（T11a / CHG-T11A-001，2026-08-17）
**决策**：Performance_Result（tbl6tFtVKExFUTWo）新增 7 个可选字段：Project_ID（link→Project）/ Project_Run_Days（formula）/ Is_Exempt（formula）/ Commission_Base_Type（text）/ Commission_Base / Commission_Ratio / Commission_Amount（number）。运行天数以 **Period 对应自然月最后一日**为基准日（DAYS(EOMONTH(TODATE([Period]&"-01"),0), FIRST([Project_ID].[Start_Date]))），不用 TODAY()；Is_Exempt = 运行天数<90（阈值源自 V04 新项目免责期，Q-10-01），仅时间资格标记，×0.8 免责提成仍 HR 人工（D-009.4 / 2026-08-14）。提成四字段为纯容器，比例/映射/金额公式属 T11b BA 职责。提成四字段粒度为人员×期间，冗余在每行（同 Monthly_Total 模式），结算侧按 Employee_ID+Period 去重读取。
**原因**：QA 阻断项 Q-10-01（新项目<90 天豁免无法计算）与 Q-10-02（系统只算到梯度档位、无提成金额产出）的模型层缺口；落地 D-009（2026-08-17）提成基数口径（运营=渠道 GSV / 内容部=个人消耗 / 主播=个人营收）。模型 FROZEN 后按规则 §17 走变更流程，Change ID=CHG-T11A-001。
**影响**：纯新增可选字段，既有 161 条结果与全部既有公式不受影响（已实测验证）；Project_Run_Days / Is_Exempt 公式三条路径（无关联 / Start_Date 空 / 正常计算 91 天→false、46 天→true）经临时表全路径验证通过，测试数据已清理。
**风险**：① **Project.Start_Date 4/4 全空**（T8a 迁移时未携带），当前 Is_Exempt 全部留空，需业务在线维护补齐 Start_Date 后公式自动生效，禁止伪造日期（已在 Handoff 标注）；② 一人多项目时 Project_ID 归属口径（默认 Is_Primary）待 BA 确认；③ Commission_Amount 公式未落（T11b），Q-10-02 只解除模型层阻断，金额产出待 T11b 完成。

## T11c 记录：幂等改造与豁免/提成公式落地（2026-08-17，feishu-builder 执行）
- **幂等生成（Q-10-03）**：新脚本 `scripts/t11c_generate_results.py` 按业务键 `Employee_ID+Metric_ID+Period` upsert（已存在 batch-update 保留 Result_ID，缺失才 create），Import_Batch 按 Batch_ID 幂等复用；连续 3 次执行均 created=0/updated=161，Performance_Result 行数不变、Monthly_Total 零差异。T9b 脚本保留为历史产物，当前生成入口改为 T11c。
- **豁免分支（Q-10-01）**：`Auto_Score` 前置 `IF([Is_Exempt]=TRUE(),100,...)`；`Weighted_Score` 改 `IF([Is_Exempt]=TRUE(),0,Weight×Final_Score)`，豁免行贡献 0 → Monthly_Total 自动不含豁免行。端到端验证（临时 SIMULATED 项目 77 天挂 RST000124）：Is_Exempt=true / Auto_Score=100 / Final_Score=100 / Weighted_Score=0 / Monthly_Total 不变（48），验证后已清理。
- **提成金额（Q-10-02）**：`Commission_Base_Type/Base/Ratio` 为存储快照由脚本按 D-009 写入（运营=GSV、主播=个人营收、内容部=个人消耗、广告=投放消耗、直播中控/客服=不适用）；Base 取岗位基数指标 Actual_Value，Ratio 按 Monthly_Total 对照 Commission_Tier 取档（运营族=0.003×Coefficient、其余=Ratio_Value）；`Commission_Amount` 改 formula = Base×Ratio。验证：Ratio 107/107、Amount 92/92 手工复算一致。
- **关键能力约束（实测）**：Base 公式 FILTER 条件内**不支持**链式访问 link 目标字段（`CurrentValue.[Metric_ID].[Metric_ID]` 被拒为 Bitable_Formula_InvalidReferenced），因此 Commission_Base 无法公式化，只能走「存储快照 + 脚本按 D-009 写入」；这与 data_model 生命周期「随批次固定/重算整批重出」一致。
- **待 PO 边界**：T11C-L1 豁免行提成处理 V04 未规定（当前 Amount 公式仍按 Base×Ratio 产出）；T11C-L2 广告投放/摄影师 Commission_Base 在 T9a 模拟无对应金额指标留空；既有 T9b L1-L5 不变。

