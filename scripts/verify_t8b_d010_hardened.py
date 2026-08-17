#!/usr/bin/env python3
"""T8b D-010 加固验证（QA t_c1a9efca 三项问题闭环）：只读，不修改 Base。

三项加固：
  A. 注册 ID 集合校验：逐条验证 Metric/Commission_Tier/Target/Project_Member
     回填 Link 的 record_id 属于 T8a 已注册主数据（Position/Channel/Employee/Project）全集。
  B. 101 源记录逐条闭环：每个源 old_record_id 恰好对应一个 Project_Member
     （经 Source 字段追溯）或一个 Active Error_Log（经 Object_ID），三集合两两不相交、并集=101。
  C. 聚合对账（沿用原 verify 语义）：45/42/6156/23/317/78/216/23 + Import_Batch。
"""
from __future__ import annotations
import json, os, re, subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/output'
BASE = 'FCxObLU6yao5jgsciZfcWHKwnjh'
BATCH = 'recvslw7f2LYhf'
# 业务表（T8b 写入目标）
T = {'Metric': 'tbldKtdIVv8nnTyX', 'Commission_Tier': 'tblkZUoHYwBIvDYe', 'Target': 'tblydZkf17kmzrO0',
     'Project_Member': 'tblcUUz0oq9MxNLu', 'Error_Log': 'tbl4ZpuuOxZacWgj', 'Import_Batch': 'tblHV3JoVR9AEETw'}
# 主数据表（T8a 注册，仅作 ID 集合来源）
M = {'Position': 'tbldzvsg9Op6pK29', 'Channel': 'tblqOGJknsD2H3bt',
     'Employee': 'tblc59aB4EnSxkQv', 'Project': 'tbl1GO2vR9ZAqPbr'}
SOURCE_SNAPSHOT = OUT / 't8b_old_project_member_source.json'

def cli(args):
    result = subprocess.run(['lark-cli', 'base', *args, '--as', 'user', '--format', 'json'],
                            cwd=ROOT, text=True, capture_output=True,
                            env=os.environ | {'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1',
                                              'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'})
    body = json.loads(result.stdout)
    if result.returncode or not body.get('ok'):
        raise RuntimeError(json.dumps({'stdout': body, 'stderr': result.stderr}, ensure_ascii=False))
    return body

def rows(table, fields, limit=200):
    output, offset = [], 0
    while True:
        args = ['+record-list', '--base-token', BASE, '--table-id', table, '--limit', str(limit), '--offset', str(offset)]
        for field in fields: args += ['--field-id', field]
        data = cli(args)['data']
        output += [{'record_id': rid, **dict(zip(data['fields'], value))}
                   for rid, value in zip(data['record_id_list'], data['data'])]
        if not data.get('has_more'): return output
        offset += len(data['data'])

def one_link(value): return bool(isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict) and value[0].get('id'))
def link_id(value): return value[0]['id'] if one_link(value) else None
def batch_match(value): return any(x.get('id') == BATCH for x in (value or []) if isinstance(x, dict))

def main():
    # ---- A 部分：注册 ID 集合 ----
    registered = {name: {r['record_id'] for r in rows(tid, ['{}_ID'.format(
        {'Position': 'Position', 'Channel': 'Channel', 'Employee': 'Employee', 'Project': 'Project'}[name])])}
        for name, tid in M.items()}
    # 也校验主数据表自身：record_id 与业务 ID 一一对应（无重复注册）
    reg_report = {name: {'count': len(ids), 'sample': sorted(ids)[:3]} for name, ids in registered.items()}

    # ---- B 部分：业务表读取 ----
    metric = rows(T['Metric'], ['Metric_ID', 'Position_ID'])
    tier = rows(T['Commission_Tier'], ['Commission_Tier_ID', 'Position_ID'])
    target = rows(T['Target'], ['Target_ID', 'Channel_ID', 'Metric_ID'])
    pm = rows(T['Project_Member'], ['Project_Member_ID', 'Employee_ID', 'Project_ID', 'Channel_ID',
                                    'Effective_Start', 'Is_Primary', 'Status', 'Source'])
    errors = [x for x in rows(T['Error_Log'], ['Batch_ID', 'Object_Type', 'Object_ID', 'Error_Type',
                                               'Process_Status', 'Status']) if batch_match(x.get('Batch_ID'))]
    batch = next(x for x in rows(T['Import_Batch'], ['Batch_ID', 'Total_Count', 'Success_Count',
                                                     'Fail_Count', 'Status']) if x['record_id'] == BATCH)

    # 逐条注册 ID 归属校验（QA 问题 2）
    violations = []  # (table, business_id, field, link_id, expected_set)
    for r in metric:
        lid = link_id(r['Position_ID'])
        if lid not in registered['Position']:
            violations.append(('Metric', r['Metric_ID'], 'Position_ID', lid, 'Position'))
    for r in tier:
        lid = link_id(r['Position_ID'])
        if lid not in registered['Position']:
            violations.append(('Commission_Tier', r['Commission_Tier_ID'], 'Position_ID', lid, 'Position'))
    for r in target:
        lid = link_id(r['Channel_ID'])
        if lid not in registered['Channel']:
            violations.append(('Target', r['Target_ID'], 'Channel_ID', lid, 'Channel'))
    for r in pm:
        eid, pid, cid = link_id(r['Employee_ID']), link_id(r['Project_ID']), link_id(r['Channel_ID'])
        if eid not in registered['Employee']:
            violations.append(('Project_Member', r['Project_Member_ID'], 'Employee_ID', eid, 'Employee'))
        if pid not in registered['Project']:
            violations.append(('Project_Member', r['Project_Member_ID'], 'Project_ID', pid, 'Project'))
        if cid is not None and cid not in registered['Channel']:
            violations.append(('Project_Member', r['Project_Member_ID'], 'Channel_ID', cid, 'Channel'))

    # 101 源记录逐条闭环（QA 问题 3）：old_record_id -> PM(Source 追溯) / Active Error_Log(Object_ID)
    source = json.loads(SOURCE_SNAPSHOT.read_text(encoding='utf-8'))['data']
    old_ids = set(source['record_id_list'])
    pm_old = {}   # old_record_id -> PM record_id
    for r in pm:
        m = re.search(r'在职人员对照项目:(rec[a-zA-Z0-9]+)', r.get('Source') or '')
        if m: pm_old[m.group(1)] = r['record_id']
    active_errors = {x['Object_ID']: x['record_id'] for x in errors
                     if x['Object_Type'] == 'Project_Member' and x['Status'] == 'Active'}
    closed_pm = [x for x in errors if x['Object_Type'] == 'Project_Member' and x['Status'] == 'Archived']
    closed_target = [x for x in errors if x['Object_Type'] == 'Target' and x['Status'] == 'Archived']

    partition_issues = []
    if len(source['record_id_list']) != 101: partition_issues.append(f'source rows={len(source["record_id_list"])} != 101')
    if set(pm_old) & set(active_errors): partition_issues.append('PM 与 Active Error_Log 的 old_record_id 重叠')
    union = set(pm_old) | set(active_errors)
    if union != old_ids:
        missing = sorted(old_ids - union); extra = sorted(union - old_ids)
        partition_issues.append(f'并集!=源集合 missing={len(missing)} extra={len(extra)}')
    # 每个 old_record_id 必须恰好一个去向（PM 中不重复）
    if len(set(pm_old)) != len(pm_old): partition_issues.append('PM Source 追溯存在重复 old_record_id')
    if len(set(active_errors)) != len(active_errors): partition_issues.append('Active Error_Log Object_ID 重复')

    # ---- C 部分：聚合对账 ----
    new_pm = [x for x in pm if x['Project_Member_ID'] and x['Project_Member_ID'] >= 'PM000001']
    report = {
        'status': 'PASSED',
        'registered_master_ids': reg_report,
        'link_registry_checks': {
            'violations': violations,
            'checked': {'Metric.Position_ID': len(metric), 'Commission_Tier.Position_ID': len(tier),
                        'Target.Channel_ID': len(target),
                        'Project_Member.Employee_ID': len(pm), 'Project_Member.Project_ID': len(pm),
                        'Project_Member.Channel_ID': sum(1 for r in pm if link_id(r['Channel_ID']) is not None)},
        },
        'counts': {
            'Metric_position_single_link': sum(one_link(x['Position_ID']) for x in metric),
            'Metric_total': len(metric),
            'Commission_position_single_link': sum(one_link(x['Position_ID']) for x in tier),
            'Commission_total': len(tier),
            'Target_channel_single_link': sum(one_link(x['Channel_ID']) for x in target),
            'Target_total': len(target),
            'Project_Member_total': len(pm), 'Project_Member_d010_expected': 23,
            'Error_Log_batch_total': len(errors),
            'Error_Log_closed_target_expected': len(closed_target),
            'Error_Log_closed_pm_expected': len(closed_pm),
            'Error_Log_active_pm_expected': len(active_errors),
        },
        'source_closure': {
            'source_rows': len(source['record_id_list']),
            'pm_traced': len(pm_old), 'active_error_traced': len(active_errors),
            'partition_issues': partition_issues,
        },
        'batch': batch,
        'project_member_statuses': Counter(x['Status'] for x in pm),
        'project_member_empty_effective_start': sum(x['Effective_Start'] is None for x in pm),
        'project_member_false_primary': sum(x['Is_Primary'] is False for x in pm),
        'open_error_breakdown': {f'{o}|{e}': c for (o, e), c in Counter(
            (x['Object_Type'], x['Error_Type']) for x in errors if x['Status'] == 'Active').items()},
    }
    expected = report['counts']
    checks = [
        not violations,
        not partition_issues,
        expected['Metric_position_single_link'] == expected['Metric_total'] == 45,
        expected['Commission_position_single_link'] == expected['Commission_total'] == 42,
        expected['Target_channel_single_link'] == expected['Target_total'] == 6156,
        expected['Project_Member_total'] == expected['Project_Member_d010_expected'] == 23,
        expected['Error_Log_batch_total'] == 317,
        expected['Error_Log_closed_target_expected'] == 216,
        expected['Error_Log_closed_pm_expected'] == 23,
        expected['Error_Log_active_pm_expected'] == 78,
        len(pm_old) == 23 and len(active_errors) == 78,
        batch['Total_Count'] == 6344 and batch['Success_Count'] == 6266 and batch['Fail_Count'] == 78 and batch['Status'] == 'Partial',
        report['project_member_statuses'] == Counter({'待在线维护': 23}),
        report['project_member_empty_effective_start'] == 23 and report['project_member_false_primary'] == 23,
    ]
    if not all(checks):
        report['status'] = 'FAILED'
    (OUT / 'T8b_d010_hardened_verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=dict) + '\n')
    print(json.dumps(report, ensure_ascii=False, default=dict))
    if report['status'] != 'PASSED': raise SystemExit(1)

if __name__ == '__main__':
    main()
