# Business Memory（business_analyst / finance_controller 可写）

## KPI 定义登记

- 2026-08-14 / T1 只读提取：V04 共9个岗位工作表、45项 KPI；每条明细、源单元格和公式已固化于 `data/output/绩效框架结构化规则.json`。
- 最终得分的源表通用结构为“指标权重 × 完成结果”，总分为各项最终得分之和；各 KPI 的评分阈值彼此独立，禁止跨岗位套用。
- 制作部消耗相关指标的取值范围为上传时间90天内素材的上月整月消耗，数据源为云视频管家。

## 封顶/保底规则

- 达成率/进度型 KPI 的封顶、保底以对应源单元格的评分标准为准；常见的150分、120分、110分和1.5封顶系数不可泛化。
- 多个提成表最高仅列至150分，≥150分的处理方式未在源文件明确，已列为待确认事项。

## 部门差异化规则

- 兴趣电商高级主管的新项目机制及免责提成仅见于该岗位源表；不得外推到其他岗位。
- 客服岗位采用奖励/处罚条件并列描述，源表未给出金额、次数与总分的统一换算公式。

## 争议与待确认

- 广告投放 KPI“团队ROI签收目标达成率”的末档文字存在重叠；直播中控提成表列头与数据列视觉错位。详见结构化规则JSON的 `disputes_and_open_items`；未对原文作修正。

## 提成计算规则（T11b 落文，2026-08-17）

- D-009 提成基数口径 + V04 42 条梯度已整合入 `docs/business_rules.md`「提成计算规则」章节；Commission_Amount = Commission_Base × Commission_Ratio。
- 运营/高级主管提成比例 = 固定提成基数 0.003（运营 K12 / 高级主管 M12）× 档位系数；主播/广告投放/制作部取 Ratio_Value 直接数值；直播中控（绩效工资×80%~110% + 0.1%/中控人数）与客服（人工录入）不适用基数×比例公式。
- 待 PO 确认 6 项（business_rules.md §5）：直播中控梯度边界错位（T9b L3）、直播中控金额口径、无梯度匹配兜底、新项目豁免得分100不参与加权时提成处理、多人共用基数分摊、广告投放消耗与 D-006 范围关系。
- 核对：`scripts/t11b_verify_tiers.py`（V04 JSON 逐条，OK=34/FLAG-L3=4/BY-DESIGN=4）、`scripts/t11b_verify_doc_tables.py`（文档表 vs Commission_Tier 42 条 0 问题）。

## D-010-R2 豁免提成基数可配置化（2026-08-17，BA 设计交付）

- 决策：0.003 不是规则常量（仅运营岗当前比例基数）；豁免适用范围可扩展（不得写死单一岗位）。设计规格：`docs/D010-R2_豁免提成基数可配置化规格.md`；机器可读：`data/output/D010-R2_提成配置化规格.json`；模型变更 CHG-D010-R2-001（data_model.md §5.4/§5.5/§5.6）。
- 配置载体：`Commission_Tier.Base_Rate`（岗位族固定基数，当前 0.003，改配置即生效不碰公式）；`Exemption_Scope` 表（适用范围=岗位/岗位族×渠道×阈值，新增范围=新增行，EXS000001=POS000013×抖音×90）；`Performance_Result.Exemption_Scope_ID`（命中记录，审计锚点）。
- 豁免提成 = Base_Rate（配置）× 达成GSV，跳过梯度/考核系数；评分照常（Auto_Score/Weighted_Score 正常）。Base 公式 Commission_Amount 表达式不改。
- Base 既有 CHG-T15B-001 遗留结构（Exemption_Scope 空表/Base_Rate 空字段/Exemption_Scope_ID 关联）已正式入模型，勿重复建表。
- 待 PO 确认：Position_Family 值域与归属、多人共用 GSV 豁免全额口径、Max_Project_Run_Days 是否随版本区分。
