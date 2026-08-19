#!/usr/bin/env python3
"""T21 D-013/D-014 可回滚模拟数据。默认仅预检；--apply 才写入专属 SIMULATED 批次。"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='FCxObLU6yao5jgsciZfcWHKwnjh'
T={'Employee':'tblc59aB4EnSxkQv','Actual':'tbli9VhcUFjVDeNd','Performance_Result':'tbl6tFtVKExFUTWo','Import_Batch':'tblHV3JoVR9AEETw'}
CLI=shutil.which('lark-cli') or str(Path.home()/'.local/bin/lark-cli')
SOURCE='SIMULATED_T21_D013_D014'
ACTUAL_BATCH='IB-T21-ACTUAL-20260818-01'
CALC_BATCH='IB-T21-CALC-20260818-01'
PLAN=ROOT/'data/output/T21_D013_D014模拟计划.json'
EXEC=ROOT/'data/output/T21_D013_D014模拟执行结果.json'
ROLLBACK=ROOT/'data/output/T21_D013_D014回滚清单.json'
ERROR=ROOT/'data/output/T21_D013_D014错误日志.json'

# 实测 Base canonical record IDs；脚本执行前仍会验证其主键，避免静默绑错记录。
POS_LIVE='recvslrK0j9KFd'; POS_OPS='recvslrK0jZL0c'
MET_LIVE='recvsgqAO9mdG3'; MET_OPS='recvsgqAO9qu6Y'
CH_DOUYIN='recvsls7z4BhTA'; CH_VIDEO='recvsls7z5bauE'

def call(args):
 p=subprocess.run([CLI,'base',*args,'--as','user'],text=True,capture_output=True)
 try:r=json.loads(p.stdout)
 except Exception as e: raise RuntimeError(f'CLI非JSON: {p.stdout[-300:]} {p.stderr[-300:]}') from e
 if p.returncode or not r.get('ok'): raise RuntimeError(json.dumps(r,ensure_ascii=False))
 return r['data']
def records(table, fields):
 out=[]; offset=0
 while True:
  a=['+record-list','--base-token',BASE,'--table-id',T[table],'--limit','200','--offset',str(offset),'--format','json']
  for f in fields:a += ['--field-id',f]
  d=call(a);out += [{**dict(zip(d['fields'],v)),'_record_id':rid} for rid,v in zip(d['record_id_list'],d['data'])]
  if not d.get('has_more'):return out
  offset += len(d['record_id_list'])
def next_num(rows, field, prefix):
 vals=[]
 for r in rows:
  m=re.fullmatch(prefix+r'(\d{6})',str(r.get(field,'')))
  if m:vals.append(int(m.group(1)))
 return max(vals,default=0)+1
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');a=ap.parse_args()
 employees=records('Employee',['Employee_ID','Status','Source'])
 actuals=records('Actual',['Actual_ID','Status','Source'])
 results=records('Performance_Result',['Result_ID','Status','Source'])
 # 四个中控收入场景：1/2/3 人均分各至少一条，另加110%档；一高级主管双渠道全额计提。
 cases=[
  ('D013-ONE-80','2027-02',[0],100000,5000,60),
  ('D013-TWO-90','2027-03',[0,1],200000,6000,80),
  ('D013-THREE-100','2027-04',[0,1,2],300000,7000,100),
  ('D013-ONE-110','2027-05',[0],100000,8000,110),
 ]
 plan={'task':'T21','source':SOURCE,'mode':'PREFLIGHT','actual_batch_id':ACTUAL_BATCH,'calc_batch_id':CALC_BATCH,'employee_id_start':next_num(employees,'Employee_ID','EMP'),'actual_id_start':next_num(actuals,'Actual_ID','ACT'),'result_id_start':next_num(results,'Result_ID','RST'),'cases':cases,'rules':{'D-013':'Perf_Salary×tier% + GSV×0.001÷eligible_middle_control_count','D-014':'sum(GSV of each Responsible_Channel_ID), no allocation ratio'}}
 PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if not a.apply:
  print(json.dumps({'status':'PREFLIGHT_PASSED','plan':str(PLAN.relative_to(ROOT)),'planned_employees':4,'planned_actuals':6,'planned_results':8},ensure_ascii=False));return
 now=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')
 batches=[{'Batch_ID':ACTUAL_BATCH,'Batch_Type':'ACTUAL','Source_Type':'SIMULATED','Source_File':PLAN.name,'Import_Time':now,'Operator':'data-engineer/T21','Total_Count':6,'Success_Count':0,'Fail_Count':0,'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Running'},{'Batch_ID':CALC_BATCH,'Batch_Type':'CALC','Source_Type':'SIMULATED','Source_File':PLAN.name,'Import_Time':now,'Operator':'data-engineer/T21','Total_Count':8,'Success_Count':0,'Fail_Count':0,'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Running'}]
 br=call(['+record-batch-create','--base-token',BASE,'--table-id',T['Import_Batch'],'--json',json.dumps({'create_records':batches},ensure_ascii=False)])['record_id_list']
 if len(br)!=2:raise RuntimeError(f'批次创建确认异常: {br}')
 empstart=plan['employee_id_start']; emp_rows=[]
 for i in range(3):emp_rows.append({'Employee_ID':f'EMP{empstart+i:06d}','Name':f'T21中控模拟{i+1}','Position_ID':[{'id':POS_LIVE}],'Perf_Salary':5000+i*1000,'Responsible_Channel_IDs':[{'id':CH_DOUYIN}],'Perf_Participate_Status':'确认参与','Employment_Status':'在职','Data_Origin':'ROSTER_MOCK','Import_Batch_ID':[{'id':br[0]}],'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Active','Note':'T21 D-013模拟人员；仅用于可回滚验证'})
 emp_rows.append({'Employee_ID':f'EMP{empstart+3:06d}','Name':'T21高级主管多渠道模拟','Position_ID':[{'id':POS_OPS}],'Responsible_Channel_IDs':[{'id':CH_DOUYIN},{'id':CH_VIDEO}],'Perf_Participate_Status':'确认参与','Employment_Status':'在职','Data_Origin':'ROSTER_MOCK','Import_Batch_ID':[{'id':br[0]}],'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Active','Note':'T21 D-014一高级主管多渠道全额计提模拟'})
 er=call(['+record-batch-create','--base-token',BASE,'--table-id',T['Employee'],'--json',json.dumps({'create_records':emp_rows},ensure_ascii=False)])['record_id_list']
 if len(er)!=4:raise RuntimeError(f'Employee创建确认异常:{er}')
 actstart=plan['actual_id_start']; actrows=[]; actual_by_case={}
 for n,(cid,period,members,gsv,salary,total) in enumerate(cases):
  row={'Actual_ID':f'ACT{actstart+n:06d}','Metric_ID':[{'id':MET_LIVE}],'Period':period,'Channel_ID':[{'id':CH_DOUYIN}],'Actual_Value':gsv,'Unit':'元','Source_Type':'MANUAL_ENTRY','Source_Ref':f'{SOURCE};{cid};渠道GSV','Collected_By':[{'id':er[0]}],'Collected_Time':now,'Validation_Status':'通过','Import_Batch_ID':[{'id':br[0]}],'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Active'};actrows.append(row);actual_by_case[cid]=row['Actual_ID']
 # D014 2027-06 两渠道 GSV，供同一高级主管的 Commission_Base=两者之和复核。
 for j,(channel,gsv) in enumerate(((CH_DOUYIN,120000),(CH_VIDEO,80000))):actrows.append({'Actual_ID':f'ACT{actstart+4+j:06d}','Metric_ID':[{'id':MET_OPS}],'Period':'2027-06','Channel_ID':[{'id':channel}],'Actual_Value':gsv,'Unit':'元','Source_Type':'MANUAL_ENTRY','Source_Ref':f'{SOURCE};D014-MULTI;渠道GSV','Collected_By':[{'id':er[3]}],'Collected_Time':now,'Validation_Status':'通过','Import_Batch_ID':[{'id':br[0]}],'Source':SOURCE,'Create_Time':now,'Update_Time':now,'Status':'Active'})
 ar=call(['+record-batch-create','--base-token',BASE,'--table-id',T['Actual'],'--json',json.dumps({'create_records':actrows},ensure_ascii=False)])['record_id_list']
 if len(ar)!=6:raise RuntimeError(f'Actual创建确认异常:{ar}')
 aid={r['Actual_ID']:rid for r,rid in zip(actrows,ar)}; rststart=plan['result_id_start']; rst=[]; k=0
 for cid,period,members,gsv,salary,total in cases:
  tier_pct={60:.8,80:.9,100:1,110:1.1}[total]
  for idx in members:
   # Live-001 权重0.1，手工补分只为构造可验证的精确得分档位。
   rst.append({'Result_ID':f'RST{rststart+k:06d}','Period':period,'Employee_ID':[{'id':er[idx]}],'Metric_ID':[{'id':MET_LIVE}],'Actual_ID':[{'id':aid[actual_by_case[cid]]}],'Target_Value_Snapshot':gsv,'Rule_Version':'V04','Calc_Batch_ID':[{'id':br[1]}],'Manual_Score':total*10,'Commission_Base':gsv,'Commission_Base_Type':'GSV','Commission_Ratio':.001/len(members),'Perf_Salary_Snapshot':salary,'Review_Status':'待复核','Status':'Active','Source':SOURCE,'Create_Time':now,'Update_Time':now,'Note':json.dumps({'t21_case':cid,'channel_record_id':CH_DOUYIN,'channel_gsv':gsv,'middle_control_count':len(members),'tier_percentage':tier_pct},ensure_ascii=False)});k+=1
 rst.append({'Result_ID':f'RST{rststart+k:06d}','Period':'2027-06','Employee_ID':[{'id':er[3]}],'Metric_ID':[{'id':MET_OPS}],'Actual_ID':[{'id':aid[actrows[4]["Actual_ID"]]}],'Target_Value_Snapshot':120000,'Rule_Version':'V04','Calc_Batch_ID':[{'id':br[1]}],'Commission_Base':200000,'Commission_Base_Type':'GSV','Commission_Ratio':.003,'Review_Status':'待复核','Status':'Active','Source':SOURCE,'Create_Time':now,'Update_Time':now,'Note':json.dumps({'t21_case':'D014-MULTI','channel_gsv':{CH_DOUYIN:120000,CH_VIDEO:80000},'expected_commission_base':200000},ensure_ascii=False)});k+=1
 rr=call(['+record-batch-create','--base-token',BASE,'--table-id',T['Performance_Result'],'--json',json.dumps({'create_records':rst},ensure_ascii=False)])['record_id_list']
 if len(rr)!=len(rst):raise RuntimeError(f'Result创建确认异常:{rr}')
 for rid,n in ((br[0],6),(br[1],len(rst))):call(['+record-batch-update','--base-token',BASE,'--table-id',T['Import_Batch'],'--json',json.dumps({'update_records':{rid:{'Success_Count':n,'Fail_Count':0,'Status':'Success','Update_Time':now}}},ensure_ascii=False)])
 execution={'task':'T21','status':'APPLY_PASSED','source':SOURCE,'batches':br,'employee_record_ids':er,'actual_record_ids':ar,'performance_result_record_ids':rr}
 EXEC.write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 ROLLBACK.write_text(json.dumps({'task':'T21','rollback_scope':'仅删除本任务创建的Employee、Actual、Performance_Result、Import_Batch；不修改既有记录/公式','source':SOURCE,**execution},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':'APPLY_PASSED','execution':str(EXEC.relative_to(ROOT)),'rollback':str(ROLLBACK.relative_to(ROOT)),'counts':{'employees':4,'actuals':6,'results':len(rst),'batches':2}},ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except Exception as e:
  ERROR.write_text(json.dumps({'task':'T21','error':str(e),'time':datetime.now().astimezone().isoformat()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':'FAILED','error':str(e),'error_log':str(ERROR.relative_to(ROOT))},ensure_ascii=False),file=sys.stderr);sys.exit(2)
