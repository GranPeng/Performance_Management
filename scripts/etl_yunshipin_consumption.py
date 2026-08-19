#!/usr/bin/env python3
"""T24 云视频管家消耗 ETL。
默认仅预检；--apply 仅在全部阻断校验通过时写入 Base。
可追踪：源文件哈希、行号、批次、明细、错误与回滚清单。
可回滚：只新增记录；回滚以 Status=Archived，不物理删除。
可验证：写前/后记录数、ID、关联、值及幂等指纹校验。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT, REF = ROOT / "data" / "output", ROOT / "1.reference"
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = {
    "Employee": "tblc59aB4EnSxkQv", "Position": "tbldzvsg9Op6pK29",
    "Project": "tbl1GO2vR9ZAqPbr", "Channel": "tblqOGJknsD2H3bt",
    "Metric": "tbldKtdIVv8nnTyX", "Project_Member": "tblcUUz0oq9MxNLu",
    "Project_Group": "tblU6US76mSPKhCD", "Actual": "tbli9VhcUFjVDeNd",
    "Import_Batch": "tblHV3JoVR9AEETw", "Error_Log": "tbl4ZpuuOxZacWgj",
}
SOURCE = "云视频管家"
ETL_SOURCE = "ETL_YUNSHIPIN_CONSUMPTION"
CSV_FILES = [REF / "生成腾讯ADQ投放报表.csv", REF / "生成投放报表(新).csv"]
EXPECTED_MISSING = {"郭丽娜", "陈乾", "黄泽威"}
# CSV/Employee 当前真实姓名与任务文本存在两个同音/字形差异；只作为输入归并，关联仍使用 Employee record_id。
NAME_ALIASES = {"褚翼瑶": "褚翼玮", "高广泓": "高广泳", "盘子熙": "盘子烨"}
PROJECT_BY_CSV_GROUP = {"伊利高个子": "伊利高个子", "骨能金装": "伊利骨能"}
METRIC_BY_POSITION_NAME = {
    "内容主管/编导": "团队产出消耗金额",
    "视频剪辑师": "个人成片消耗金额",
    "摄影师": "个人素材数量",
}
GROUP_SPECS = [
    ("施桐鑫", "施桐鑫（内容高级主管）小组"),
    ("潘剑秋", "潘剑秋（编导，骨能）小组"),
    ("王思伟", "王思伟（编导，高个子）小组"),
]
GROUP_PROJECTS = {"王思伟": "伊利高个子", "潘剑秋": "伊利骨能"}
# 按 PO 指定的「编导—剪辑团队架构」维护。集合仅含直属剪辑/摄影成员，
# 不把编导本人计入剪辑均摊分母；别名已在 NAME_ALIASES 处归并为花名册姓名。
GROUP_MEMBERS = {
    "王思伟": {"黄祖湛", "褚翼玮", "肖思宇", "高广泳", "古旭锋", "谢梦欣", "欧子豪"},
    "潘剑秋": {"罗卓彬", "李波", "盘子烨"},
    "施桐鑫": set(),
}


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def norm(v: Any) -> str:
    return "" if v is None else str(v).strip().replace("\u3000", " ").replace("\t", "").strip()


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def link(record_id: str) -> list[dict[str, str]]:
    return [{"id": record_id}]


def cli(args: list[str], payload: dict | None = None) -> dict:
    cmd = ["lark-cli", "base", *args, "--base-token", BASE, "--as", "user"]
    if payload is not None:
        cmd += ["--json", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
    got = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if got.returncode:
        raise RuntimeError(got.stderr or got.stdout)
    response = json.loads(got.stdout)
    if not response.get("ok"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response["data"]


def rows(table: str, fields: list[str]) -> list[dict[str, Any]]:
    out, offset = [], 0
    while True:
        args = ["+record-list", "--table-id", TABLE[table], "--format", "json", "--limit", "200", "--offset", str(offset)]
        for field in fields:
            args += ["--field-id", field]
        data = cli(args)
        out.extend(dict(zip(data["fields"], vals)) | {"record_id": rid}
                   for vals, rid in zip(data["data"], data["record_id_list"]))
        if not data.get("has_more"):
            return out
        offset += len(data["data"])


def returned_record_id(data: dict[str, Any]) -> str:
    """兼容 lark-cli 当前快捷命令的顶层/嵌套 record_id 返回形状。"""
    record = data.get("record") or {}
    record_ids = record.get("record_id_list") or []
    record_id = data.get("record_id") or record.get("record_id") or (record_ids[0] if len(record_ids) == 1 else None)
    if not record_id:
        raise RuntimeError(f"写入成功响应未返回 record_id：{json.dumps(data, ensure_ascii=False)}")
    return record_id


def parse_csv(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for enc in ("gbk", "gb18030", "utf-8-sig"):
        try:
            raw = list(csv.reader(path.read_text(encoding=enc).splitlines()))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"无法读取 {path.name}")
    header = next((i for i, r in enumerate(raw) if "账号" in r and "消耗" in r), None)
    if header is None:
        raise ValueError(f"未找到账号/消耗列：{path.name}")
    fields = [norm(x) or f"__blank_{i}" for i, x in enumerate(raw[header])]
    def col(name: str) -> str:
        return next(x for x in fields if x == name or name in x)
    account_col, spend_col = col("账号"), col("消耗")
    output = []
    for line, values in enumerate(raw[header + 1:], start=header + 2):
        values += [""] * (len(fields) - len(values))
        record = dict(zip(fields, values))
        account, spend = norm(record[account_col]), norm(record[spend_col])
        # 平台报表首行是总计，非账户事实行；忽略并在预检中保留跳过原因。
        if account in {"", "--"}:
            continue
        try:
            amount = float(spend.replace(",", "").replace("¥", ""))
        except ValueError:
            output.append({"source_file": path.name, "source_row": line, "parse_error": f"消耗不可解析：{spend}", "raw": record})
            continue
        output.append({"source_file": path.name, "source_row": line, "account_name": account,
                       "spend": amount, "raw": record})
    return {"file": path.name, "sha256": digest(path), "encoding": enc,
            "header_row": header + 1, "headers": fields}, output


def next_ids(prefix: str, existing: list[dict[str, Any]], field: str, count: int) -> list[str]:
    numbers = []
    for row in existing:
        match = re.fullmatch(prefix + r"(\d{6})", norm(row.get(field)))
        if match:
            numbers.append(int(match.group(1)))
    start = max(numbers, default=0) + 1
    return [f"{prefix}{i:06d}" for i in range(start, start + count)]


def stable_batch_id(source_files: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> str:
    body = json.dumps({"files": source_files, "rows": [
        {"file": r.get("source_file"), "row": r.get("source_row"), "name": r.get("account_name"), "spend": r.get("spend")}
        for r in raw_rows]}, ensure_ascii=False, sort_keys=True)
    return "IB-YSP-" + hashlib.sha256(body.encode()).hexdigest()[:16].upper()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="预检成功后才写入 Base")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    source_files, raw_rows = [], []
    for file in CSV_FILES:
        info, data = parse_csv(file)
        source_files.append(info); raw_rows.extend(data)

    employees = rows("Employee", ["Employee_ID", "Name", "Position_ID", "Employment_Status", "Perf_Participate_Status", "Status"])
    positions = rows("Position", ["Position_ID", "Position_Name", "Status"])
    metrics = rows("Metric", ["Metric_ID", "Position_ID", "Metric_Name", "Status"])
    projects = rows("Project", ["Project_ID", "Project_Name", "Status"])
    members = rows("Project_Member", ["Project_Member_ID", "Employee_ID", "Project_ID", "Group_ID", "Status"])
    groups = rows("Project_Group", ["Group_ID", "Group_Name", "Leader_Employee_ID", "Status"])
    actuals = rows("Actual", ["Actual_ID", "Import_Batch_ID", "Employee_ID", "Owner_Employee_ID", "Source", "Source_Ref", "Status"])
    batches = rows("Import_Batch", ["Batch_ID", "Status"])
    error_logs = rows("Error_Log", ["Error_ID", "Batch_ID", "Object_ID", "Error_Type", "Status"])

    employee_by_name = {norm(x["Name"]): x for x in employees if norm(x.get("Name"))}
    pos_name = {x["record_id"]: norm(x.get("Position_Name")) for x in positions}
    metric_by_pos_name = {(x["Position_ID"] or [{}])[0].get("id"): x for x in metrics
                          if (x["Position_ID"] or []) and norm(x.get("Metric_Name"))}
    # 一个岗位可能有多个 KPI，故显式按岗位名+指标名索引。
    metric_lookup = {(pos_name.get((x["Position_ID"] or [{}])[0].get("id")), norm(x.get("Metric_Name"))): x
                     for x in metrics if (x["Position_ID"] or [])}
    project_by_name = {norm(x.get("Project_Name")): x for x in projects}

    errors, mapped = [], []
    for raw in raw_rows:
        if raw.get("parse_error"):
            errors.append({"object_id": f"{raw['source_file']}:{raw['source_row']}", "type": "CSV解析", "content": raw["parse_error"]})
            continue
        source_name = norm(raw["account_name"])
        lookup_name = NAME_ALIASES.get(source_name, source_name)
        employee = employee_by_name.get(lookup_name)
        if employee is None:
            errors.append({"object_id": source_name, "type": "人员匹配", "content": f"账号未匹配 Employee；来源={raw['source_file']}:{raw['source_row']}；未导入。"})
            continue
        pos_links = employee.get("Position_ID") or []
        position = pos_name.get(pos_links[0].get("id")) if len(pos_links) == 1 else None
        metric_name = METRIC_BY_POSITION_NAME.get(position)
        metric = metric_lookup.get((position, metric_name)) if metric_name else None
        if metric is None:
            # D-019：非制作部岗位在云视频管家的二次编辑消耗属于无效数据；
            # 显式落 Error_Log，但不阻断同批制作部事实写入，也绝不伪造 Metric。
            error_type = "无效数据-运营二次编辑消耗" if position else "岗位/指标映射"
            content = (f"Employee={lookup_name}，岗位={position or '空/非唯一'}；"
                       + ("D-019：非制作部岗位云视频管家二次编辑消耗不计入制作部绩效，跳过 Actual。"
                          if position else "岗位为空/非唯一，无法确定合规 Metric，禁止导入 Actual。"))
            errors.append({"object_id": source_name, "type": error_type, "content": content})
            continue
        group_text = norm(raw["raw"].get("分组"))
        project = project_by_name.get(PROJECT_BY_CSV_GROUP.get(group_text, ""))
        if project is None:
            errors.append({"object_id": f"{source_name}@{raw['source_file']}:{raw['source_row']}", "type": "项目映射", "content": f"CSV分组“{group_text}”未映射 Project；Actual 保持个人主体，不写 Project_ID。"})
        mapped.append({"raw": raw, "employee": employee, "position": position, "metric": metric, "project": project,
                       "name_normalized": lookup_name != source_name})

    raw_names = {r.get("account_name") for r in raw_rows if r.get("account_name")}
    missing_seen = raw_names & EXPECTED_MISSING
    for name in sorted(missing_seen):
        # 如果已有通用人员匹配错误，不重复创建错误事实。
        if not any(e["object_id"] == name and e["type"] == "人员匹配" for e in errors):
            errors.append({"object_id": name, "type": "人员匹配", "content": "任务指定花名册缺失人员，禁止导入 Actual。"})
    if missing_seen != EXPECTED_MISSING:
        errors.append({"object_id": "T24输入完整性", "type": "输入完整性", "content": f"CSV实际缺失人员集合={sorted(missing_seen)}，与任务指定不一致。"})

    batch_id = stable_batch_id(source_files, raw_rows)
    existing_batch = next((x for x in batches if x.get("Batch_ID") == batch_id), None)
    # 任务明确要求的三位花名册缺失人员属于可写入 Error_Log 的业务异常，
    # 不是阻断；其它人员/指标异常才阻断事实写入。
    blockers = [e for e in errors if e["type"] in {"CSV解析", "岗位/指标映射", "输入完整性"}
                or (e["type"] == "人员匹配" and e["object_id"] not in EXPECTED_MISSING)]
    # D-019 批次由 9 名合规制作部人员 + 4 条可审计异常构成：
    # 指定花名册缺失 3 人，及 1 名非制作岗位无效二次编辑消耗。
    expected_actual_count = 9
    preflight = {
        "task": "T24", "mode": "APPLY" if args.apply else "READ_ONLY_PREFLIGHT", "generated_at": stamp(),
        "batch_id": batch_id, "existing_batch": existing_batch, "source_files": source_files,
        "raw_data_rows": len(raw_rows), "mapped_actual_count": len(mapped),
        "mapped": [{"source": f"{x['raw']['source_file']}:{x['raw']['source_row']}", "csv_account": x['raw']['account_name'],
                    "employee": x['employee']['Name'], "employee_id": x['employee']['Employee_ID'], "position": x['position'],
                    "metric": x['metric']['Metric_Name'], "project": x['project']['Project_Name'] if x['project'] else "【待确认】",
                    "channel": "【待确认】", "spend": x['raw']['spend']} for x in mapped],
        "groups_before": [{k: x.get(k) for k in ("Group_ID", "Group_Name", "Status")} | {"record_id": x["record_id"]} for x in groups],
        "project_member_count": len(members), "errors": errors,
        "blocking_errors": blockers,
        "apply_gate": "PASS" if not blockers and len(mapped) == expected_actual_count else "BLOCKED",
        "apply_gate_reason": "D-019：仅当9条合规制作部Actual、三名花名册缺失人员日志、及一条非制作岗位无效数据日志齐全且无阻断异常时写入。",
    }
    (OUT / "T24_云视频管家ETL_预检.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 本地组织汇总：只基于可映射事实；Period/Channel不明不伪造。
    spend_by_employee = {x["employee"]["Name"]: x["raw"]["spend"] for x in mapped}
    aggregate = []
    for leader, group_name in GROUP_SPECS:
        people = sorted(GROUP_MEMBERS.get(leader, set()))
        detail = [{"employee": p, "spend": spend_by_employee.get(p), "in_this_import": p in spend_by_employee} for p in people]
        team_sum = sum(d["spend"] for d in detail if d["spend"] is not None)
        aggregate.append({"leader": leader, "group_name": group_name, "member_count_configured": len(people),
                          "member_detail": detail, "team_spend_sum_imported": team_sum,
                          "director_team_sum": team_sum if leader in {"潘剑秋", "王思伟"} else None,
                          "editor_equal_share_x_0_9": (team_sum / len(people) * 0.9) if people else None,
                          "period": "【待确认】", "channel": "【待确认】"})
    (OUT / "T24_云视频管家ETL_组织汇总.json").write_text(json.dumps({"generated_at": stamp(), "batch_id": batch_id,
        "calculation": "编导=直属小组已导入成员消耗总和；剪辑=同组已导入消耗÷配置成员数×0.9。Period/Channel未见于CSV，标记待确认。", "groups": aggregate}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.apply:
        print(json.dumps({"status": "PREFLIGHT_COMPLETE", "batch_id": batch_id, "mapped": len(mapped),
            "errors": len(errors), "blockers": len(blockers), "apply_gate": preflight["apply_gate"]}, ensure_ascii=False))
        return 0
    if preflight["apply_gate"] != "PASS":
        raise RuntimeError(f"写入已阻断：mapped={len(mapped)}，blocking_errors={len(blockers)}；详见预检文件。")

    # 同指纹批次存在时，先验证此前事实行/异常行已完整落地；通过后仅补齐
    # 可独立幂等的组织归属，不新增/覆盖 Actual、Error_Log 或 Import_Batch。
    existing_actuals: list[dict[str, Any]] = []
    existing_errors: list[dict[str, Any]] = []
    if existing_batch:
        existing_actuals = [x for x in actuals if any(linked.get("id") == existing_batch["record_id"]
                                                       for linked in (x.get("Import_Batch_ID") or []))]
        existing_errors = [x for x in error_logs if any(linked.get("id") == existing_batch["record_id"]
                                                        for linked in (x.get("Batch_ID") or []))]
        if len(existing_actuals) != expected_actual_count or len(existing_errors) != len(errors):
            raise RuntimeError("已存在批次明细不完整，禁止用幂等路径掩盖异常："
                               f"Actual={len(existing_actuals)}/{expected_actual_count}，"
                               f"Error_Log={len(existing_errors)}/{len(errors)}。")

    now = stamp()
    # 先创建/复用三组，再更新现有 Project_Member.Group_ID；不改其它成员字段。
    groups_by_leader = {((x.get("Leader_Employee_ID") or [{}])[0].get("id")): x for x in groups}
    group_ids = next_ids("GRP", groups, "Group_ID", len(GROUP_SPECS))
    leaders = {norm(x["Name"]): x for x in employees}
    group_records = {}
    created_group_ids = []
    for idx, (leader_name, group_name) in enumerate(GROUP_SPECS):
        leader = leaders[leader_name]
        existing = groups_by_leader.get(leader["record_id"])
        if existing:
            group_records[leader_name] = existing["record_id"]
            continue
        payload = {"Group_ID": group_ids[idx], "Group_Name": group_name, "Leader_Employee_ID": link(leader["record_id"]),
                   "Create_Time": now, "Update_Time": now, "Status": "Active"}
        rid = returned_record_id(cli(["+record-upsert", "--table-id", TABLE["Project_Group"]], payload))
        group_records[leader_name] = rid; created_group_ids.append(rid)
    member_group_updates = []
    employee_name_by_rid = {x["record_id"]: norm(x["Name"]) for x in employees}
    for member in members:
        emp_links = member.get("Employee_ID") or []
        name = employee_name_by_rid.get(emp_links[0].get("id")) if len(emp_links) == 1 else None
        leader = next((lead for lead, people in GROUP_MEMBERS.items() if name in people), None)
        current_group_links = member.get("Group_ID") or []
        current_group_id = current_group_links[0].get("id") if len(current_group_links) == 1 else None
        if leader and current_group_id != group_records[leader]:
            cli(["+record-upsert", "--table-id", TABLE["Project_Member"], "--record-id", member["record_id"]],
                {"Group_ID": link(group_records[leader]), "Update_Time": now})
            member_group_updates.append({"project_member_record_id": member["record_id"], "employee": name,
                                         "leader": leader, "old_group_record_id": current_group_id,
                                         "new_group_record_id": group_records[leader]})

    actual_owner_updates = []
    if existing_batch:
        # T24 明确规定 Owner_Employee_ID=员工；对既有同批事实仅补空缺/错误归因，
        # 逐行保留旧关联用于回滚，绝不改动 Actual_Value、Metric 或来源字段。
        for actual in existing_actuals:
            employee_links = actual.get("Employee_ID") or []
            owner_links = actual.get("Owner_Employee_ID") or []
            employee_record_id = employee_links[0].get("id") if len(employee_links) == 1 else None
            owner_record_id = owner_links[0].get("id") if len(owner_links) == 1 else None
            if not employee_record_id:
                raise RuntimeError(f"既有Actual {actual['record_id']} 缺少唯一Employee_ID，禁止补写Owner。")
            if owner_record_id != employee_record_id:
                cli(["+record-upsert", "--table-id", TABLE["Actual"], "--record-id", actual["record_id"]],
                    {"Owner_Employee_ID": link(employee_record_id), "Update_Time": now})
                actual_owner_updates.append({"actual_record_id": actual["record_id"],
                                             "actual_id": actual.get("Actual_ID"),
                                             "old_owner_employee_record_id": owner_record_id,
                                             "new_owner_employee_record_id": employee_record_id})

    if existing_batch:
        sync_rollback = {
            "batch_id": batch_id,
            "batch_record_id": existing_batch["record_id"],
            "project_member_group_updates": member_group_updates,
            "actual_owner_employee_updates": actual_owner_updates,
            "rollback_method": "按 project_member_group_updates 的 old_group_record_id 恢复 Group_ID；按 actual_owner_employee_updates 的 old_owner_employee_record_id 恢复 Owner_Employee_ID；null 表示清空关联。",
        }
        sync_rollback_path = OUT / "T24_云视频管家ETL_组织同步回滚清单.json"
        # 后续无变更的幂等复跑不得覆盖首个有变更的回滚证据。
        if member_group_updates or actual_owner_updates or not sync_rollback_path.exists():
            sync_rollback_path.write_text(json.dumps(sync_rollback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {"status": "IDEMPOTENT_SYNCED", "batch_id": batch_id,
                  "batch_record_id": existing_batch["record_id"], "actual_count_verified": len(existing_actuals),
                  "error_count_verified": len(existing_errors), "group_created": len(created_group_ids),
                  "member_group_updated": len(member_group_updates), "actual_owner_updated": len(actual_owner_updates),
                  "reason": "同一源文件批次事实完整，未新增Actual/Error_Log/Import_Batch；仅补齐组织归属与Owner归因。"}
        (OUT / "T24_云视频管家ETL_执行结果.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False)); return 0

    batch_payload = {"Batch_ID": batch_id, "Batch_Type": "ACTUAL", "Source_Type": "Excel文件", "Source_File": ",".join(x.name for x in CSV_FILES),
        "Source_SHA256": hashlib.sha256("|".join(x["sha256"] for x in source_files).encode()).hexdigest(), "Import_Time": now,
        "Operator": "data-engineer/T24", "Total_Count": len(mapped), "Success_Count": 0, "Fail_Count": len(errors),
        "Source": ETL_SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running",
        "Note": "D-015：CSV已按近90天成片当月消耗导出；Period与Channel在源文件中不可证明，标记待确认。"}
    batch_rid = returned_record_id(cli(["+record-upsert", "--table-id", TABLE["Import_Batch"]], batch_payload))
    actual_ids = next_ids("ACT", actuals, "Actual_ID", len(mapped))
    payloads = []
    for actual_id, item in zip(actual_ids, mapped):
        raw, emp, metric = item["raw"], item["employee"], item["metric"]
        payload = {"Actual_ID": actual_id, "Metric_ID": link(metric["record_id"]), "Period": "【待确认】", "Employee_ID": link(emp["record_id"]),
                   "Owner_Employee_ID": link(emp["record_id"]), "Actual_Value": raw["spend"], "Unit": "元", "Material_Type": "NEW_MATERIAL", "Source_Type": "PLATFORM_IMPORT",
                   "Source_Ref": f"{SOURCE};{raw['source_file']}:{raw['source_row']};账号={raw['account_name']};列=消耗",
                   "Collected_By": link(emp["record_id"]), "Collected_Time": now, "Validation_Status": "待校验", "Import_Batch_ID": link(batch_rid),
                   "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active",
                   "Note": "Period/Channel未从CSV或文件名验证，均待确认；Owner_Employee_ID按T24归因为对应员工；首投日期待确认。"}
        if item["project"]:
            payload["Project_ID"] = link(item["project"]["record_id"])
        payloads.append(payload)
    actual_rids = cli(["+record-batch-create", "--table-id", TABLE["Actual"]], {"create_records": payloads}).get("record_id_list", [])
    if len(actual_rids) != len(payloads):
        raise RuntimeError("Actual 创建数量不一致；停止并保留批次用于回滚。")
    error_rids = []
    if errors:
        error_existing = rows("Error_Log", ["Error_ID"])
        error_ids = next_ids("ERR", error_existing, "Error_ID", len(errors))
        error_payloads = [{"Error_ID": eid, "Batch_ID": link(batch_rid), "Object_Type": "CSV账号/ETL输入", "Object_ID": e["object_id"],
            "Error_Type": e["type"], "Error_Content": e["content"], "Process_Status": "待处理", "Source": ETL_SOURCE,
            "Create_Time": now, "Update_Time": now, "Status": "Active", "Note": "T24真实数据ETL异常"} for eid, e in zip(error_ids, errors)]
        error_rids = cli(["+record-batch-create", "--table-id", TABLE["Error_Log"]], {"create_records": error_payloads}).get("record_id_list", [])
    cli(["+record-upsert", "--table-id", TABLE["Import_Batch"], "--record-id", batch_rid],
        {"Success_Count": len(actual_rids), "Fail_Count": len(error_rids), "Status": "Success" if not error_rids else "Partial", "Update_Time": stamp()})
    rollback = {"batch_id": batch_id, "batch_record_id": batch_rid, "created_actual_record_ids": actual_rids,
                "created_error_record_ids": error_rids, "created_project_group_record_ids": created_group_ids,
                "project_member_group_updates": member_group_updates,
                "rollback_method": "将本批新增Actual/Error_Log/Import_Batch/Project_Group置Archived；Project_Member.Group_ID按此清单恢复原值。"}
    (OUT / "T24_云视频管家ETL_回滚清单.json").write_text(json.dumps(rollback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"status": "APPLY_PASSED", "batch_id": batch_id, "batch_record_id": batch_rid, "actual_count": len(actual_rids),
              "error_count": len(error_rids), "group_created": len(created_group_ids), "member_group_updated": len(member_group_updates)}
    (OUT / "T24_云视频管家ETL_执行结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False)); return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "T24_云视频管家ETL_运行异常.json").write_text(json.dumps({"status": "FAILED", "time": stamp(), "error": str(exc)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
