#!/usr/bin/env python3
"""T8b D-010 写后读回验证；只读，不修改 Base。"""
from __future__ import annotations
import json, os, subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/output'
BASE = 'FCxObLU6yao5jgsciZfcWHKwnjh'
BATCH = 'recvslw7f2LYhf'
T = {'Metric': 'tbldKtdIVv8nnTyX', 'Commission_Tier': 'tblkZUoHYwBIvDYe', 'Target': 'tblydZkf17kmzrO0', 'Project_Member': 'tblcUUz0oq9MxNLu', 'Error_Log': 'tbl4ZpuuOxZacWgj', 'Import_Batch': 'tblHV3JoVR9AEETw'}

def cli(args):
    result = subprocess.run(['lark-cli', 'base', *args, '--as', 'user', '--format', 'json'], cwd=ROOT, text=True, capture_output=True, env=os.environ | {'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1', 'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'})
    body = json.loads(result.stdout)
    if result.returncode or not body.get('ok'):
        raise RuntimeError(json.dumps({'stdout': body, 'stderr': result.stderr}, ensure_ascii=False))
    return body

def rows(table, fields):
    output, offset = [], 0
    while True:
        args = ['+record-list', '--base-token', BASE, '--table-id', table, '--limit', '200', '--offset', str(offset)]
        for field in fields: args += ['--field-id', field]
        data = cli(args)['data']
        output += [{'record_id': rid, **dict(zip(data['fields'], value))} for rid, value in zip(data['record_id_list'], data['data'])]
        if not data.get('has_more'): return output
        offset += len(data['data'])

def one_link(value): return bool(isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict) and value[0].get('id'))
def batch_match(value): return any(x.get('id') == BATCH for x in (value or []) if isinstance(x, dict))

metric = rows(T['Metric'], ['Metric_ID', 'Position_ID'])
tier = rows(T['Commission_Tier'], ['Commission_Tier_ID', 'Position_ID'])
target = rows(T['Target'], ['Target_ID', 'Channel_ID', 'Metric_ID'])
pm = rows(T['Project_Member'], ['Project_Member_ID', 'Employee_ID', 'Project_ID', 'Channel_ID', 'Effective_Start', 'Is_Primary', 'Status'])
errors = [x for x in rows(T['Error_Log'], ['Batch_ID', 'Object_Type', 'Object_ID', 'Error_Type', 'Process_Status', 'Status']) if batch_match(x.get('Batch_ID'))]
batch = next(x for x in rows(T['Import_Batch'], ['Batch_ID', 'Total_Count', 'Success_Count', 'Fail_Count', 'Status']) if x['record_id'] == BATCH)
new_pm = [x for x in pm if x['Project_Member_ID'] and x['Project_Member_ID'] >= 'PM000001']
report = {
  'status': 'PASSED',
  'counts': {
    'Metric_position_single_link': sum(one_link(x['Position_ID']) for x in metric),
    'Metric_total': len(metric), 'Commission_position_single_link': sum(one_link(x['Position_ID']) for x in tier), 'Commission_total': len(tier),
    'Target_channel_single_link': sum(one_link(x['Channel_ID']) for x in target), 'Target_total': len(target),
    'Project_Member_total': len(pm), 'Project_Member_d010_expected': 23,
    'Error_Log_batch_total': len(errors),
    'Error_Log_closed_target_expected': sum(x['Object_Type'] == 'Target' and x['Process_Status'] == '已忽略' and x['Status'] == 'Archived' for x in errors),
    'Error_Log_closed_pm_expected': sum(x['Object_Type'] == 'Project_Member' and x['Process_Status'] == '已解决' and x['Status'] == 'Archived' for x in errors),
    'Error_Log_active_pm_expected': sum(x['Object_Type'] == 'Project_Member' and x['Process_Status'] == '待处理' and x['Status'] == 'Active' for x in errors),
  },
  'batch': batch,
  'project_member_statuses': Counter(x['Status'] for x in pm),
  'project_member_empty_effective_start': sum(x['Effective_Start'] is None for x in pm),
  'project_member_false_primary': sum(x['Is_Primary'] is False for x in pm),
  'open_error_breakdown': {f'{object_type}|{error_type}': count for (object_type, error_type), count in Counter((x['Object_Type'], x['Error_Type']) for x in errors if x['Status'] == 'Active').items()},
}
expected = report['counts']
checks = [
 expected['Metric_position_single_link'] == expected['Metric_total'] == 45,
 expected['Commission_position_single_link'] == expected['Commission_total'] == 42,
 expected['Target_channel_single_link'] == expected['Target_total'] == 6156,
 expected['Project_Member_total'] == expected['Project_Member_d010_expected'] == 23,
 expected['Error_Log_batch_total'] == 317,
 expected['Error_Log_closed_target_expected'] == 216,
 expected['Error_Log_closed_pm_expected'] == 23,
 expected['Error_Log_active_pm_expected'] == 78,
 batch['Total_Count'] == 6344 and batch['Success_Count'] == 6266 and batch['Fail_Count'] == 78 and batch['Status'] == 'Partial',
 report['project_member_statuses'] == Counter({'待在线维护': 23}),
 report['project_member_empty_effective_start'] == 23 and report['project_member_false_primary'] == 23,
]
if not all(checks):
    report['status'] = 'FAILED'
(OUT / 'T8b_d010_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=dict) + '\n')
print(json.dumps(report, ensure_ascii=False, default=dict))
if report['status'] != 'PASSED': raise SystemExit(1)
