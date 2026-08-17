#!/usr/bin/env python3
"""回滚 T8b D-010 收尾。默认只生成清单；--apply 才恢复改前字段并删除本次新建 Project_Member。"""
from __future__ import annotations
import argparse, json, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/output'
BASE = 'FCxObLU6yao5jgsciZfcWHKwnjh'
T = {'Project_Member': 'tblcUUz0oq9MxNLu', 'Error_Log': 'tbl4ZpuuOxZacWgj', 'Import_Batch': 'tblHV3JoVR9AEETw'}


def cli(args, payload=None, name='rollback'):
    cmd = ['lark-cli', 'base', *args, '--as', 'user', '--format', 'json']
    if payload is not None:
        path = OUT / 't8b_d010_payloads' / f'{name}.json'
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
        cmd += ['--json', '@' + str(path.relative_to(ROOT))]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=os.environ | {'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1', 'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'})
    body = json.loads(result.stdout)
    if result.returncode or not body.get('ok'):
        raise RuntimeError(json.dumps({'stdout': body, 'stderr': result.stderr}, ensure_ascii=False))
    return body


def chunks(items, n=200):
    for i in range(0, len(items), n):
        yield i // n + 1, items[i:i + n]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = json.loads((OUT / 'T8b_d010_finalize_plan.json').read_text())
    result = json.loads((OUT / 'T8b_d010_finalize_result.json').read_text())['result'] if (OUT / 'T8b_d010_finalize_result.json').exists() else {'written': {'Project_Member': [], 'Error_Log': [], 'Import_Batch': []}}
    written = result['written']
    manifest = {
        'task': 'T8b-D010-finalize', 'decision': 'D-010', 'batch_record_id': plan['batch_record_id'],
        'rollback_scope': {'Project_Member_delete': len(written['Project_Member']), 'Error_Log_restore': len(written['Error_Log']), 'Import_Batch_restore': len(written['Import_Batch'])},
        'method': 'Delete only D-010-created Project_Member records; restore exact prior mutable Error_Log and Import_Batch values captured in the preflight plan. Create_Time and original Source are untouched.',
        'apply_required': True,
    }
    (OUT / 'T8b_d010_rollback_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    if not args.apply:
        print(json.dumps({'status': 'DRY_RUN_PASSED', 'manifest': str(OUT / 'T8b_d010_rollback_manifest.json'), 'scope': manifest['rollback_scope']}, ensure_ascii=False))
        return
    prior_fields = ['Error_Content', 'Process_Status', 'Handler', 'Handle_Time', 'Status', 'Update_Time']
    prior = {item['record_id']: {key: item['prior'].get(key) for key in prior_fields} for item in plan['error_log']['closed']}
    for i, group in chunks(list(prior.items())):
        cli(['+record-batch-update', '--base-token', BASE, '--table-id', T['Error_Log']], {'update_records': dict(group)}, f'rollback_error_log_{i}')
    batch_prior = {key: plan['batch_prior'].get(key) for key in ['Total_Count', 'Success_Count', 'Fail_Count', 'Status', 'Update_Time']}
    cli(['+record-batch-update', '--base-token', BASE, '--table-id', T['Import_Batch']], {'update_records': {plan['batch_record_id']: batch_prior}}, 'rollback_import_batch')
    for record_id in written['Project_Member']:
        cli(['+record-delete', '--base-token', BASE, '--table-id', T['Project_Member'], '--record-id', record_id, '--yes'])
    print(json.dumps({'status': 'ROLLED_BACK', 'scope': manifest['rollback_scope']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
