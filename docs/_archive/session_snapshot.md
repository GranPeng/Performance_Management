# 绩效核算系统 · 会话状态快照（2026-08-20 晚）

> 用途：上下文压缩/换会话后接续。最新状态以此文件 + decision_log.md + kanban 看板（`hermes kanban list`）为准。

## 项目一句话
绩效核算系统开发：妙搭应用内交互式维护数据（主存储=妙搭 PostgreSQL）→ TS 计算引擎核算 → 结果存 Base/导出；飞书 bot 报数入口最后接入（P5）。kanban 多 agent 编排。

## 架构（2026-08-19 拍板，D-022/D-023/D-024，仍然有效）
- 系统运行主存储 = 妙搭 PostgreSQL；Base 只存结果/导入数据，不维护
- 计算引擎 = 妙搭服务端 TypeScript（唯一计算权威，规则读配置）
- 校对核实权威源 = 外部独立标准答案（V04/V60 Excel、Base 原始录入、192 行基线蓝本），禁止系统自证
- 新建 Base 禁用关联表功能（文本字段存 record_id）

## 合同层（2026-08-20 建立，是实现的最高业务依据）
位置：`org-performance-app-bdec-tbd/docs/`（分支 `docs/bdec-commission-contract`）
- **B-DEC**《提成归属与聚合合同》：员工+期间唯一月度提成快照，禁止按 KPI 行累加（D-025）
- **C0**《计算引擎取值与组合规则合同》：V01 已定稿+GREEN；V02 修订中（卡 t_a8300dab，实时聚合+四枚举）
- **C1**《Actual到结果关联合同》：历史决策，已被 C2 取代（文首有声明，勿据此实施）
- **C2**《结算计算输入关联合同》：V02 独立关联表 `app_calc_input_link` 已定稿且纯函数 GREEN；V3 变更中（卡 t_187248c4，团队实时聚合放开评分输入基数）
- **C0 补丁 V01**《岗位绩效与手工校准差异与建议》：方案 B（导入层物化）已被 PO 否决，仅边界分析保留参考价值

## 白板（业务语义源头，PO 直接维护）
- 文档 `https://jv8fym591u8.feishu.cn/docx/F6jVdDnOLocDb3xr3rjcHow9nJh`，画板 token `QtJdw70Uahh4AwbmV2AcJ7ulnih`
- 最新导出（V2）：`performance-system/2.diagrams/whiteboard_nodes_20260820_v2.json` + 同名 preview jpg；V1 导出同目录（Diff 工具脚本曾用 /tmp/wb_diff.py）
- V2 核心语义 = decision_log D-026/D-027/D-028

## 当前阶段（引擎重构进行中）
- **已收口**：数据层（T 系列 11 轮复验）、P1a/b/c、P2、P3a/P3b、数据迁移（t_10edd9a2 ACCEPTED）、dev/online 双库
- **引擎重构第一批（已验收+提交固化）**：A1 读模型 RED 门槛 → B1 转绿（commit 046a6be，全量 102/102 无任何故意 RED）；C0 source-resolver GREEN（b487be3）；C2 V2 calc-input-link GREEN 11/11（8dcd8f0）；D-CTX 文档同步（t_82848c43）；C0 补丁 V01（1e69f78）
- **进行中**：C0-V02（t_a8300dab）、C2-V3（t_187248c4）两张合同卡，均订阅飞书私聊 notify+wake
- **挂起**：P3d（t_10d771d7 todo，jsonb→text 拍平 40 列+57 处，**已成关键路径**）；P3c（t_4500c139 blocked——实际活已干完：试算161行0差异/落库161行/结果书导出565KB/Jest 81/81 全过，但**未提交**，改动在主仓库 `wip/p3c-isolation-t_fa00cf3f` 分支工作区；等 B1✓+P3d 落地后复核恢复）

## 下一步顺序
C0 V02 + C2 V3 定稿 → DDL+服务接入卡（app_calc_input_link 建表+读路径统一解析：adapter/结果书/preview/run/详情四处）→ P3d → P3c 复核恢复+提交 → 外部基线校对 → 手工调整例外通道与团队聚合实现卡

## 仓库拓扑（易踩坑）
- 主仓库 `org-performance-app/`：开发主线分支 `sprint/default`（main 只有 init 提交，勿以 main 为准）
- **活跃工作区 `org-performance-app-bdec-tbd/`**：分支 `docs/bdec-commission-contract`，引擎重构全部最新产出在这里
- 其他 worktree：`a1-tbd`（A1 分支，未并入主线）、`c1-tbd`（C1 历史）、`p0-clean-t_fa00cf3f`（A0 基线参照）、`p3c-wip-archive-t_fa00cf3f`（P3c 未提交改动备份，P3c 验收前勿删）
- worktree 清理须用 `git worktree remove`，勿直接删文件夹（分支未并入主线）

## 环境坑
- **worker profile（system-architect 等 6 个）没有 `miaoda-fullstack-dev` 技能**：发卡带 `--skill miaoda-fullstack-dev` 曾成功（18:34/19:25），20:38 起报 Unknown skill 秒崩（t_7c9a66d1 教训，机制变化未定位）。复制技能进 profile 需 PO 批准（跨 profile 写）。当前发卡不带该技能
- jest 运行先 `export PATH="$PWD/node_modules/.bin:$PATH"`（终端护栏坑，见 hermes-terminal-guard 技能）
- 空会话壳 `20260820_171041_33cfcf5b` 是 handoff 撞车产物，已归档，勿困惑
- 妙搭 dev 库连接串约 5 天时效，过期重跑 env-pull

## 看板速查
- running：t_a8300dab / t_187248c4；blocked：t_4500c139（P3c）；todo：t_10d771d7（P3d）
- 完工推送 → 飞书私聊 `oc_0de3b0be2c9e1bda4ab08c23f915faab`（notify+wake）

## 遗留（非阻塞）
~~王思伟/潘剑秋消耗修正~~（已随迁移落库 ACT000123/ACT000131）；广告投放 GSV 待 HR 复核；郭丽娜/陈乾/黄泽威 3 人不入；32 人 Responsible_Channel_IDs 未维护；云视频 Channel 映射待做

## 重要约束（用户偏好）
- token 额度用户自管：API 报错/额度不足阻塞时不自行切换模型，等用户充值；主模型限额绝不 fallback 到 moa（moa 是独立编排，不调用不启用，不碰）
- 接口/平台能力问题必须先查文档、看实际接口再回答，禁止不查资料乱说
- 全链路终验不拆分；QA 只读红线；决策记录只增不删；分批发卡批间确认；worker 自报必须独立核查
- goal 模式用户嫌烧 token，确定性任务不用
- 模型成本敏感：全 profile 默认 kimi-k3（kimi-coding），主配置 k3-256k
