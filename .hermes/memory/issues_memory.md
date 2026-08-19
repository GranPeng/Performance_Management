# Issues Memory

## T12a（2026-08-17）计算链独立验证与 LIVE 差异闭环

- Q-T12A-01：已关闭。`scripts/verify_calculation_chain.py` 以 V04 JSON 独立重算 161 条 Performance_Result；最终 161 条一致、0 差异、幂等读取稳定。机器可读证据：`data/output/T12a计算链独立校验报告.json`；可读报告：`docs/计算链验证报告.md`。
- Q-T12A-03 / LIVE-003：已关闭。ACT000013、ACT000022、ACT000031 的 V04 与 Base 正确预期均为 60 分；旧 T9a 预期 80 分源于生成器复用通用中档逻辑。生成器已按 LIVE-003 特例刷新本地预期清单。
- Q-T12A-04 / LIVE 梯度：已关闭。经 PO 书面确认并完成影响评估后，Commission_Tier 的 CT-V04-IE-LIVE-001..004 已由错移下限 60/80/100/150 修复为 V04 的 0/60/80/100，Score_Upper 补齐 60/80/100/150。变更前后证据与可逆回滚步骤：`data/output/T12a_LIVE梯度影响评估.json`；Change ID=CHG-T12A-001。
- D-010【已修订为 D-010-R1/R2，2026-08-17】：旧口径「豁免得分强制100、加权为0、按梯度比例提成」已废弃。当前仅抖音兴趣电商运营岗的项目运行<90天豁免行，提成=当前基数0.003×达成GSV，跳过梯度/考核系数；评分与加权仍按正常 V04 计算且不影响该提成。T14 使用 ACTUAL/SIMULATED 批次验证：运行44天、基数100、比例0.003、金额0.3>0、评分100/加权30，见 `data/output/T14_D010非零比例豁免执行结果.json`，回滚清单同名。教训：测试必须以非零金额覆盖分支；初始参数与事后修正不得混为同一计划，保留不可变初始证据并交付最终参数快照；来源布尔值可能以字符串读回，校验器必须归一化。D-010-R2 后续要求提成基数和豁免适用范围岗位绑定、可配置，禁止把0.003或单一岗位写死进通用公式。
- D-010-R2 配置化实施（2026-08-17，t_4cff8827 / CHG-T15B-001）：Base `Commission_Tier.Base_Rate` 已回填运营/高级主管14条为0.003；`Exemption_Scope` 已建并种子EXS000001=POS000013×运营×抖音×90；`Performance_Result.Exemption_Scope_ID` 已建，`Is_Exempt`公式改为读取命中范围行的`Max_Project_Run_Days`，不再硬编码90。T14模拟行已关联EXS000001并实测44<90、Base=100、Ratio=0.003、Amount=0.3。`t11c_generate_results.py`正常运营梯度改读`Base_Rate×Coefficient`，配置缺失抛错而不回退常量。限制：现有112条模拟Actual除T14外没有Channel_ID、181结果大多无Project_ID，无法为历史模拟行自动匹配范围；正式接入必须以Actual.Channel_ID或Project_Member的有效渠道关系匹配，缺渠道视为不豁免。

## T16（2026-08-17）验证器配置化与文档同步

- Q-T15-02/Q-T15-03：Base 已完成 `Base_Rate` 配置化后，验证器和验证报告若仍保留比例字面量或旧行数，会造成「实现已变、验证/文档未变」的假性通过。修复原则：验证预期必须从 `Commission_Tier.Base_Rate` 读取；仅用于验证的 `--base-rate` 覆盖值不得写入 Base；配置缺失或同岗位 Active 梯度基数不一致必须失败并写错误日志，禁止回退默认常量。
- Q-T15-04（文档）：规则文档应将已执行且可回滚的 LIVE 梯度边界修复与仍待 PO 确认的直播中控金额公式分开标注。不可因边界已对齐而擅自补全「绩效工资比例」与「0.1%/中控人数」的合成规则。
  - **已关闭 2026-08-18 / D-013**：PO 已拍板直播中控收入 = 绩效工资×档位百分比（80%/90%/100%/110%）＋ 渠道GSV×0.001÷中控人数；T17 已落文 business_rules.md「直播中控收入规则」章。梯度边界（CHG-T12A-001）与金额公式现均已有正式依据，文档标记语义由「待PO」转为「复合表达式无法单值结构化」（FLAG-L3 保留为技术标记）。

## T20（2026-08-18）CHG-T18-001/002 Base 结构落地

- Q-T15r-01：已关闭。正式 Base `FCxObLU6yao5jgsciZfcWHKwnjh` 已仅新增 Employee.Perf_Salary / Responsible_Channel_IDs（多值 link→Channel）、Performance_Result.Perf_Salary_Snapshot、Actual.Group_ID / Material_Type / Owner_Employee_ID / Material_First_Run_Date、Project_Member.Group_ID，以及新表 Project_Group（`tblU6US76mSPKhCD`，GRP 主键）。所有字段描述均标注 D-013/D-014/D-015.3/D-016 与 CHG-T18-001/002 的目的、来源、消费者和生命周期；小组维度仍为仅建模，禁止在 PO 拍板前用于核算。
- 验证：字段总数实测 Employee 18、Performance_Result 41、Actual 24、Project_Member 14、Project_Group 6；Performance_Result record-list 仍为181条。多值 link 用 EMP000001 临时写入两个 Channel 关联并读回确认两个 record id，随后清空字段，未保留测试数据。
