# 绩效核算系统 · 会话状态快照（2026-08-19）

> 用途：上下文压缩/换会话后接续。最新状态以此文件 + decision_log.md + kanban 看板为准。

## 项目一句话
绩效核算系统开发：妙搭应用内交互式维护数据（主存储=妙搭 PostgreSQL）→ TS 计算引擎核算 → 结果存 Base/导出；飞书 bot 报数入口最后接入（P5）。kanban 多 agent 编排。

## 架构（2026-08-19 拍板，D-022/D-023/D-024）
- 系统运行主存储 = 妙搭 PostgreSQL；Base 只存结果/导入数据，不维护
- 计算引擎 = 妙搭服务端 TypeScript（唯一计算权威，规则读配置）
- 校对核实权威源 = 外部独立标准答案（V04/V60 Excel、Base 原始录入、192 行基线蓝本），禁止系统自证
- 新建 Base 禁用关联表功能（文本字段存 record_id）

## 当前阶段
- T1~T27 + T15r11：数据层收口 ACCEPTED（192 行基线 0 差异）
- P1a/b/c（修复+清理）、P2（计算引擎）：done，已发布线上
- P3a 转向（t_eb766723）/ P3b 引擎落库+结果书（t_c1ce57be）：done ACCEPTED
- **数据迁移（t_10edd9a2）：done ACCEPTED——主存储已切妙搭 SQL，db-sync 16/16 已禁用（可恢复）**
- **拆双库完成（2026-08-20）**：专家模式开启后平台自动初始化，dev/online 双库就绪，本地可连 dev（SUDA_DATABASE_URL，5 天时效，过期重跑 env-pull）
- 线上：https://jv8fym591u8.feishuapp.com/app/app_17cdx8yk8pw（release 7675798605589384481）

## 看板现状（default 板）
- done：T 系列全部、P1a/P1b/P1c、P2、P3a 转向 t_eb766723、P3b t_c1ce57be、迁移 t_10edd9a2
- 已归档（架构转向作废）：t_a1ea45ca / t_39668d19 / t_896867d7（comment 留痕）
- 主任务 T1 = t_ce78b6e8

## 下一步（详见 docs/开发进度梳理与下一步计划_20260819_V01_架构切SQL.md）
1. ✅ 看板调整 → 2. ✅ P3a 写 SQL → 3. ✅ 数据迁移+拆双库 → 4. 本地备份 cron（优先级最低，开发完成后）→ 5. 结果书端点登录态实测+骨架生成卡 → 6. P4 节点式组织管理 → 7. P5 agent 报数

## 遗留（非阻塞）
~~王思伟/潘剑秋消耗修正~~（已随迁移落库 ACT000123/ACT000131）；广告投放 GSV 待 HR 复核；郭丽娜/陈乾/黄泽威 3 人不入；32 人 Responsible_Channel_IDs 未维护；云视频 Channel 映射待做

## 重要约束（用户偏好）
- token 额度用户自管：API 报错/额度不足阻塞时不自行切换模型，等用户充值；主模型限额绝不 fallback 到 moa（moa 是独立编排，不调用不启用，不碰）
- 接口/平台能力问题必须先查文档、看实际接口再回答，禁止不查资料乱说
- 全链路终验不拆分；QA 只读红线；决策记录只增不删；分批发卡批间确认
- goal 模式用户嫌烧 token，确定性任务不用
- 模型成本敏感：全 profile 默认 kimi-k3（kimi-coding），主配置 k3-256k
