#!/usr/bin/env python3
"""T8b 关系回填回滚。默认只生成/核验清单；--apply 才清空Link并删除本批次新建日志和批次。"""
from __future__ import annotations
import argparse,json,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/output'; BASE='FCxObLU6yao5jgsciZfcWHKwnjh'
TABLE={'Metric':'tbldKtdIVv8nnTyX','Commission_Tier':'tblkZUoHYwBIvDYe','Target':'tblydZkf17kmzrO0','Error_Log':'tbl4ZpuuOxZacWgj','Import_Batch':'tblHV3JoVR9AEETw'}
def cli(a,p=None,n='rollback'):
 c=['lark-cli','base',*a,'--as','user','--format','json']
 if p is not None:
  f=OUT/'t8b_payloads'/f'{n}.json';f.write_text(json.dumps(p,ensure_ascii=False,separators=(',',':')));c+=['--json','@'+str(f.relative_to(ROOT))]
 r=subprocess.run(c,cwd=ROOT,text=True,capture_output=True,env=os.environ|{'LARKSUITE_CLI_NO_UPDATE_NOTIFIER':'1'})
 d=json.loads(r.stdout)
 if r.returncode or not d.get('ok'):raise RuntimeError(json.dumps({'stdout':d,'stderr':r.stderr},ensure_ascii=False))
 return d
def chunks(x,n=200):
 for i in range(0,len(x),n):yield i//n+1,x[i:i+n]
def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
 plan=json.loads((OUT/'T8b_backfill_plan.json').read_text());res=json.loads((OUT/'T8b_apply_result.json').read_text())['result'];w=res['written']
 manifest={'batch_id':plan['batch_id'],'batch_record_id':res['batch_record_id'],'rollback_scope':{'Metric_Position_ID':len(w['Metric']),'Commission_Tier_Position_ID':len(w['Commission_Tier']),'Target_Channel_ID':len(w['Target']),'Error_Log_delete':len(w['Error_Log']),'Import_Batch_delete':len(w['Import_Batch'])},'method':'Clear only T8b-written relation fields, then delete only T8b-created Error_Log and Import_Batch records. Update_Time is refreshed by rollback and is not restored as a historical value.','apply_required':True}
 (OUT/'T8b_rollback_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 if not a.apply: print(json.dumps({'status':'DRY_RUN_PASSED','manifest':str(OUT/'T8b_rollback_manifest.json'),'scope':manifest['rollback_scope']},ensure_ascii=False));return
 for label,key,field in [('Metric','Metric','Position_ID'),('Commission_Tier','Commission_Tier','Position_ID'),('Target','Target','Channel_ID')]:
  for i,g in chunks(w[key]):cli(['+record-batch-update','--base-token',BASE,'--table-id',TABLE[label]],{'update_records':{rid:{field:None} for rid in g}},f'rollback_{label}_{i}')
 for label,key in [('Error_Log','Error_Log'),('Import_Batch','Import_Batch')]:
  for rid in w[key]:cli(['+record-delete','--base-token',BASE,'--table-id',TABLE[label],'--record-id',rid,'--yes'])
 print(json.dumps({'status':'ROLLED_BACK','scope':manifest['rollback_scope']},ensure_ascii=False))
if __name__=='__main__':main()
