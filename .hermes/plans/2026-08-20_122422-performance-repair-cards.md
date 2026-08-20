# 绩效核算系统全量修复发卡计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 先修复绩效系统的员工-期间数据合同、Actual→计算闭环、提成聚合与服务端安全边界，再恢复前端功能开发；最后以 expand/contract 方式完成关联字段 jsonb→文本迁移。

**Architecture:** `performance_result` 的物理行粒度保持“员工 × 期间 × 指标”，不重写已验收的计算数据。新增/修正“员工 × 期间”的**读取聚合模型**，让列表、详情、Dashboard、结果书使用同一聚合规则。关联字段迁移采用新增文本列、双读/双写、回填核验、切换、观察期的渐进式方案；禁止原地把 jsonb 强转 text。

**Tech Stack:** 妙搭 full-stack、NestJS、Drizzle/PostgreSQL、React、Jest、妙搭 dev/online 环境、lark-cli、Chrome 线上验收。

---

## 0. 全局发卡纪律与固定门禁

### 当前任务处理

- `t_4500c139`（旧 P3c）保持 `blocked`；其工作区有未提交改动，**不得验收、不得发布、不得作为后续修复基线**。
- `t_10d771d7`（旧 P3d）保持 `todo`，不得因依赖自动流转；jsonb→文本迁移必须由本计划的 J 系列新卡替代。
- 新卡不得依赖旧 P3c/P3d。旧卡仅保留历史证据，待新链路全部验收后再归档。

### 每张实现卡的共同要求

1. 先读根目录 `AGENTS.md`、本计划、`全系统复核报告_20260820_V01_核心闭环与迁移风险.md`。
2. 每张卡只修改本卡明确列出的文件范围；不得顺手改相邻模块。
3. 先写能复现问题的 RED 测试，再写最小修复；禁止“测试先绿再补”。
4. 每卡必须分别执行：目标 Jest、全量 Jest、`npm run type:check`、`npm run lint`。
5. 涉及结果/金额的卡，必须使用外部独立基线（Base/Excel/Python 蓝本），不能以 SQL 自己写出的结果自证。
6. 发布卡之外禁止创建 release；online DDL/DML 必须有明确的上线授权。
7. 任何测试写入 online 的数据必须在同一验收步骤删除，且以 SQL 回读证明未留脏数据。

### 总体验收标准

- 结果列表：一行 = 一个员工 + 一个期间；不再把指标行当员工月度结果。
- 结果详情：显示该员工当期全部指标行，且月度总分 = 指标加权分之和（允许既定浮点容差）。
- 提成：一个员工每期间仅计算/汇总一次；Dashboard、结果书、详情口径一致。
- 新 Actual 从录入到 preview/run 的结果值变化可端到端验证。
- `calc/run` 有显式登录、角色授权、操作审计和并发保护。
- jsonb→文本迁移后，所有关联读取、写入、计算、规则、导出、页面与外部基线全部通过。

---

# Phase A：冻结工作区与固化回归契约

## 卡 A0：隔离旧 P3c 未提交改动，建立干净修复基线

**Owner:** `system-architect`

**Objective:** 保护旧 P3c 试算面板代码，但让后续 P0 修复基于干净的 `sprint/default` 工作树，杜绝夹带发布。

**Files:**
- 只操作 git 工作树/工作区元数据；不得修改业务源码。
- 输出：`org-performance-app/docs/修复基线与P3c隔离记录.md`

**Steps:**
1. 读取并完整保存当前 `git diff`、未跟踪文件清单及当前 HEAD。
2. 将 P3c 未提交改动隔离到单独 WIP worktree 或等效可恢复 patch；不创建 release。
3. 在干净 worktree 运行 `git status --short`，必须为空。
4. 对比 WIP 与干净 worktree，确认未修改 `schema.ts`、jsonb 关联合同或线上环境。

**Acceptance Criteria:**
- P3c 改动可恢复、不丢失；修复工作树 clean；无业务代码发布。
- 输出记录包含 commit 基线、隔离文件清单、恢复方式。

**Dependencies:** 无。

---

## 卡 A1：建立员工-期间读模型的失败回归测试

**Owner:** `qa-reviewer`

**Objective:** 把当前线上“重复员工、总分错误、详情无明细”的真实症状固化为服务层和页面合同测试。

**Files:**
- Create/Modify：`server/modules/performance/performance.service.spec.ts`（若不存在则新建）
- Modify：现有 performance fixture / shared API test fixture（仅测试数据）
- 不改业务实现。

**Steps:**
1. 构造同一员工同一期间至少 2 个指标行，且每行 `monthly_total` 均非空、单项 `final_score` 不同。
2. 断言当前 list 应返回 1 个员工-期间聚合条目；当前实现必须 RED。
3. 断言 detail 返回全部指标行，顶层月度总分等于 `Σ weighted_score`；当前实现必须 RED。
4. 断言相同月度提成在多指标行中不会被聚合为 N 倍。
5. 只提交测试，不修业务实现。

**Acceptance Criteria:**
- 测试红色且直接对应 P0-1/P0-2；不依赖在线库；可在本地稳定复现。

**Dependencies:** A0。

---

# Phase B：建立正确结果读模型与财务聚合口径

## 决策门 B-DEC：确认提成归属粒度

**Owner:** `performance-business-analyst`

**Objective:** 将当前已有模型/结果书规则转写为唯一可执行的提成归属合同，消除“指标行重复月度提成”歧义。

**Files:**
- Create：`org-performance-app/docs/提成归属与聚合合同.md`
- 可引用：`performance-system/docs/data_model.md`、历史结果书验证记录、Base 外部基线。

**必须回答：**
1. 提成金额是否为“员工 + 期间”唯一月度字段；
2. 多指标行上重复值是否只是快照；
3. Dashboard/结果书/详情的提成应取 `MAX`/`MIN`/代表行还是指标求和；
4. 同组多条提成值不一致时是阻断、告警还是按优先级取值。

**Acceptance Criteria:**
- 产出唯一、可测试的合同和例子；与 Excel/Base/Python 外部口径对照；PO 确认后才解锁 B1/B2。

**Dependencies:** A1。

**Human Gate:** 必须由 Product Owner 对提成归属结论确认。推荐结论：提成是“员工 + 期间”唯一月度字段，指标行仅保存重复快照；汇总使用一致性校验后的单值，禁止 `SUM`。

---

## 卡 B1：修复绩效结果列表与详情的员工-期间聚合 API

**Owner:** `automation-engineer`

**Objective:** 实现正确的员工月度绩效读取模型，不更改计算引擎写入行粒度。

**Files:**
- Modify：`server/modules/performance/performance.service.ts:35-230`
- Modify：`server/modules/performance/performance.controller.ts`
- Modify：`shared/api.interface.ts`
- Modify：`client/src/api/performance.ts`
- Modify：`client/src/pages/PerformanceResultsPage/PerformanceResultsPage.tsx`
- Modify：`client/src/pages/PerformanceResultsPage/ResultDetailSheet.tsx`
- Test：`server/modules/performance/performance.service.spec.ts`

**Implementation constraints:**
1. 列表按 `app_employee_id + app_period` 分组；聚合 ID 必须稳定且不依赖可变显示名。
2. 顶层字段命名明确：使用 `monthlyTotal` 表示月度总分；不得再把单项 `final_score` 标为“总得分”。
3. 详情按员工关联值 + 期间取全部指标行；删除 `monthly_total IS NULL` 作为明细判定。
4. 所有月度重复字段使用 B-DEC 的合同；发现同组不一致须可见、可测试，不能静默错误求和。
5. 保持筛选按员工、部门、岗位、期间、复核状态、档位的语义为聚合后记录。

**Verification:**
- A1 全部测试转绿；
- 新增 API 断言：2026-07 结果列表为 32 个员工-期间聚合项，而不是 161 指标行；
- Chrome 线上验收：默认列表无同员工同期间重复；抽屉出现完整指标明细；
- 与 Base/Excel 对照随机抽样至少 5 名员工的月度总分。

**Dependencies:** B-DEC。

---

## 卡 B2：统一 Dashboard 与结果书的月度提成聚合

**Owner:** `data-engineer`

**Objective:** 按 B-DEC 的提成归属合同修复总览 KPI、部门汇总、结果书员工汇总，杜绝指标行重复累计。

**Files:**
- Modify：`server/modules/dashboard/dashboard.service.ts`
- Modify：`server/modules/calc/result-book.ts`
- Modify：`server/modules/calc/result-book.spec.ts`
- Modify：Dashboard/结果书对应测试。

**Implementation constraints:**
1. 所有月度提成聚合必须按员工 + 期间去重；
2. 同组提成快照不一致时抛出业务可读异常或显式告警，不能静默 `SUM`；
3. 月度总分和提成总额采用同一聚合 CTE/共享 helper，避免页面与导出再次分叉；
4. 不改评分、档位、豁免计算规则。

**Verification:**
- 人工构造一员工 3 指标、同一月度提成快照的 fixture：总提成仅计 1 次；
- 结果书、Dashboard、B1 详情三方金额一致；
- 外部结果书基线对照通过。

**Dependencies:** B-DEC；可与 B1 并行实现，但必须在 Q0 一起集成验收。

---

# Phase C：Actual 写入到计算的闭环

## 卡 C1：定义 Actual→Performance_Result 归属与稳定标识合同

**Owner:** `system-architect`

**Objective:** 先定义实际值的主体验证、唯一匹配和稳定标识，避免“录入成功但不参与计算”。

**Files:**
- Create：`org-performance-app/docs/Actual到结果关联合同.md`
- Read：`server/modules/write/*`、`server/modules/calc/adapter.ts`、`schema.ts`
- 不改实现。

**必须明确：**
1. Actual 是直接指向一条 result，还是按 `(期间、指标、员工/组织/项目/渠道)` 自动唯一匹配；
2. 一个 Actual 是否允许扇出到多条 result；
3. 应使用 `base_record_id`、应用 UUID 还是新增稳定 text key；
4. 无匹配/多匹配时 API 的错误与人工处理路径；
5. 手工录入与导入数据的冲突优先级。

**Acceptance Criteria:**
- 合同带至少 6 个单值/组织/项目/渠道/无匹配/多匹配实例；PO 确认后才实施 C2。

**Dependencies:** A0。

**Human Gate:** 需要 PO 确认 Actual 自动匹配是否允许一对多扇出；若未确认，不得猜测实现。

---

## 卡 C2：实现 Actual 写入、关联与重算的原子闭环

**Owner:** `automation-engineer`

**Objective:** 让 `POST /api/actuals` 的数据在同一事务中拥有可计算的稳定关联，并可被 preview/run 读取。

**Files:**
- Modify：`server/modules/write/write.service.ts`
- Modify：`server/modules/write/sql-write.store.ts`
- Modify：`server/modules/calc/adapter.ts`（仅按 C1 合同所需）
- Modify：`server/modules/write/*.spec.ts`
- Create/Modify：calc integration test。

**Implementation constraints:**
1. 新增 Actual 后必须生成/取得 C1 定义的稳定链接标识；
2. 在一个事务中创建/更新 Actual 与对应 result 关联，失败则整体回滚；
3. 写前验证员工、期间、指标、主体粒度一致；
4. 幂等与后续 C3 并发设计兼容；
5. 禁止用 Base 同步、人工 SQL 或临时补丁作为正常链路。

**Verification:**
- RED：创建 Actual 后 preview 的实际值、达成率、分数均不变；
- GREEN：同一案例创建后上述字段按预期变化；
- online 冒烟只能使用明确标记测试数据，并在同一任务内删除、回读证明 0 脏数据；
- 外部 Python 蓝本校验该案例。

**Dependencies:** C1；B1（结果读取合同已稳定）。

---

## 卡 C3：加固 Actual 幂等与编号并发安全

**Owner:** `automation-engineer`

**Objective:** 消除 Actual 的先查后插竞态和 `MAX(ACT)+1` 编号竞态。

**Files:**
- Modify：`server/modules/write/sql-write.store.ts`
- Modify：`server/modules/write/write.service.ts`
- Modify：相应 schema/migration（仅 dev；若确需数据库约束）
- Test：write service / integration tests。

**Implementation constraints:**
1. 以 C1 合同定义业务幂等键或请求幂等键；
2. 使用数据库唯一约束与 `INSERT ... ON CONFLICT ... RETURNING`；
3. 展示编号使用数据库 sequence/identity 或不承担并发主键职责；
4. “同金额短时间报单不算重复”的既定业务口径必须保留：不能仅按金额误去重。

**Verification:**
- 并发至少 2 请求同一幂等键，只留一条；
- 不同业务语义但同金额的两条请求均可存在；
- 不产生编号冲突；全量 write tests 通过。

**Dependencies:** C2。

---

# Phase D：重算、复核与 API 安全边界

## 卡 D1：为重算接口添加登录、授权、操作审计与 CSRF 合同

**Owner:** `system-architect`

**Objective:** 以妙搭实际认证/角色 API 为准，设计 `calc/run` 的最小安全边界；不得凭印象使用 decorator 或 guard。

**Files:**
- Create：`org-performance-app/docs/重算授权与审计合同.md`
- Read：妙搭本地 skill/SDK、现有 `@NeedLogin()` 写接口、应用角色配置。

**Acceptance Criteria:**
- 查明实际可用的登录 decorator、userContext 形状、角色 guard、审计字段和 CSRF 机制；
- 设计“谁能重算、谁能导出、谁能复核”的权限矩阵；
- 拿到 PO 对角色边界确认。

**Dependencies:** A0。

**Human Gate:** PO 确认绩效管理员/复核人/只读查看者的实际权限范围。

---

## 卡 D2：实现重算权限、审计和状态机并发保护

**Owner:** `feishu-builder`

**Objective:** 在服务端而非前端弹窗实现对批量重算与复核的安全约束。

**Files:**
- Modify：`server/modules/calc/calc.controller.ts`
- Modify：`server/modules/calc/calc.service.ts`
- Modify：`server/modules/calc/sql-calc.store.ts`
- Modify：`server/modules/write/write.controller.ts`
- Modify：`server/modules/write/write.service.ts`
- Modify：`server/modules/write/sql-write.store.ts`
- Test：calc/write controller/service tests。

**Implementation constraints:**
1. `calc/run` 至少显式 `NeedLogin`；按 D1 角色矩阵进行授权；
2. run 写入记录操作人、发起时间、期间、结果摘要；
3. 复核更新使用 compare-and-swap：旧状态不匹配返回 409；
4. 统一 NULL/空 `review_status` 的规范化；
5. UI 仅消费服务端返回的权限与冲突错误，不把前端确认视为安全控制。

**Verification:**
- 未登录、无权限、合法管理员三类测试；
- 两个并发复核请求只有一个成功；
- NULL 历史状态可按统一规则完成首次复核；
- run 的审计记录可回读。

**Dependencies:** D1；C2（写闭环稳定）。

---

## 卡 D3：统一字段值域与输入边界

**Owner:** `automation-engineer`

**Objective:** 消除 `is_exempt`、分页、排序等跨层合同不一致。

**Files:**
- Modify：`shared/api.interface.ts`
- Modify：`server/modules/performance/performance.controller.ts`
- Modify：`server/modules/actual/actual.controller.ts`
- Modify：`server/modules/calc/calc.service.ts`
- Modify：`server/modules/performance/performance.service.ts`
- Modify：对应 React 渲染和 tests。

**Verification:**
- `is_exempt` 只有一个 canonical enum；
- 非法 page/pageSize/sort 返回 400；
- UI 不显示裸 `true/false`；
- 类型检查与既有 API tests 通过。

**Dependencies:** B1、D2。

---

# Phase E：端到端回归、独立校对与发布

## 卡 Q0：全链路集成验收（dev）

**Owner:** `qa-reviewer`

**Objective:** 在 dev 环境完成“不依赖系统自证”的闭环验收，覆盖录入、计算、结果、提成、复核、导出。

**Files:**
- Create：`org-performance-app/docs/修复后全链路验收报告.md`
- Create/Modify：测试/验收脚本（只读输出，不含生产数据写入）。

**Verification Matrix:**
1. 录入 Actual → preview/run 数值发生预期变化；
2. 结果列表按员工+期间唯一；详情有全部指标；
3. `Σ weighted_score = monthly_total`；
4. Dashboard / 结果书 / 详情提成一致且不重复；
5. 未授权重算失败、授权重算成功并可审计；
6. 并发 Actual / 并发复核行为正确；
7. 2026-07 与 Base/Excel/Python 外部基线逐项对照；
8. npm test、typecheck、lint 全绿。

**Acceptance Criteria:**
- 所有项 PASS；任何金额或分数差异为 0，或已得到 PO 书面解释；
- 测试数据已清理并回读 0 残留；
- 不发布 online。

**Dependencies:** B1、B2、C2、C3、D2、D3。

---

## 卡 Q1：线上发布与页面端到端验收

**Owner:** `qa-reviewer`

**Objective:** 经 PO 明确上线授权后，按一次完整、可回滚的 release 验证线上真实页面与 API。

**Files:**
- Create：`org-performance-app/docs/线上发布与页面验收记录.md`

**Steps:**
1. 审查 clean worktree、提交范围、独立代码审查结论；
2. push `sprint/default`；创建并轮询妙搭 release；
3. 使用 Chrome 已登录态验收：总览、结果列表、详情、员工档案、规则、采集、项目、批次；
4. 核对浏览器页面数值与 online SQL、外部基线；
5. 记录线上 URL、release ID、实际截图/接口证据；
6. 若失败，停止后续迁移，按已审查回滚方案处理。

**Acceptance Criteria:**
- 每页加载、筛选、详情、错误态、权限态均通过；
- 线上结果不重复、不空明细、不重复计提成；
- 不发生未授权写入；
- PO 验收后才解锁后续 jsonb 迁移。

**Dependencies:** Q0。

**Human Gate:** 明确上线授权。

---

# Phase F：关联字段 jsonb→文本迁移（最后执行）

## 卡 J0：字段级文本关联设计与迁移演练计划

**Owner:** `system-architect`

**Objective:** 把 40 个 jsonb 关联字段分成单值、多值、保留 JSON 三类，生成可执行的 expand/contract 迁移清单。

**Files:**
- Create：`org-performance-app/docs/jsonb到文本迁移设计与字段矩阵.md`
- Read：`server/database/schema.ts`、`server/common/jsonb-link.ts`、审计报告。

**Required decisions:**
- 单值：新增 `*_record_id text NULL`，值为目标 `base_record_id`；
- 多值：`responsible_channel_ids` 保持数组语义，短期 JSON 文本数组或长期关系表，禁止逗号拼接；
- 不删除旧 jsonb 列，不立即改变线上列类型；
- 每字段写清回填 SQL、双读规则、空值/畸形值/无效引用策略、consumer owner。

**Acceptance Criteria:**
- 40 列逐字段矩阵完成；所有 75 个消费点已映射；PO 确认多值字段方案。

**Dependencies:** Q1。

---

## 卡 J1：dev 新增文本列、回填与双读兼容层

**Owner:** `data-engineer`

**Objective:** 仅在 dev 通过扩展性 schema 变更安全引入文本关联字段，保留 jsonb 原列。

**Files:**
- Modify：`server/database/schema.ts`
- Create：dev migration / validation script
- Modify：`server/common/jsonb-link.ts`（变为兼容层或替代 helper）
- Modify：受影响服务的读取路径（分批进行）。

**Steps:**
1. 为单值关联新增 `_record_id text NULL`，不得原地改 jsonb；
2. dev 回填：从 `link_record_ids[0]` 提取 `rec...`；空壳映射为 SQL NULL；
3. 对每表记录总行数、非空数、空值分类、目标存在性、重复/无效引用；
4. 先双读（文本优先、jsonb fallback），不切在线写入；
5. 运行 `db-env-diff`，只审查不迁 online。

**Acceptance Criteria:**
- dev 回填零无效引用；数据核对报告完整；jsonb 原列仍在；线上零改动。

**Dependencies:** J0。

---

## 卡 J2：转换写接口、计算、规则、总览、导出与前端 API 合同

**Owner:** `feishu-builder`

**Objective:** 将所有关联读写从 jsonb 壳切换为文本关联合同，并保持前端 DTO 语义不变。

**Files:**
- Modify：`server/modules/write/*`
- Modify：`server/modules/calc/*`
- Modify：`server/modules/performance/*`
- Modify：`server/modules/dashboard/*`
- Modify：`server/modules/rule/*`
- Modify：`server/modules/employee/*`
- Modify：`server/modules/project/*`
- Modify：`server/modules/actual/*`
- Modify：测试与 fixtures。

**Implementation constraints:**
1. 不在 React 端暴露/解析关联壳；后端继续返回拍平 DTO；
2. 新增/更新写入只写文本关联字段；观察期内可选双写旧 jsonb，但必须有单点 helper，不可散落手写 JSON；
3. 所有 SQL JSON 运算替换为 text join；
4. 多值负责渠道按 J0 方案处理；
5. 每个模块独立测试，避免大规模盲改。

**Acceptance Criteria:**
- 搜索运行态 `link_record_ids` 依赖为 0（兼容/迁移脚本中的历史读取除外，并列明）；
- 结果、规则、人员、项目、Actual、导出、Dashboard 全部测试通过；
- 前端无直接 jsonb 耦合。

**Dependencies:** J1。

---

## 卡 J3：dev 外部基线回归与迁移发布准备

**Owner:** `qa-reviewer`

**Objective:** 验证文本关联迁移没有改变业务计算与页面行为，并做 online 发布前的不可逆风险检查。

**Files:**
- Create：`org-performance-app/docs/jsonb文本迁移dev验收报告.md`

**Verification:**
1. 16 表行数、单值/多值关联非空数、无效引用均通过；
2. 2026-07 与 Base/Excel/Python 外部基线逐项比对；
3. `Σ weighted_score = monthly_total`；
4. 写入、重算、复核、列表、详情、Dashboard、结果书、规则匹配、项目归属全链路通过；
5. 生成并校验离机 online 备份（不依赖短 PITR）；
6. `db-env-diff` 精确 DDL 已审阅，评估锁表与回滚。

**Acceptance Criteria:**
- dev 全绿；无金额/得分差异；提供上线 DDL、回滚/双读期限与风险清单。

**Dependencies:** J2。

---

## 卡 J4：online 迁移、线上复验与观察期切换

**Owner:** `data-engineer`

**Objective:** 仅在 PO 明确上线授权后，把已在 dev 验证的 expand 阶段迁移发布到 online，并做复验；不删除 jsonb 原列。

**Steps:**
1. 再次确认 db-sync 维持 disabled；
2. 执行审阅过的 `db-env-migrate`；
3. 回填/双读数据校验；
4. Chrome 线上端到端验收 + 外部基线比对；
5. 保留 jsonb 原列跨一个观察期；记录所有异常。

**Acceptance Criteria:**
- online 结果、金额、关联无差异；
- 无需、也不得启用 db-sync 作为回滚；
- 观察期结束且 PO 确认后，才可另立“contract 阶段删除旧 jsonb”卡。

**Dependencies:** J3。

**Human Gate:** 明确 online schema/data 迁移授权。

---

# Phase G：恢复产品功能开发

## 卡 G1：重新拆分前端试算、重算、导出功能

**Owner:** `feishu-builder`

**Objective:** 在 Q1 通过后，基于正确结果读模型和权限合同重新实现 UI，不复用旧 P3c 未审查代码。

**拆卡方式：**
1. G1a：只读试算预览与“未落库”清晰标识；
2. G1b：授权用户的“重算并落库”确认流程、冲突/权限/审计反馈；
3. G1c：结果书按 B-DEC 合同导出；
4. 每卡完成后均需真实 Chrome 页面验收。

**Dependencies:** Q1。

---

# 批次与依赖图

```text
A0 → A1 → B-DEC(PO确认) ─┬→ B1 ─┐
                         └→ B2 ─┼→ Q0 → Q1(上线授权) → J0 → J1 → J2 → J3 → J4(迁移授权) → G1
A0 → C1(PO确认) → C2 → C3 ──────┤
A0 → D1(PO确认) → D2 → D3 ──────┘
```

## 推荐发卡批次

| 批次 | 可发卡 | 前提 | 说明 |
|---|---|---|---|
| 0 | A0 | 无 | 只隔离旧工作区，先确保修复不会夹带旧 P3c |
| 1 | A1、C1、D1、B-DEC | A0 | 调研/测试/设计可并行；B-DEC、C1、D1 含 PO 决策门 |
| 2 | B1、B2、C2、D2 | PO 对 B-DEC/C1/D1 确认 | 核心 P0 实现；B1/B2 可并行，C2/D2 按合同实现 |
| 3 | C3、D3、Q0 | Phase 2 完成 | 先加固，再集成验收 |
| 4 | Q1 | Q0 PASS + PO 上线授权 | 唯一允许发布的修复卡 |
| 5 | J0→J4 | Q1 PASS + 各迁移授权 | jsonb 迁移最后执行，严格串行 |
| 6 | G1a→G1c | J4 观察期后 | 恢复试算/重算/导出 UI 功能 |

## 明确不做

- 不直接修改 `jsonb` 原列类型；
- 不重新启用 db-sync；
- 不以系统 SQL 自己回读当外部正确性证明；
- 不把未提交 P3c 改动与任何修复 release 混发；
- 不在核心读模型错误时继续做节点组织管理、bot 报数或备份自动化功能。
