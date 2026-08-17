#!/usr/bin/env python3
"""执行 D-010 的 T8b 收尾；默认只生成计划，--apply 才写正式 Base。

不新增任何主数据 ID。只把旧在线维护表中的自然语言展示值映射为已注册的 Link record_id；
不能唯一映射的行保持为真实数据质量异常，绝不伪造必填关联。
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/output'
BASE = 'FCxObLU6yao5jgsciZfcWHKwnjh'
BATCH_RECORD_ID = 'recvslw7f2LYhf'
T = {
    'Employee': 'tblc59aB4EnSxkQv', 'Project': 'tbl1GO2vR9ZAqPbr',
    'Channel': 'tblqOGJknsD2H3bt', 'Project_Member': 'tblcUUz0oq9MxNLu',
    'Error_Log': 'tbl4ZpuuOxZacWgj', 'Import_Batch': 'tblHV3JoVR9AEETw',
    'Old_Project_Member': 'tblB8ujzwz3EJsSv',
}
CHANNEL_ALIASES = {'天猫/淘宝': '天猫淘宝', '抖音达人': '达播'}


def stamp():
    return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')


def cli(args, payload=None, name='payload'):
    cmd = ['lark-cli', 'base', *args, '--as', 'user', '--format', 'json']
    if payload is not None:
        path = OUT / 't8b_d010_payloads' / f'{name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
        cmd.extend(['--json', '@' + str(path.relative_to(ROOT))])
    env = os.environ | {'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1', 'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'}
    for attempt in range(5):
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=env)
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            body = {'ok': False, 'stdout': result.stdout, 'stderr': result.stderr}
        if result.returncode == 0 and body.get('ok'):
            return body
        if 'onOverQPSLimit' in result.stdout + result.stderr and attempt < 4:
            time.sleep(attempt + 1)
            continue
        raise RuntimeError(json.dumps({'cmd': cmd[:4], 'rc': result.returncode, 'body': body, 'stderr': result.stderr}, ensure_ascii=False))
    raise RuntimeError('QPS retry exhausted')


def rows(table, fields):
    result, offset = [], 0
    while True:
        args = ['+record-list', '--base-token', BASE, '--table-id', table, '--limit', '200', '--offset', str(offset)]
        for field in fields:
            args.extend(['--field-id', field])
        data = cli(args)['data']
        names, values, ids = data['fields'], data['data'], data['record_id_list']
        if len(values) != len(ids):
            raise RuntimeError(f'{table}: record/data length mismatch')
        result.extend({'record_id': rid, **dict(zip(names, value))} for rid, value in zip(ids, values))
        if not data.get('has_more'):
            return result
        if not values:
            raise RuntimeError(f'{table}: empty page while has_more')
        offset += len(values)


def link(record_id):
    return [{'id': record_id}]


def first(value):
    return value[0] if isinstance(value, list) and value else value


def chunks(values, size=200):
    for start in range(0, len(values), size):
        yield start // size + 1, values[start:start + size]


def unique_by(rows_, key, label):
    groups = {}
    for row in rows_:
        value = row.get(key)
        if value:
            groups.setdefault(value, []).append(row)
    duplicates = sorted(k for k, v in groups.items() if len(v) != 1)
    if duplicates:
        raise RuntimeError(f'{label} natural-value mapping not unique: {duplicates}')
    return {k: v[0] for k, v in groups.items()}


def batch_link_contains(value):
    return any(item.get('id') == BATCH_RECORD_ID for item in (value or []) if isinstance(item, dict))


def pm_number(value):
    match = re.fullmatch(r'PM(\d{6})', value or '')
    return int(match.group(1)) if match else 0


def build_plan():
    now = stamp()
    employees = rows(T['Employee'], ['Employee_ID', 'Name', 'Status'])
    projects = rows(T['Project'], ['Project_ID', 'Project_Name', 'Status'])
    channels = rows(T['Channel'], ['Channel_ID', 'Channel_Name', 'Status'])
    old = rows(T['Old_Project_Member'], ['姓名', '手机号码', '人员对照项目', '项目所属渠道'])
    existing_pm = rows(T['Project_Member'], ['Project_Member_ID'])
    errors = rows(T['Error_Log'], ['Error_ID', 'Batch_ID', 'Object_Type', 'Object_ID', 'Error_Type', 'Error_Content', 'Process_Status', 'Handler', 'Handle_Time', 'Status', 'Update_Time'])
    batches = rows(T['Import_Batch'], ['Batch_ID', 'Total_Count', 'Success_Count', 'Fail_Count', 'Status', 'Update_Time'])

    batch = next((r for r in batches if r['record_id'] == BATCH_RECORD_ID), None)
    if not batch:
        raise RuntimeError(f'Import_Batch not found: {BATCH_RECORD_ID}')
    t8_errors = [r for r in errors if batch_link_contains(r.get('Batch_ID'))]
    if len(t8_errors) != 317:
        raise RuntimeError(f'T8b Error_Log cardinality mismatch: expected 317, got {len(t8_errors)}')

    emp_by = unique_by([r for r in employees if r.get('Status') == 'Active'], 'Name', 'Employee')
    project_by = unique_by([r for r in projects if r.get('Status') == 'Active'], 'Project_Name', 'Project')
    channel_by = unique_by([r for r in channels if r.get('Status') == 'Active'], 'Channel_Name', 'Channel')
    prior_pm_max = max((pm_number(r.get('Project_Member_ID')) for r in existing_pm), default=0)

    pm_create, unresolved = [], []
    for source_index, row in enumerate(old, 1):
        employee_name = row.get('姓名')
        project_name = first(row.get('人员对照项目'))
        source_channel = first(row.get('项目所属渠道'))
        canonical_channel = CHANNEL_ALIASES.get(source_channel, source_channel)
        reasons = []
        if employee_name not in emp_by:
            reasons.append(f'Employee未注册或非Active：{employee_name!r}')
        if project_name not in project_by:
            reasons.append(f'Project缺失/未注册或非Active：{project_name!r}')
        if source_channel and canonical_channel not in channel_by:
            reasons.append(f'Channel非权威或未注册：{source_channel!r}')
        if reasons:
            unresolved.append({'old_record_id': row['record_id'], 'source_index': source_index, 'reasons': reasons})
            continue
        member_id = f'PM{prior_pm_max + len(pm_create) + 1:06d}'
        source_text = (
            f'在职人员对照项目:{row["record_id"]}；D-010历史占位同步；'
            'Effective_Start按D-010留空；Is_Primary=false待在线维护确认。'
        )
        record = {
            'Project_Member_ID': member_id,
            'Employee_ID': link(emp_by[employee_name]['record_id']),
            'Project_ID': link(project_by[project_name]['record_id']),
            'Effective_Start': None,
            'Is_Primary': False,
            'Source': source_text,
            'Create_Time': now,
            'Update_Time': now,
            'Status': '待在线维护',
        }
        if source_channel:
            record['Channel_ID'] = link(channel_by[canonical_channel]['record_id'])
        pm_create.append({'old_record_id': row['record_id'], 'source_index': source_index, 'record': record})

    # D-010 closes the Target-to-Metric ambiguity as expected behavior. PM errors only close when a compliant placeholder was created.
    created_old_ids = {x['old_record_id'] for x in pm_create}
    closed, retained = [], []
    d010_note = '【D-010】已定：Target与Metric为间接多对多，预算Target不挂单一Metric_ID；此项为预期行为，已关闭。'
    for error in t8_errors:
        if error['Object_Type'] == 'Target' and error['Error_Type'] == '指标映射':
            closed.append({'record_id': error['record_id'], 'fields': {'Error_Content': error['Error_Content'] + '；' + d010_note, 'Process_Status': '已忽略', 'Handler': 'data-engineer/T8b-D010', 'Handle_Time': now, 'Status': 'Archived', 'Update_Time': now}, 'prior': error})
        elif error['Object_Type'] == 'Project_Member' and error['Object_ID'] in created_old_ids:
            closed.append({'record_id': error['record_id'], 'fields': {'Error_Content': error['Error_Content'] + '；【D-010】已创建历史占位Project_Member；Effective_Start留空、Is_Primary=false、Status=待在线维护。', 'Process_Status': '已解决', 'Handler': 'data-engineer/T8b-D010', 'Handle_Time': now, 'Status': 'Archived', 'Update_Time': now}, 'prior': error})
        else:
            retained.append({'record_id': error['record_id'], 'object_type': error['Object_Type'], 'object_id': error['Object_ID'], 'error_type': error['Error_Type'], 'content': error['Error_Content']})
    if len(closed) + len(retained) != 317:
        raise RuntimeError('Error_Log transition accounting mismatch')

    success = 6243 + len(pm_create)
    failure = len(unresolved)
    if success + failure != 6344:
        raise RuntimeError(f'Batch accounting mismatch: {success}+{failure} != 6344')
    return {
        'task': 'T8b-D010-finalize', 'decision': 'D-010', 'created_at': now, 'base_token': BASE,
        'batch_record_id': BATCH_RECORD_ID, 'batch_prior': batch, 'source_counts': {'old_project_member': len(old), 't8b_error_log': len(t8_errors)},
        'project_member': {'create_count': len(pm_create), 'unresolved_count': len(unresolved), 'records': pm_create, 'unresolved': unresolved},
        'error_log': {'close_count': len(closed), 'retain_open_count': len(retained), 'closed': closed, 'retained_open': retained},
        'batch_final': {'Total_Count': 6344, 'Success_Count': success, 'Fail_Count': failure, 'Status': 'Success' if failure == 0 else 'Partial', 'Update_Time': now},
        'assumptions': {'Effective_Start': 'null by D-010', 'Is_Primary': False, 'Is_Primary_reason': 'source has no primary marker; false is an explicit non-assertion pending online maintenance', 'Project_Member_Status': '待在线维护 by D-010'},
    }


def apply(plan):
    written = {'Project_Member': [], 'Error_Log': [], 'Import_Batch': []}
    for number, group in chunks(plan['project_member']['records']):
        payload = {'create_records': [item['record'] for item in group]}
        result = cli(['+record-batch-create', '--base-token', BASE, '--table-id', T['Project_Member']], payload, f'project_member_create_{number}')
        ids = result['data']['record_id_list']
        if len(ids) != len(group):
            raise RuntimeError(f'Project_Member create mismatch {len(ids)}/{len(group)}')
        written['Project_Member'].extend(ids)
    for number, group in chunks(plan['error_log']['closed']):
        payload = {'update_records': {item['record_id']: item['fields'] for item in group}}
        result = cli(['+record-batch-update', '--base-token', BASE, '--table-id', T['Error_Log']], payload, f'error_log_close_{number}')
        if result['data'].get('ignored_fields'):
            raise RuntimeError(f'Error_Log ignored fields: {result["data"]["ignored_fields"]}')
        written['Error_Log'].extend(item['record_id'] for item in group)
    payload = {'update_records': {BATCH_RECORD_ID: plan['batch_final']}}
    result = cli(['+record-batch-update', '--base-token', BASE, '--table-id', T['Import_Batch']], payload, 'import_batch_final')
    if result['data'].get('ignored_fields'):
        raise RuntimeError(f'Import_Batch ignored fields: {result["data"]["ignored_fields"]}')
    written['Import_Batch'].append(BATCH_RECORD_ID)
    return {'written': written}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    plan = build_plan()
    (OUT / 'T8b_d010_finalize_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    if not args.apply:
        print(json.dumps({'status': 'PREFLIGHT_PASSED', 'plan': str(OUT / 'T8b_d010_finalize_plan.json'), 'project_member_create': plan['project_member']['create_count'], 'project_member_unresolved': plan['project_member']['unresolved_count'], 'error_close': plan['error_log']['close_count'], 'error_retained': plan['error_log']['retain_open_count'], 'batch_final': plan['batch_final']}, ensure_ascii=False))
        return
    result = apply(plan)
    (OUT / 'T8b_d010_finalize_result.json').write_text(json.dumps({'plan_summary': {key: plan[key] for key in ('task', 'decision', 'batch_record_id', 'source_counts', 'batch_final', 'assumptions')}, 'result': result}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'APPLY_COMPLETED', 'result': result}, ensure_ascii=False))

if __name__ == '__main__':
    main()
