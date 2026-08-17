# T8c 岗位归并全量排查报告

生成时间：2026-08-17 12:34:39 +0800

## 运行方式

只读预检；未修改任何 Base 记录。

## 计数

- Position: 53
- Employee: 80
- Metric: 45

## 同名岗位组及结论

### 平面设计师
- POS000029（record_id=recvslrK0j6XH2；Org=recvslr8CHxVvG；Status=Active；Note=空）
- POS000030（record_id=recvslrK0jLmvT；Org=recvslr8CHLXF4；Status=Active；Note=空）
- POS000031（record_id=recvslrK0jBEsX；Org=recvslr8CHb4xd；Status=Active；Note=空）
- Employee：3 人，挂靠 record_id=recvslrK0j6XH2, recvslrK0jLmvT
- Metric：0 项，挂靠 record_id=无
- 结论：保留：无 Metric 挂靠，无法以 V04 KPI 规则证明应合并；同名记录按部门实体语义保留。

### 电商客服专员
- POS000037（record_id=recvslrK0jQSSX；Org=recvslr8CHneDq；Status=Inactive；Note=已并入 POS000038，2026-08-17，T8c）
- POS000038（record_id=recvslrK0ji8UR；Org=recvslr8CHLXF4；Status=Active；Note=空）
- Employee：5 人，挂靠 record_id=recvslrK0ji8UR
- Metric：6 项，挂靠 record_id=recvslrK0ji8UR
- 结论：归并完成：EMP000027/EMP000028 已改挂 POS000038；POS000037 已 Inactive 并保留归并注记；6项 Active Metric 仍挂 POS000038。

### 电商客服主管
- POS000039（record_id=recvslrK0jAhwx；Org=recvslr8CHneDq；Status=Active；Note=T8c全量排查：与 POS000040 同名，但不在 V04 KPI 覆盖范围；保留原实体语义，暂不处理。）
- POS000040（record_id=recvslrK0j01uJ；Org=recvslr8CHLXF4；Status=Active；Note=T8c全量排查：与 POS000039 同名，但不在 V04 KPI 覆盖范围；保留原实体语义，暂不处理。）
- Employee：2 人，挂靠 record_id=recvslrK0j01uJ
- Metric：0 项，挂靠 record_id=无
- 结论：暂不处理：同名但属于不同实体语义，且不在 V04 KPI 覆盖范围；按任务要求保留。

## 确认参与员工 → Active Metric 预检

- 预期/实际确认参与人数：32/32
- 当前通过/失败：32/0

## 阻断项


## 后续维护说明

1. D-012/CHG-T8C-001 已为全部 14 张正式表补建可选 Note(TEXT) 字段；后续治理说明须追加在该字段，不得复用 Source 或 Position_Alias。
2. 本次仅归并 EMP000027、EMP000028 至 POS000038，并将 POS000037 置 Inactive；未修改 Metric、Target 或业务结果。
3. 归并前快照、写入结果与记录级回滚计划见 data/output/T8c_position_merge_execution_*.json 及 scripts/rollback_t8c_position_merge.py。
