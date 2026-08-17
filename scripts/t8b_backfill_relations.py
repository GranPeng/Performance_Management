#!/usr/bin/env python3
"""T8b 正式库关联回填：先生成可审计计划，--apply 后才写入。

不修改权威 Excel；只使用 T8a 已注册的 Base record_id 作 link 值。
对无法由 D-005/D-006 或在线维护源唯一确定的关联，保留空值并写 Error_Log。
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
BASE='FCxObLU6yao5jgsciZfcWHKwnjh'
T={'Position':'tbldzvsg9Op6pK29','Employee':'tblc59aB4EnSxkQv','Project':'tbl1GO2vR9ZAqPbr','Channel':'tblqOGJknsD2H3bt','Metric':'tbldKtdIVv8nnTyX','Commission_Tier':'tblkZUoHYwBIvDYe','Target':'tblydZkf17kmzrO0','Project_Member':'tblcUUz0oq9MxNLu','Import_Batch':'tblHV3JoVR9AEETw','Error_Log':'tbl4ZpuuOxZacWgj','Old_Project_Member':'tblB8ujzwz3EJsSv'}
OUT=ROOT/'data/output'
BATCH='IB-T8B-REL-20260815-01'
# V04源工作表→T8a Position：每个源工作表恰好一个正式岗位。
SHEET_POSITION={'兴趣电商-运营':'兴趣电商运营','兴趣电商-高级主管':'兴趣电商运营高级主管','兴趣电商-广告投放':'广告投放','兴趣电商-直播中控':'直播中控/运营助理','兴趣电商-主播':'主播','兴趣电商-客服':'电商客服专员','制作部-编导':'内容主管/编导','制作部-视频剪辑':'视频剪辑师','制作部-摄影师':'摄影师'}
CHANNEL_ALIASES={'天猫/淘宝':'天猫淘宝','抖音达人':'达播'}


def stamp(): return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')
def cli(args:list[str], payload:dict|None=None, name='payload')->dict:
    cmd=['lark-cli','base',*args,'--as','user','--format','json']
    if payload is not None:
        p=OUT/'t8b_payloads'/f'{name}.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
        cmd += ['--json','@'+str(p.relative_to(ROOT))]
    env=os.environ|{'LARKSUITE_CLI_NO_UPDATE_NOTIFIER':'1','LARKSUITE_CLI_NO_SKILLS_NOTIFIER':'1'}
    for n in range(5):
        r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,env=env)
        try: body=json.loads(r.stdout)
        except Exception: body={'ok':False,'stdout':r.stdout,'stderr':r.stderr}
        if r.returncode==0 and body.get('ok'): return body
        if 'onOverQPSLimit' in (r.stdout+r.stderr) and n<4: time.sleep(n+1); continue
        raise RuntimeError(json.dumps({'cmd':cmd[:4],'rc':r.returncode,'body':body,'stderr':r.stderr},ensure_ascii=False))
    raise RuntimeError('QPS retry exhausted')
def rows(table:str, fields:list[str])->list[dict]:
    out=[]; off=0
    while True:
        a=['+record-list','--base-token',BASE,'--table-id',table,'--limit','200','--offset',str(off)]
        for f in fields:a += ['--field-id',f]
        d=cli(a)['data']; names=d['fields']; data=d['data']; ids=d['record_id_list']
        if len(data)!=len(ids): raise RuntimeError(f'{table} record/data length mismatch')
        out += [{'record_id':rid,**dict(zip(names,val))} for rid,val in zip(ids,data)]
        if not d.get('has_more'): return out
        if not data: raise RuntimeError(f'{table} empty page with has_more')
        off += len(data)
def chunks(x,n=200):
    for i in range(0,len(x),n):yield i//n+1,x[i:i+n]
def link(rid):return [{'id':rid}]
def tid(sha,row,channel,period): return 'TGT-V60-'+hashlib.sha256(f'V60|{sha}|{row}|{channel}|{period}'.encode()).hexdigest()[:20].upper()
def err(eid,batchrec,objtype,objid,etype,content,now):return {'Error_ID':eid,'Batch_ID':link(batchrec),'Object_Type':objtype,'Object_ID':objid,'Error_Type':etype,'Error_Content':content,'Process_Status':'待处理','Status':'Active','Source':'T8b关联回填|data-engineer','Create_Time':now,'Update_Time':now}

def build():
    now=stamp()
    pos=rows(T['Position'],['Position_ID','Position_Name','Org_ID'])
    emp=rows(T['Employee'],['Employee_ID','Name'])
    pro=rows(T['Project'],['Project_ID','Project_Name'])
    ch=rows(T['Channel'],['Channel_ID','Channel_Name','Channel_Alias'])
    met=rows(T['Metric'],['Metric_ID','Source_Sheet','Metric_Name','Budget_Field_Ref','Position_ID'])
    tier=rows(T['Commission_Tier'],['Commission_Tier_ID','Source_Sheet','Position_ID'])
    targets=rows(T['Target'],['Target_ID','Channel_ID','Metric_ID'])
    old=rows(T['Old_Project_Member'],['姓名','手机号码','人员对照项目','项目所属渠道'])
    posby={r['Position_Name']:r for r in pos}; empby={r['Name']:r for r in emp}; proby={r['Project_Name']:r for r in pro}; chby={r['Channel_Name']:r for r in ch}
    # 账户ID由 T8a 正式表读取，禁止自行生成。
    for n in SHEET_POSITION.values():
        if n not in posby: raise RuntimeError(f'Position not registered: {n}')
    metric_updates=[]; tier_updates=[]
    for r in met:
        pn=SHEET_POSITION.get(r['Source_Sheet'])
        if not pn: raise RuntimeError(f'Metric source sheet not in mapping: {r["Source_Sheet"]}')
        metric_updates.append((r['record_id'],{'Position_ID':link(posby[pn]['record_id']),'Update_Time':now}))
    for r in tier:
        pn=SHEET_POSITION.get(r['Source_Sheet'])
        if not pn: raise RuntimeError(f'Tier source sheet not in mapping: {r["Source_Sheet"]}')
        tier_updates.append((r['record_id'],{'Position_ID':link(posby[pn]['record_id']),'Update_Time':now}))
    # Target ID 由 T7 确定性规则还原；所有9个V60权威渠道必须命中一个T8a Channel record。
    source=json.loads((OUT/'预算目标结构化提取.json').read_text()); sha=source['source']['sha256']
    expected={}
    for item in source['budget_targets']:
        for cb in item['channels']:
            cname=cb['channel']
            if cname not in chby: raise RuntimeError(f'V60 channel not registered in T8a: {cname}')
            for mo in cb['monthly_values']:
                expected[tid(sha,item['source_row'],cname,mo['month'])]=cname
    if len(expected)!=6156 or len(targets)!=6156: raise RuntimeError(f'Target cardinality mismatch expected={len(expected)} actual={len(targets)}')
    target_updates=[]
    for r in targets:
        cname=expected.get(r['Target_ID'])
        if not cname: raise RuntimeError(f'Target_ID not in V60 source: {r["Target_ID"]}')
        target_updates.append((r['record_id'],{'Channel_ID':link(chby[cname]['record_id']),'Update_Time':now}))
    # D-005/006 only identifies V60 rows, not a single Metric: GSV有7个岗位指标、消耗有2个岗位指标。
    gsv=[r for r in met if '主营业务收入=退货后GSV' in (r.get('Budget_Field_Ref') or '')]
    consume=[r for r in met if '广告投流费=消耗' in (r.get('Budget_Field_Ref') or '')]
    if len(gsv)!=7 or len(consume)!=2: raise RuntimeError(f'Unexpected metric candidates GSV={len(gsv)} consumption={len(consume)}')
    # 逐个受影响Target留痕：Metric_ID 保持空，绝不从多候选中猜选一个。
    metric_errors=[]
    for item in source['budget_targets']:
        kind=None
        if item['line_item']=='主营业务收入':kind=('GSV',gsv)
        elif item['line_item']=='渠道投入/广告投流费':kind=('消耗',consume)
        if kind:
            label,cands=kind
            for cb in item['channels']:
                for mo in cb['monthly_values']:
                    x=tid(sha,item['source_row'],cb['channel'],mo['month'])
                    metric_errors.append(('Target',x,'指标映射',f'D-005/D-006已定位{label}预算行，但存在{len(cands)}个候选Metric_ID（{",".join(c["Metric_ID"] for c in cands)}）；Target缺少岗位/项目维度，无法唯一关联，Metric_ID保持空。'))
    # Project_Member：旧表没有Effective_Start。它是强制字段且承载业务生效语义，不能用导入日期伪造。
    pm_records=[]; pm_errors=[]
    for r in old:
        name=r.get('姓名'); project=(r.get('人员对照项目') or [None])[0]; channel=(r.get('项目所属渠道') or [None])[0]
        reasons=[]
        if not name or name not in empby: reasons.append(f'Employee未注册或姓名无法唯一匹配：{name!r}')
        if not project or project not in proby: reasons.append(f'项目缺失/未注册：{project!r}')
        canon=CHANNEL_ALIASES.get(channel,channel)
        if not channel or canon not in chby: reasons.append(f'渠道缺失或非权威映射：{channel!r}')
        reasons.append('旧在线表不含Effective_Start；该字段为Project_Member必填且有业务生效语义，禁止以导入日期代替。')
        pm_errors.append(('Project_Member',r['record_id'],'必填/ID存在性','；'.join(reasons)))
    assert not pm_records and len(pm_errors)==101
    plan={'task':'T8b','batch_id':BATCH,'created_at':now,'base_token':BASE,'tables':T,'source_counts':{'Metric':len(met),'Commission_Tier':len(tier),'Target':len(targets),'Old_Project_Member':len(old)},'updates':{'Metric_Position_ID':len(metric_updates),'Commission_Tier_Position_ID':len(tier_updates),'Target_Channel_ID':len(target_updates),'Target_Metric_ID':0,'Project_Member_create':0},'unresolved':{'Target_Metric_ID':len(metric_errors),'Project_Member':len(pm_errors)},'mapping_rules':{'V04_source_sheet_to_position':SHEET_POSITION,'channel_aliases':CHANNEL_ALIASES,'metric_rule':'D-005/D-006 row-level mapping is ambiguous without Target position/project grain; no Metric_ID written.'},'payloads':{'metric_updates':metric_updates,'tier_updates':tier_updates,'target_updates':target_updates,'metric_errors':metric_errors,'project_member_errors':pm_errors}}
    return plan

def apply(plan):
    now=plan['created_at']; source='T8b关联回填|T8a主数据注册表|V04/V60/在职人员对照项目'
    batch={'Batch_ID':BATCH,'Batch_Type':'MASTER_DATA','Total_Count':6344,'Success_Count':0,'Fail_Count':0,'Import_Time':now,'Create_Time':now,'Update_Time':now,'Operator':'data-engineer/T8b-ETL','Source':source,'Source_Type':'Excel文件','Source_File':'V04+V60+在职人员对照项目','Source_SHA256':'V04:5342d3dd…3250;V60:65d3c2a6…5943','Status':'Running'}
    b=cli(['+record-batch-create','--base-token',BASE,'--table-id',T['Import_Batch']],{'create_records':[batch]},'import_batch')
    bid=b['data']['record_id_list'][0]; written={'Import_Batch':[bid],'Metric':[],'Commission_Tier':[],'Target':[],'Error_Log':[],'Project_Member':[]}
    try:
        for label,table,key in [('Metric',T['Metric'],'metric_updates'),('Commission_Tier',T['Commission_Tier'],'tier_updates'),('Target',T['Target'],'target_updates')]:
            pairs=plan['payloads'][key]
            for i,g in chunks(pairs):
                payload={'update_records':{rid:fields for rid,fields in g}}
                out=cli(['+record-batch-update','--base-token',BASE,'--table-id',table],payload,f'{label.lower()}_update_{i}')
                if out['data'].get('ignored_fields'): raise RuntimeError(f'{label} ignored_fields {out["data"]["ignored_fields"]}')
                written[label] += [rid for rid,_ in g]
        errors=[]
        for ix,(typ,obj,et,content) in enumerate(plan['payloads']['metric_errors']+plan['payloads']['project_member_errors'],1):
            eid='ERR-T8B-'+hashlib.sha256(f'{BATCH}|{typ}|{obj}|{et}|{content}'.encode()).hexdigest()[:16].upper()
            errors.append(err(eid,bid,typ,obj,et,content,now))
        for i,g in chunks(errors):
            out=cli(['+record-batch-create','--base-token',BASE,'--table-id',T['Error_Log']],{'create_records':g},f'errors_{i}')
            got=out['data']['record_id_list'];
            if len(got)!=len(g): raise RuntimeError(f'Error_Log create count mismatch {len(got)}/{len(g)}')
            written['Error_Log'] += got
        # 6243 rows have all requested unambiguous links: 45+42+6156; 101 Project_Member source rows blocked by required business date.
        cli(['+record-batch-update','--base-token',BASE,'--table-id',T['Import_Batch']],{'update_records':{bid:{'Success_Count':6243,'Fail_Count':101,'Update_Time':stamp(),'Status':'Partial'}}},'import_batch_final')
    except Exception:
        (OUT/'T8b_apply_failure.json').write_text(json.dumps({'batch_record_id':bid,'written':written},ensure_ascii=False,indent=2)+'\n')
        raise
    return {'batch_record_id':bid,'written':written}
def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    plan=build(); (OUT/'T8b_backfill_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    if not a.apply:
        print(json.dumps({'status':'PREFLIGHT_PASSED','plan':str(OUT/'T8b_backfill_plan.json'),'updates':plan['updates'],'unresolved':plan['unresolved']},ensure_ascii=False));return
    result=apply(plan); (OUT/'T8b_apply_result.json').write_text(json.dumps({'plan_summary':{k:plan[k] for k in ('batch_id','updates','unresolved','source_counts')},'result':result},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'APPLY_COMPLETED','result':result},ensure_ascii=False))
if __name__=='__main__':main()
