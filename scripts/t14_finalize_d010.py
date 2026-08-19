#!/usr/bin/env python3
"""T14：对已写入且读回通过的 D-010 用例补全批次状态、执行证据和回滚清单。"""
import json, shutil, subprocess
from datetime import datetime
from pathlib import Path

BASE="FCxObLU6yao5jgsciZfcWHKwnjh"; SOURCE="SIMULATED_T14_D010_NONZERO"
ROOT=Path(__file__).resolve().parents[1]
CLI=shutil.which("lark-cli") or str(Path.home()/".local/bin/lark-cli")
TABLE={"Performance_Result":"tbl6tFtVKExFUTWo","Actual":"tbli9VhcUFjVDeNd","Import_Batch":"tblHV3JoVR9AEETw","Project":"tbl1GO2vR9ZAqPbr"}
EXECUTION=ROOT/"data/output/T14_D010非零比例豁免执行结果.json"
ROLLBACK=ROOT/"data/output/T14_D010非零比例豁免回滚清单.json"
def call(args):
 p=subprocess.run([CLI,"base",*args,"--as","user"],text=True,capture_output=True); d=json.loads(p.stdout)
 if p.returncode or not d.get("ok"): raise RuntimeError(json.dumps(d,ensure_ascii=False))
 return d["data"]
def rows(table,fields):
 out=[]; off=0
 while True:
  args=["+record-list","--base-token",BASE,"--table-id",TABLE[table],"--limit","200","--format","json","--offset",str(off)]
  for f in fields: args += ["--field-id",f]
  d=call(args)
  for rid,v in zip(d["record_id_list"],d["data"]): out.append({**dict(zip(d["fields"],v)),"_record_id":rid})
  if not d.get("has_more"): return out
  off += len(d["record_id_list"])
def n(v): return None if v in (None,"") else float(v)
def main():
 r=[x for x in rows("Performance_Result",["Source","Result_ID","Project_Run_Days","Is_Exempt","Auto_Score","Weighted_Score","Commission_Base","Commission_Ratio","Commission_Amount"]) if x.get("Source")==SOURCE]
 a=[x for x in rows("Actual",["Source","Actual_ID"]) if x.get("Source")==SOURCE]
 b=[x for x in rows("Import_Batch",["Source","Batch_ID"]) if x.get("Source")==SOURCE]
 p=[x for x in rows("Project",["Source","Project_ID"]) if x.get("Source")==SOURCE]
 if not (len(r)==len(a)==len(p)==1 and len(b)==2): raise RuntimeError(f"T14 来源记录数量异常 r/a/b/p={len(r)}/{len(a)}/{len(b)}/{len(p)}")
 x=r[0]; base,ratio,amount,days,auto,weighted=n(x["Commission_Base"]),n(x["Commission_Ratio"]),n(x["Commission_Amount"]),n(x["Project_Run_Days"]),n(x["Auto_Score"]),n(x["Weighted_Score"])
 if None in (base,ratio,amount,days,auto,weighted): raise RuntimeError(f"T14 读回存在空值：{x}")
 checks={"project_run_days_lt_90":days<90,"is_exempt":str(x["Is_Exempt"]).lower()=="true","auto_score_100":auto==100,"weighted_score_0":weighted==0,"ratio_nonzero":ratio>0,"amount_equals_base_times_ratio":abs(amount-base*ratio)<1e-6,"amount_positive":amount>0}
 if not all(checks.values()): raise RuntimeError(f"T14 读回复核失败：{checks}; {x}")
 now=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
 call(["+record-batch-update","--base-token",BASE,"--table-id",TABLE["Import_Batch"],"--json",json.dumps({"update_records":{z["_record_id"]:{"Success_Count":1,"Fail_Count":0,"Status":"Success","Update_Time":now} for z in b}},ensure_ascii=False)])
 execution={"task":"T14","status":"APPLY_PASSED","source":SOURCE,"case_id":"T14-D010-EXEMPT-NONZERO-01","finalized_at":now,"batches":b,"created":{"project_record_id":p[0]["_record_id"],"actual_record_id":a[0]["_record_id"],"performance_result_record_id":x["_record_id"]},"read_back":x,"assertions":checks,"note":"首次写入后的类型比较失败仅阻断执行器收尾；本脚本以同一只读回值复核后补全成功批次状态，未改动业务数据。"}
 EXECUTION.write_text(json.dumps(execution,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 rollback={"task":"T14","rollback_scope":"仅删除 T14 创建的 SIMULATED Project、两批次、Actual 和 Performance_Result；不修改既有业务记录或公式","execution":EXECUTION.name,"project_record_id":p[0]["_record_id"],"actual_record_ids":[a[0]["_record_id"]],"performance_result_record_ids":[x["_record_id"]],"import_batch_record_ids":[z["_record_id"] for z in b],"rollback_order":["Performance_Result","Actual","Import_Batch","Project"]}
 ROLLBACK.write_text(json.dumps(rollback,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":"FINALIZE_PASSED","execution":str(EXECUTION.relative_to(ROOT)),"rollback":str(ROLLBACK.relative_to(ROOT)),"assertions":checks},ensure_ascii=False))
if __name__=="__main__": main()
