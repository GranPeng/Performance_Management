#!/usr/bin/env python3
"""T8c 岗位归并：D-012/CHG-T8C-001 受控执行。

默认只生成可审计计划；--apply 才会写 Base。写入范围严格限定：
1) 14 张正式表补建可选 text 字段 Note；
2) EMP000027/EMP000028 的 Position_ID；
3) POS000037 Status/Note，POS000039/040 Note；
4) 关闭本任务前置 schema 阻断 Error_Log，并写入本次 Import_Batch。
不修改 Metric、Target 或任何业务结果。每次写入均保留回滚前快照。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
BATCH_ID = "IB-T8C-MERGE-20260817-01"
PRECHECK_ERROR_ID = "ERR-T8C-20260817-SCHEMA-NOTE"
PRECHECK_ERROR_RECORD_ID = "recvswujqTCUIC"
FORMAL_TABLES = {
    "Organization": "tblc6rU0d2bHMVnZ",
    "Position": "tbldzvsg9Op6pK29",
    "Employee": "tblc59aB4EnSxkQv",
    "Project": "tbl1GO2vR9ZAqPbr",
    "Channel": "tblqOGJknsD2H3bt",
    "Project_Member": "tblcUUz0oq9MxNLu",
    "Metric": "tbldKtdIVv8nnTyX",
    "Target": "tblydZkf17kmzrO0",
    "Actual": "tbli9VhcUFjVDeNd",
    "Performance_Result": "tbl6tFtVKExFUTWo",
    "Commission_Tier": "tblkZUoHYwBIvDYe",
    "Import_Batch": "tblHV3JoVR9AEETw",
    "Validation_Rule": "tblnc4m0jV47DKna",
    "Error_Log": "tbl4ZpuuOxZacWgj",
}


def stamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def cli(args: list[str], payload: Any | None = None, payload_name: str = "payload") -> dict[str, Any]:
    cmd = ["lark-cli", "base", *args, "--as", "user", "--format", "json"]
    if payload is not None:
        directory = OUT / "t8c_payloads"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{payload_name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        cmd.extend(["--json", "@" + str(path.relative_to(ROOT))])
    env = os.environ | {"LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1", "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1"}
    for attempt in range(5):
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=env)
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            body = {"ok": False, "stdout": result.stdout, "stderr": result.stderr}
        if result.returncode == 0 and body.get("ok"):
            return body
        if "1254291" in result.stdout + result.stderr or "onOverQPSLimit" in result.stdout + result.stderr:
            if attempt < 4:
                time.sleep(attempt + 1)
                continue
        raise RuntimeError(json.dumps({"args": args, "rc": result.returncode, "body": body, "stderr": result.stderr}, ensure_ascii=False))
    raise RuntimeError("QPS retry exhausted")


def fields(table: str) -> list[dict[str, Any]]:
    return cli(["+field-list", "--base-token", BASE, "--table-id", FORMAL_TABLES[table]])["data"]["fields"]


def rows(table: str, field_names: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", FORMAL_TABLES[table], "--limit", "200", "--offset", str(offset)]
        for field in field_names:
            args.extend(["--field-id", field])
        data = cli(args)["data"]
        names, values, ids = data["fields"], data["data"], data["record_id_list"]
        if len(values) != len(ids):
            raise RuntimeError(f"{table}: record_id_list/data 长度不一致")
        result.extend({"record_id": rid, **dict(zip(names, value))} for rid, value in zip(ids, values))
        if not data.get("has_more"):
            return result
        if not values:
            raise RuntimeError(f"{table}: has_more=true 但返回空页")
        offset += len(values)


def one_link(value: Any) -> str | None:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0].get("id")
    return None


def link(record_id: str) -> list[dict[str, str]]:
    return [{"id": record_id}]


def require_single(items: list[dict[str, Any]], predicate, label: str) -> dict[str, Any]:
    matched = [item for item in items if predicate(item)]
    if len(matched) != 1:
        raise RuntimeError(f"{label} 预期唯一记录，实际={len(matched)}")
    return matched[0]


def build_plan() -> dict[str, Any]:
    now = stamp()
    field_state = {name: fields(name) for name in FORMAL_TABLES}
    note_existing = {name: [f for f in values if f.get("name") == "Note"] for name, values in field_state.items()}
    non_text_note = {name: value for name, value in note_existing.items() if value and value[0].get("type") != "text"}
    if non_text_note:
        raise RuntimeError(f"已存在非 TEXT 类型 Note，禁止修改：{non_text_note}")
    note_to_create = [name for name, value in note_existing.items() if not value]

    positions = rows("Position", ["Position_ID", "Position_Name", "Status", "Note", "Update_Time"] if not note_to_create or "Position" not in note_to_create else ["Position_ID", "Position_Name", "Status", "Update_Time"])
    employees = rows("Employee", ["Employee_ID", "Name", "Position_ID", "Perf_Participate_Status", "Status", "Note"] if not note_to_create or "Employee" not in note_to_create else ["Employee_ID", "Name", "Position_ID", "Perf_Participate_Status", "Status"])
    metrics = rows("Metric", ["Metric_ID", "Position_ID", "Status"])
    batches = rows("Import_Batch", ["Batch_ID", "Batch_Type", "Total_Count", "Success_Count", "Fail_Count", "Status", "Note"] if not note_to_create or "Import_Batch" not in note_to_create else ["Batch_ID", "Batch_Type", "Total_Count", "Success_Count", "Fail_Count", "Status"])
    errors = rows("Error_Log", ["Error_ID", "Object_Type", "Object_ID", "Error_Content", "Process_Status", "Handler", "Handle_Time", "Status", "Update_Time", "Note"] if not note_to_create or "Error_Log" not in note_to_create else ["Error_ID", "Object_Type", "Object_ID", "Error_Content", "Process_Status", "Handler", "Handle_Time", "Status", "Update_Time"])

    existing_batches = [row for row in batches if row.get("Batch_ID") == BATCH_ID]
    if len(existing_batches) > 1:
        raise RuntimeError(f"目标 Import_Batch {BATCH_ID} 出现重复记录；为防重复写入停止")
    existing_batch = existing_batches[0] if existing_batches else None
    if existing_batch and existing_batch.get("Status") != "Running":
        raise RuntimeError(f"目标 Import_Batch {BATCH_ID} 已存在且状态不是 Running：{existing_batch.get('Status')}")
    pos37 = require_single(positions, lambda r: r.get("Position_ID") == "POS000037", "POS000037")
    pos38 = require_single(positions, lambda r: r.get("Position_ID") == "POS000038", "POS000038")
    pos39 = require_single(positions, lambda r: r.get("Position_ID") == "POS000039", "POS000039")
    pos40 = require_single(positions, lambda r: r.get("Position_ID") == "POS000040", "POS000040")
    emp27 = require_single(employees, lambda r: r.get("Employee_ID") == "EMP000027", "EMP000027")
    emp28 = require_single(employees, lambda r: r.get("Employee_ID") == "EMP000028", "EMP000028")
    schema_error = require_single(errors, lambda r: r["record_id"] == PRECHECK_ERROR_RECORD_ID and r.get("Error_ID") == PRECHECK_ERROR_ID, "T8c 前置 Error_Log")

    preconditions = []
    if pos37.get("Status") != "Active": preconditions.append("POS000037 当前不是 Active")
    if pos38.get("Status") != "Active": preconditions.append("POS000038 当前不是 Active")
    for employee in (emp27, emp28):
        if one_link(employee.get("Position_ID")) != pos37["record_id"]:
            preconditions.append(f"{employee.get('Employee_ID')} 当前未挂 POS000037")
    pos38_metrics = [m for m in metrics if one_link(m.get("Position_ID")) == pos38["record_id"] and m.get("Status") == "Active"]
    if len(pos38_metrics) != 6: preconditions.append(f"POS000038 Active Metric 数量不是 6，而是 {len(pos38_metrics)}")
    if schema_error.get("Status") != "Active": preconditions.append("前置 schema Error_Log 非 Active，不能按预定闭环")
    if preconditions:
        raise RuntimeError("；".join(preconditions))

    active_metric_positions = {one_link(m.get("Position_ID")) for m in metrics if m.get("Status") == "Active" and one_link(m.get("Position_ID"))}
    participants = [e for e in employees if e.get("Perf_Participate_Status") == "确认参与"]
    if len(participants) != 32:
        raise RuntimeError(f"确认参与员工数预期32，实际{len(participants)}")
    before_failures = [e.get("Employee_ID") for e in participants if one_link(e.get("Position_ID")) not in active_metric_positions]
    if before_failures != ["EMP000027", "EMP000028"]:
        raise RuntimeError(f"修复前失败集合异常：{before_failures}")

    updates = {
        "Employee": [
            {"record_id": emp27["record_id"], "fields": {"Position_ID": link(pos38["record_id"]), "Update_Time": now}, "prior": {"Position_ID": emp27.get("Position_ID"), "Update_Time": emp27.get("Update_Time")}},
            {"record_id": emp28["record_id"], "fields": {"Position_ID": link(pos38["record_id"]), "Update_Time": now}, "prior": {"Position_ID": emp28.get("Position_ID"), "Update_Time": emp28.get("Update_Time")}},
        ],
        "Position": [
            {"record_id": pos37["record_id"], "fields": {"Status": "Inactive", "Note": "已并入 POS000038，2026-08-17，T8c", "Update_Time": now}, "prior": {"Status": pos37.get("Status"), "Note": pos37.get("Note"), "Update_Time": pos37.get("Update_Time")}},
            {"record_id": pos39["record_id"], "fields": {"Note": "T8c全量排查：与 POS000040 同名，但不在 V04 KPI 覆盖范围；保留原实体语义，暂不处理。", "Update_Time": now}, "prior": {"Note": pos39.get("Note"), "Update_Time": pos39.get("Update_Time")}},
            {"record_id": pos40["record_id"], "fields": {"Note": "T8c全量排查：与 POS000039 同名，但不在 V04 KPI 覆盖范围；保留原实体语义，暂不处理。", "Update_Time": now}, "prior": {"Note": pos40.get("Note"), "Update_Time": pos40.get("Update_Time")}},
        ],
        "Error_Log": [{"record_id": schema_error["record_id"], "fields": {"Error_Content": str(schema_error.get("Error_Content") or "") + "；【D-012/CHG-T8C-001】14张正式表已补建 Note(TEXT)，归并已执行并读回验证。", "Process_Status": "已解决", "Handler": "data-engineer/T8c", "Handle_Time": now, "Status": "Archived", "Update_Time": now}, "prior": {key: schema_error.get(key) for key in ("Error_Content", "Process_Status", "Handler", "Handle_Time", "Status", "Update_Time")}}],
    }
    canonical = {"decision": "D-012/CHG-T8C-001", "operator": "data-engineer/T8c", "note_field_tables": note_to_create, "record_updates": updates}
    source_hash = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    batch = {"Batch_ID": BATCH_ID, "Batch_Type": "MASTER_DATA", "Source_Type": "D-012/CHG-T8C-001受控归并", "Source_File": "context/decision_log.md;docs/data_model.md;data/output/T8c_position_merge_preflight.json", "Source_SHA256": source_hash, "Import_Time": now, "Operator": "data-engineer/T8c", "Total_Count": len(FORMAL_TABLES) + 5, "Success_Count": 0, "Fail_Count": 0, "Source": "T8c岗位归并", "Create_Time": now, "Update_Time": now, "Status": "Running"}
    return {"task": "T8c", "decision": "D-012/CHG-T8C-001", "created_at": now, "base_token": BASE, "note_fields_total": len(FORMAL_TABLES), "note_fields_existing": {name: value for name, value in note_existing.items() if value}, "note_fields_to_create": note_to_create, "existing_batch_record_id": existing_batch["record_id"] if existing_batch else None, "precondition": {"Position": {"POS000037": pos37["record_id"], "POS000038": pos38["record_id"], "POS000039": pos39["record_id"], "POS000040": pos40["record_id"]}, "Employee": {"EMP000027": emp27["record_id"], "EMP000028": emp28["record_id"]}, "POS000038_active_metric_count": len(pos38_metrics), "confirmed_participants_before": len(participants), "participant_failures_before": before_failures}, "updates": updates, "batch": batch}


def apply(plan: dict[str, Any]) -> dict[str, Any]:
    written: dict[str, Any] = {"Note_fields": {}, "records": defaultdict(list), "batch_record_id": None}
    # Schema first as explicitly directed by PO. One simple TEXT field per table; each response yields its real field ID.
    for table in plan["note_fields_to_create"]:
        response = cli(["+field-create", "--base-token", BASE, "--table-id", FORMAL_TABLES[table]], {"type": "text", "name": "Note", "description": "通用治理备注；承载归并说明、作废原因、特殊标注等。CHG-T8C-001。"}, f"field_create_{table}")
        created = response.get("data", {}).get("created") or response.get("data", {})
        written["Note_fields"][table] = created
    if plan.get("existing_batch_record_id"):
        batch_record_id = plan["existing_batch_record_id"]
    else:
        batch_response = cli(["+record-upsert", "--base-token", BASE, "--table-id", FORMAL_TABLES["Import_Batch"]], plan["batch"], "import_batch_create")
        batch_record = batch_response["data"].get("record", {})
        batch_record_id = batch_record.get("record_id") or batch_record.get("id")
        if not batch_record_id:
            raise RuntimeError("Import_Batch 创建未返回 record_id；停止后续写入以避免不可追踪变更")
    written["batch_record_id"] = batch_record_id
    for table in ("Employee", "Position", "Error_Log"):
        payload = {"update_records": {item["record_id"]: item["fields"] for item in plan["updates"][table]}}
        response = cli(["+record-batch-update", "--base-token", BASE, "--table-id", FORMAL_TABLES[table]], payload, f"{table.lower()}_update")
        if response.get("data", {}).get("ignored_fields"):
            raise RuntimeError(f"{table} 出现 ignored_fields：{response['data']['ignored_fields']}")
        written["records"][table].extend(item["record_id"] for item in plan["updates"][table])
    # Read-back: schema, exact repaired records, and every confirmed participant → Active Metric.
    note_verification = {table: [f for f in fields(table) if f.get("name") == "Note" and f.get("type") == "text"] for table in FORMAL_TABLES}
    missing_notes = [table for table, value in note_verification.items() if len(value) != 1]
    if missing_notes:
        raise RuntimeError(f"Note 字段读回失败/非唯一：{missing_notes}")
    positions = rows("Position", ["Position_ID", "Status", "Note"])
    employees = rows("Employee", ["Employee_ID", "Name", "Position_ID", "Perf_Participate_Status"])
    metrics = rows("Metric", ["Metric_ID", "Position_ID", "Status"])
    pos37 = require_single(positions, lambda r: r.get("Position_ID") == "POS000037", "POS000037读回")
    pos38 = require_single(positions, lambda r: r.get("Position_ID") == "POS000038", "POS000038读回")
    e27 = require_single(employees, lambda r: r.get("Employee_ID") == "EMP000027", "EMP000027读回")
    e28 = require_single(employees, lambda r: r.get("Employee_ID") == "EMP000028", "EMP000028读回")
    if pos37.get("Status") != "Inactive" or pos37.get("Note") != "已并入 POS000038，2026-08-17，T8c":
        raise RuntimeError("POS000037 状态或归并注记读回不符")
    if one_link(e27.get("Position_ID")) != pos38["record_id"] or one_link(e28.get("Position_ID")) != pos38["record_id"]:
        raise RuntimeError("EMP000027/EMP000028 Position_ID 读回不符")
    active_positions = {one_link(m.get("Position_ID")) for m in metrics if m.get("Status") == "Active" and one_link(m.get("Position_ID"))}
    participants = [e for e in employees if e.get("Perf_Participate_Status") == "确认参与"]
    failures = [{"Employee_ID": e.get("Employee_ID"), "Name": e.get("Name"), "Position_record_id": one_link(e.get("Position_ID"))} for e in participants if one_link(e.get("Position_ID")) not in active_positions]
    if len(participants) != 32 or failures:
        raise RuntimeError(f"确认参与员工关联 Active Metric 验证失败：人数={len(participants)} failures={failures}")
    success_count = plan["note_fields_total"] + 5
    batch_final = {"Success_Count": success_count, "Fail_Count": 0, "Status": "Success", "Update_Time": stamp(), "Note": "D-012/CHG-T8C-001：14张正式表补建 Note；归并与32/32关联验证均通过。"}
    response = cli(["+record-batch-update", "--base-token", BASE, "--table-id", FORMAL_TABLES["Import_Batch"]], {"update_records": {batch_record_id: batch_final}}, "import_batch_final")
    if response.get("data", {}).get("ignored_fields"):
        raise RuntimeError(f"Import_Batch final ignored_fields：{response['data']['ignored_fields']}")
    return {"written": {**written, "records": dict(written["records"])}, "verification": {"note_fields": {table: verification[0].get("id") for table, verification in note_verification.items()}, "EMP000027_Position_record_id": one_link(e27.get("Position_ID")), "EMP000028_Position_record_id": one_link(e28.get("Position_ID")), "POS000037": {"status": pos37.get("Status"), "note": pos37.get("Note")}, "confirmed_participants": len(participants), "participant_failures": failures, "active_metric_positions": len(active_positions)}, "batch_final": batch_final}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际执行已审计的 Base 写入")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    plan = build_plan()
    plan_path = OUT / "T8c_position_merge_execution_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.apply:
        print(json.dumps({"status": "PREFLIGHT_PASSED", "plan": str(plan_path), "note_fields_to_create": len(plan["note_fields_to_create"]), "record_updates": {table: len(items) for table, items in plan["updates"].items()}, "batch": plan["batch"]}, ensure_ascii=False))
        return
    result = apply(plan)
    result_path = OUT / "T8c_position_merge_execution_result.json"
    result_path.write_text(json.dumps({"plan": plan, "result": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "APPLY_COMPLETED", "result": result, "result_file": str(result_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
