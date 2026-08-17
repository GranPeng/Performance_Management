#!/usr/bin/env python3
"""T8a 回滚工具：默认只生成清单；仅 --apply 执行，且严格核对本批业务 ID。"""
import argparse, json, subprocess
from pathlib import Path

BASE='FCxObLU6yao5jgsciZfcWHKwnjh'
TABLES={'Employee':'tblc59aB4EnSxkQv','Channel':'tblqOGJknsD2H3bt','Project':'tbl1GO2vR9ZAqPbr','Position':'tbldzvsg9Op6pK29','Organization':'tblc6rU0d2bHMVnZ','Error_Log':'tbl4ZpuuOxZacWgj','Import_Batch':'tblHV3JoVR9AEETw'}
PK={'Employee':'Employee_ID','Channel':'Channel_ID','Project':'Project_ID','Position':'Position_ID','Organization':'Org_ID'}
ROOT=Path(__file__).resolve().parents[1]

def call(args):
 r=subprocess.run(['lark-cli','base']+args+['--as','user'],capture_output=True,text=True)
 if r.returncode: raise RuntimeError(r.stdout+r.stderr)
 return json.loads(r.stdout)
def rows(table, filter_json=None):
 a=['+record-list','--base-token',BASE,'--table-id',TABLES[table],'--format','json','--limit','200']
 if filter_json: a+=['--filter-json',json.dumps(filter_json,ensure_ascii=False)]
 d=call(a)['data']; return [dict(zip(d['fields'],v)) for v in d['data']], d['record_id_list']
def delete(table, ids):
 for i in range(0,len(ids),200): call(['+record-delete','--base-token',BASE,'--table-id',TABLES[table],'--json',json.dumps({'record_id_list':ids[i:i+200]}),'--yes'])
def main():
 a=argparse.ArgumentParser(); a.add_argument('--apply',action='store_true'); ns=a.parse_args()
 plan=json.loads((ROOT/'data/output/T8a_import_plan.json').read_text())
 result=json.loads((ROOT/'data/output/T8a_apply_result.json').read_text())['applied']
 batch_id=result['batch_id']; batch_record_id=result['batch_record_id']
 targets={'Employee':plan['employees'],'Channel':plan['channels'],'Project':plan['projects'],'Position':plan['positions'],'Organization':plan['orgs']}
 work=[]
 for table,planned in targets.items():
  current,ids=rows(table); m={r.get(PK[table]):rid for r,rid in zip(current,ids)}; expected={r[PK[table]] for r in planned}
  if set(m)&expected != expected: raise RuntimeError(f'{table}未包含完整T8a计划ID，拒绝回滚')
  work.append((table,[m[k] for k in expected]))
 err_filter={'logic':'and','conditions':[['Batch_ID','intersects',[{'id':batch_record_id}]]]}
 _,err_ids=rows('Error_Log',err_filter)
 batch_rows,batch_ids=rows('Import_Batch',{'logic':'and','conditions':[['Batch_ID','==',batch_id]]})
 if len(batch_ids)!=1: raise RuntimeError('Import_Batch定位不唯一，拒绝回滚')
 work=[('Error_Log',err_ids)]+work+[('Import_Batch',batch_ids)]
 manifest={'batch_id':batch_id,'apply':ns.apply,'deletion_order':[{'table':t,'records':len(ids)} for t,ids in work]}
 (ROOT/'data/output/T8a_rollback_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 if ns.apply:
  for table,ids in work: delete(table,ids)
 print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
