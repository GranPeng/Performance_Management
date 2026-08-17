#!/usr/bin/env python3
"""T8a 主数据 ETL：计划可审计、写入幂等、失败显式记录。"""
import argparse, hashlib, json, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
T = {"Organization":"tblc6rU0d2bHMVnZ","Position":"tbldzvsg9Op6pK29","Employee":"tblc59aB4EnSxkQv","Project":"tbl1GO2vR9ZAqPbr","Channel":"tblqOGJknsD2H3bt","Import_Batch":"tblHV3JoVR9AEETw","Error_Log":"tbl4ZpuuOxZacWgj"}
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data/raw"
OUT=ROOT/"data/output"
NOW=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
TODAY=datetime.now().astimezone().strftime("%Y-%m-%d")
AUTH_CHANNELS=["抖音","视频号","天猫淘宝","拼多多","京东POP","京东自营","达播","私域","外部分销"]
CHANNEL_ALIASES={"天猫淘宝":"天猫/淘宝","京东POP":"京东pop","达播":"抖音达人","外部分销":""}

def val(x):
    if isinstance(x,list): return x[0] if x else None
    return x

def norm(x):
    if x is None: return None
    x=str(x).strip().replace("　","")
    return x or None

def load(name):
    p=RAW/name
    d=json.loads(p.read_text())['data']
    fields=d['fields']
    rows=[dict(zip(fields,row)) for row in d['data']]
    return rows, hashlib.sha256(p.read_bytes()).hexdigest()

def cli(args, input_json=None):
    cmd=['lark-cli','base']+args+['--as','user']
    r=subprocess.run(cmd,input=input_json,text=True,capture_output=True)
    if r.returncode:
        raise RuntimeError(f"CLI failed ({r.returncode}): {' '.join(cmd)}\n{r.stderr}\n{r.stdout}")
    try: return json.loads(r.stdout)
    except Exception as e: raise RuntimeError(f"CLI returned non-JSON: {r.stdout}") from e

def list_records(table):
    r=cli(['+record-list','--base-token',BASE,'--table-id',T[table],'--format','json','--limit','200'])
    d=r['data']; return [dict(zip(d['fields'],row)) for row in d['data']], d.get('record_id_list',[])

def batch_create(table, records):
    ids=[]
    for i in range(0,len(records),200):
        payload=json.dumps({'create_records':records[i:i+200]},ensure_ascii=False)
        r=cli(['+record-batch-create','--base-token',BASE,'--table-id',T[table],'--json',payload])
        ids += r['data'].get('record_id_list',[])
    if len(ids)!=len(records): raise RuntimeError(f"{table} batch result ID count mismatch {len(ids)} != {len(records)}")
    return ids

def ensure_records(table, records, id_field):
    """Create an empty target once, or resume only when its stable business-ID set exactly matches the plan."""
    existing, recids=list_records(table)
    if not existing:
        batch_create(table, records)
        existing, recids=list_records(table)
    record_map={row.get(id_field):rid for row,rid in zip(existing,recids)}
    planned={r[id_field] for r in records}
    if set(record_map) != planned or len(record_map) != len(records):
        raise RuntimeError(f'{table} 已有记录与本迁移计划不一致；停止以防止重复或静默修改。existing={len(record_map)} planned={len(records)}')
    return record_map

def single_create(table, record):
    r=cli(['+record-upsert','--base-token',BASE,'--table-id',T[table],'--json',json.dumps(record,ensure_ascii=False)])
    created=r['data']['record']
    return created.get('record_id') or created.get('id')

def link(record_id): return [{'id':record_id}]

def source_meta(sha): return f"旧Base原型只读快照；D-001/D-008；SHA256={sha}"

def build_plan():
    roster, roster_sha=load('t8_roster.json')
    org_rows, org_sha=load('t8_org.json')
    pc_rows, pc_sha=load('t8_project_channel.json')
    errors=[]
    # Department tree: source rows + roster; model has only level 1/2, so team/group is intentionally excluded.
    roots=set(); seconds=set()
    for r in org_rows:
        root=norm(val(r['一级部门'])); sec=norm(val(r['二级部门']))
        if root: roots.add(root)
        if root and sec: seconds.add((root,sec))
    for r in roster:
        root=norm(val(r['一级部门'])); sec=norm(val(r['二级部门']))
        if root: roots.add(root)
        if root and sec: seconds.add((root,sec))
    orgs=[]
    for i,name in enumerate(sorted(roots),1): orgs.append({'Org_ID':f'ORG{i:06d}','Org_Name':name,'parent_key':None,'Org_Level':1})
    root_ids={x['Org_Name']:x['Org_ID'] for x in orgs}
    for j,(root,name) in enumerate(sorted(seconds),len(orgs)+1): orgs.append({'Org_ID':f'ORG{j:06d}','Org_Name':name,'parent_key':root,'Org_Level':2})
    sec_ids={(x['parent_key'],x['Org_Name']):x['Org_ID'] for x in orgs if x['Org_Level']==2}
    # Position grain: distinct role + root + second department. This prevents same role under different departments from being merged.
    pos_map={}
    position_source=[]
    for src, rows in [('组织架构表',org_rows),('花名册',roster)]:
        for r in rows:
            role=norm(val(r['岗位职务'] if '岗位职务' in r else r['职务']))
            root=norm(val(r['一级部门'])); sec=norm(val(r['二级部门']))
            grade=norm(val(r['对应职级'] if '对应职级' in r else r['职级']))
            family=norm(val(r['对应序列'] if '对应序列' in r else r['序列']))
            if not role or not root or not sec:
                errors.append({'Object_Type':'Position','Object_ID':role or 'UNKNOWN','Error_Type':'必填','Error_Content':f'{src}缺少岗位或一级/二级部门，未注册'})
                continue
            key=(role,root,sec)
            ent=pos_map.setdefault(key,{'Position_Name':role,'root':root,'sec':sec,'grades':set(),'families':set(),'sources':set()})
            if grade: ent['grades'].add(grade)
            if family: ent['families'].add(family)
            ent['sources'].add(src)
    positions=[]
    for n,key in enumerate(sorted(pos_map),1):
        e=pos_map[key]; oid=sec_ids.get((e['root'],e['sec']))
        if not oid:
            errors.append({'Object_Type':'Position','Object_ID':e['Position_Name'],'Error_Type':'ID存在性','Error_Content':f'无法找到二级部门 {e["root"]}/{e["sec"]} 的Org_ID，未注册'})
            continue
        positions.append({'Position_ID':f'POS{n:06d}','Position_Name':e['Position_Name'],'root':e['root'],'sec':e['sec'],'Org_ID':oid,'Grade':'、'.join(sorted(e['grades'])) or None,'Job_Family':'、'.join(sorted(e['families'])) or None,'sources':sorted(e['sources'])})
    pos_exact={(p['Position_Name'],p['root'],p['sec']):p['Position_ID'] for p in positions}
    # Projects from project-channel table. Name/Brand are display only; identity is registered ID.
    project_map={}
    for r in pc_rows:
        name=norm(val(r['产品序列'])); brand=norm(val(r['品牌']))
        if name: project_map[name]=brand
        else: errors.append({'Object_Type':'Project','Object_ID':'UNKNOWN','Error_Type':'必填','Error_Content':'项目渠道检索存在空产品序列，未注册'})
    projects=[{'Project_ID':f'PROJ{i:06d}','Project_Name':name,'Brand':brand} for i,(name,brand) in enumerate(sorted(project_map.items()),1)]
    # Channels strictly authoritative list; all source distinct non-authoritative values are explicit warning errors.
    source_channels=sorted({norm(val(r['项目对照渠道'])) for r in pc_rows if norm(val(r['项目对照渠道']))})
    channels=[{'Channel_ID':f'CH{i:06d}','Channel_Name':n,'Channel_Alias':CHANNEL_ALIASES.get(n)} for i,n in enumerate(AUTH_CHANNELS,1)]
    authset=set(AUTH_CHANNELS)|{'天猫/淘宝'}
    for n in source_channels:
        if n not in authset:
            errors.append({'Object_Type':'Channel','Object_ID':n,'Error_Type':'渠道映射','Error_Content':f'旧项目渠道检索出现非V60权威渠道“{n}”，按任务要求不注册；待业务确认映射'})
    # Employee: 82 roster rows. Name not used as relational key. Manager mapping deferred to immutable Employee_ID only after registration.
    employees=[]
    for i,r in enumerate(roster,1):
        name=norm(r['姓名']); root=norm(val(r['一级部门'])); sec=norm(val(r['二级部门'])); role=norm(val(r['职务']))
        pid=pos_exact.get((role,root,sec)); oid=sec_ids.get((root,sec))
        if not name or not pid or not oid:
            errors.append({'Object_Type':'Employee','Object_ID':name or f'ROW{i}','Error_Type':'ID存在性','Error_Content':f'无法映射Org_ID或Position_ID：部门={root}/{sec}，岗位={role}；该人员未导入'})
            continue
        hire=norm(r['入职日期']); hire=hire[:10] if hire else None
        if not hire:
            errors.append({'Object_Type':'Employee','Object_ID':name,'Error_Type':'必填','Error_Content':'花名册入职日期为空；该人员未导入'})
            continue
        perf=norm(r['是否参与绩效考核']) or '待确认'
        employees.append({'Employee_ID':f'EMP{i:06d}','Name':name,'Org_ID':oid,'Position_ID':pid,'Hire_Date':hire,'Employment_Status':'在职','Perf_Participate_Status':('确认参与' if perf in ('是','参与') else '确认不参与' if perf in ('否','不参与') else '待确认'),'manager_name':norm(r['直属上级']),'source_row':i})
    return {'orgs':orgs,'positions':positions,'projects':projects,'channels':channels,'employees':employees,'errors':errors,'sha':{'roster':roster_sha,'org':org_sha,'project_channel':pc_sha},'source_counts':{'roster':len(roster),'org':len(org_rows),'project_channel':len(pc_rows)}}

def write_plan(plan):
    OUT.mkdir(parents=True,exist_ok=True)
    serial={k:v for k,v in plan.items() if k not in ('orgs','positions','projects','channels','employees')}
    serial.update({k:plan[k] for k in ('orgs','positions','projects','channels','employees')})
    (OUT/'T8a_import_plan.json').write_text(json.dumps(serial,ensure_ascii=False,indent=2))

def run(plan):
    # Every entity is created only if empty; retries are allowed solely when exact planned business IDs are already present.
    batch_id='IB-T8A-'+hashlib.sha256(json.dumps(plan['sha'],sort_keys=True).encode()).hexdigest()[:16].upper()
    batch={'Batch_ID':batch_id,'Batch_Type':'MASTER_DATA','Source_Type':'Base原型只读快照','Source_File':'tblK13ENF7v5EwYg,tblIeQRH5U7Ip8b5,tbl6JGBru8LLWV52','Source_SHA256':hashlib.sha256(json.dumps(plan['sha'],sort_keys=True).encode()).hexdigest(),'Import_Time':NOW,'Operator':'data-engineer/T8a','Total_Count':len(plan['orgs'])+len(plan['positions'])+len(plan['projects'])+len(plan['channels'])+len(plan['employees']),'Success_Count':0,'Fail_Count':len(plan['errors']),'Source':'T8a主数据ETL','Create_Time':NOW,'Update_Time':NOW,'Status':'Running'}
    batch_rows,batch_recids=list_records('Import_Batch')
    prior_batch={row.get('Batch_ID'):rid for row,rid in zip(batch_rows,batch_recids)}
    if batch_id in prior_batch:
        batch_rec=prior_batch[batch_id]
    else:
        batch_rec=single_create('Import_Batch',batch)
    if not batch_rec:
        raise RuntimeError('Import_Batch 创建未返回可用 record_id，已停止以避免不可追踪写入')
    common={'Source':'T8a主数据ETL','Create_Time':NOW,'Update_Time':NOW,'Status':'Active'}
    # Org first; parent links updated only after all stable record IDs have been registered.
    org_payload=[{**common,'Org_ID':x['Org_ID'],'Org_Name':x['Org_Name'],'Org_Level':x['Org_Level'],'Effective_Start':TODAY} for x in plan['orgs']]
    org_record_by_id=ensure_records('Organization',org_payload,'Org_ID')
    for x in plan['orgs']:
        if x['parent_key']:
            parent_business_id=next(y['Org_ID'] for y in plan['orgs'] if y['Org_Name']==x['parent_key'] and y['Org_Level']==1)
            cli(['+record-upsert','--base-token',BASE,'--table-id',T['Organization'],'--record-id',org_record_by_id[x['Org_ID']],'--json',json.dumps({'Parent_Org_ID':link(org_record_by_id[parent_business_id]),'Update_Time':NOW},ensure_ascii=False)])
    pos_payload=[{**common,'Position_ID':x['Position_ID'],'Position_Name':x['Position_Name'],'Org_ID':link(org_record_by_id[x['Org_ID']]),'Job_Family':x['Job_Family'],'Grade':x['Grade'],'Version':'V04'} for x in plan['positions']]
    pos_record_by_id=ensure_records('Position',pos_payload,'Position_ID')
    project_payload=[{**common,**x} for x in plan['projects']]; ensure_records('Project',project_payload,'Project_ID')
    channel_payload=[{**common,**x,'Is_V60_Authoritative':True} for x in plan['channels']]; ensure_records('Channel',channel_payload,'Channel_ID')
    emp_payload=[{**common,'Employee_ID':x['Employee_ID'],'Name':x['Name'],'Org_ID':link(org_record_by_id[x['Org_ID']]),'Position_ID':link(pos_record_by_id[x['Position_ID']]),'Hire_Date':x['Hire_Date'],'Employment_Status':x['Employment_Status'],'Perf_Participate_Status':x['Perf_Participate_Status'],'Data_Origin':'ROSTER_MOCK','Import_Batch_ID':link(batch_rec)} for x in plan['employees']]
    emp_rec_by_id=ensure_records('Employee',emp_payload,'Employee_ID')
    # Direct manager: use a name only to resolve original roster display field into an Employee_ID, then write a link by record ID.
    names=defaultdict(list)
    for x in plan['employees']: names[x['Name']].append(x)
    manager_errors=[]
    for x in plan['employees']:
        candidates=names.get(x['manager_name'],[])
        if x['manager_name'] and len(candidates)==1:
            cli(['+record-upsert','--base-token',BASE,'--table-id',T['Employee'],'--record-id',emp_rec_by_id[x['Employee_ID']],'--json',json.dumps({'Direct_Manager_ID':link(emp_rec_by_id[candidates[0]['Employee_ID']]),'Update_Time':NOW},ensure_ascii=False)])
        elif x['manager_name']:
            manager_errors.append({'Object_Type':'Employee','Object_ID':x['Employee_ID'],'Error_Type':'ID存在性','Error_Content':f'直属上级“{x["manager_name"]}”未能唯一解析为Employee_ID；未写入Direct_Manager_ID'})
    errors=plan['errors']+manager_errors
    # Error_Log is explicit, linked to the batch using stable record id.
    err_filter={'logic':'and','conditions':[['Batch_ID','intersects',[{'id':batch_rec}]]]}
    # record-list supports a batch link predicate; an existing exact count means a retry must not duplicate audit records.
    r=cli(['+record-list','--base-token',BASE,'--table-id',T['Error_Log'],'--format','json','--limit','200','--filter-json',json.dumps(err_filter,ensure_ascii=False)])['data']
    prior_error_ids=r.get('record_id_list',[])
    if prior_error_ids and len(prior_error_ids)!=len(errors):
        raise RuntimeError(f'本批已有 Error_Log 数量{len(prior_error_ids)}与计划异常数{len(errors)}不一致，停止防止审计日志重复或缺失')
    if not prior_error_ids:
        existing_err,_=list_records('Error_Log'); start=len(existing_err)+1
        err_payload=[{'Error_ID':f'ERR{i:06d}','Batch_ID':link(batch_rec),**e,'Process_Status':'待处理','Source':'T8a主数据ETL','Create_Time':NOW,'Update_Time':NOW,'Status':'Active'} for i,e in enumerate(errors,start)]
        if err_payload: batch_create('Error_Log',err_payload)
    success=len(plan['orgs'])+len(plan['positions'])+len(plan['projects'])+len(plan['channels'])+len(plan['employees'])
    cli(['+record-upsert','--base-token',BASE,'--table-id',T['Import_Batch'],'--record-id',batch_rec,'--json',json.dumps({'Success_Count':success,'Fail_Count':len(errors),'Status':'Success' if not errors else 'Partial','Update_Time':NOW},ensure_ascii=False)])
    return {'batch_id':batch_id,'batch_record_id':batch_rec,'counts':{'Organization':len(plan['orgs']),'Position':len(plan['positions']),'Project':len(plan['projects']),'Channel':len(plan['channels']),'Employee':len(plan['employees']),'Error_Log':len(errors)},'source_counts':plan['source_counts'],'source_sha':plan['sha'],'manager_errors':len(manager_errors)}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--apply',action='store_true'); a=p.parse_args()
    plan=build_plan(); write_plan(plan)
    summary={'planned_counts':{k:len(plan[k]) for k in ('orgs','positions','projects','channels','employees','errors')},'source_counts':plan['source_counts'],'plan_file':str(OUT/'T8a_import_plan.json')}
    if a.apply: summary['applied']=run(plan)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
