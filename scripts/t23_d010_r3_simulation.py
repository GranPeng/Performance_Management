#!/usr/bin/env python3
"""T23 D-010-R3 双条件豁免模拟。

默认预检，不修改在线数据；--apply 仅创建 SIMULATED_T23_D010_R3 专属
Project / Actual / Performance_Result / Import_Batch，并回填 EXS000001 的
Max_Monthly_Revenue=1,000,000（CNY）。执行和回滚清单均落盘。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
T = {
    "Project": "tbl1GO2vR9ZAqPbr", "Actual": "tbli9VhcUFjVDeNd",
    "Performance_Result": "tbl6tFtVKExFUTWo", "Import_Batch": "tblHV3JoVR9AEETw",
    "Exemption_Scope": "tblP6Im75vDohuPF", "Metric": "tbldKtdIVv8nnTyX",
}
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
SOURCE = "SIMULATED_T23_D010_R3"
ACTUAL_BATCH = "IB-T23-ACTUAL-20260818-01"
CALC_BATCH = "IB-T23-CALC-20260818-01"
SCOPE_RID = "recvsyf5IYhkt5"
SCOPE_ID = "EXS000001"
OPS_METRIC_RID = "recvsgqAO9qu6Y"
CHANNEL_DOUYIN_RID = "recvsls7z4BhTA"
T14_RESULT_RID = "recvsyat0oz6cL"
T14_ACTUAL_RID = "recvsyastLpoaV"
PLAN = ROOT / "data/output/T23_D010_R3模拟计划.json"
EXEC = ROOT / "data/output/T23_D010_R3模拟执行结果.json"
ROLLBACK = ROOT / "data/output/T23_D010_R3回滚清单.json"
ERROR = ROOT / "data/output/T23_D010_R3错误日志.json"


def call(args: list[str]) -> dict[str, Any]:
    p = subprocess.run([CLI, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        raw = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli 非 JSON: {p.stdout[-500:]} / {p.stderr[-500:]}") from exc
    if p.returncode or not raw.get("ok"):
        raise RuntimeError(json.dumps(raw, ensure_ascii=False))
    return raw["data"]


def records(table: str, fields: list[str]) -> list[dict[str, Any]]:
    out, offset = [], 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", T[table], "--limit", "200", "--offset", str(offset), "--format", "json"]
        for field in fields:
            args += ["--field-id", field]
        data = call(args)
        out.extend({**dict(zip(data["fields"], values)), "_record_id": rid} for rid, values in zip(data["record_id_list"], data["data"]))
        if not data.get("has_more"):
            return out
        offset += len(data["record_id_list"])


def record_get(table: str, rid: str, fields: list[str]) -> dict[str, Any]:
    data = call(["+record-get", "--base-token", BASE, "--table-id", T[table], "--record-id", rid, "--format", "json"])
    return dict(zip(data["fields"], data["data"][0]))


def one_link(value: Any) -> str | None:
    return value[0]["id"] if isinstance(value, list) and value else None


def next_id(rows: list[dict[str, Any]], field: str, prefix: str) -> int:
    values = []
    for row in rows:
        match = re.fullmatch(rf"{prefix}(\d{{6}})", str(row.get(field, "")))
        if match:
            values.append(int(match.group(1)))
    return max(values, default=0) + 1


def build_plan() -> dict[str, Any]:
    scopes = records("Exemption_Scope", ["Exemption_Scope_ID", "Max_Project_Run_Days", "Max_Monthly_Revenue", "Status"])
    scope = next((x for x in scopes if x.get("Exemption_Scope_ID") == SCOPE_ID and x["_record_id"] == SCOPE_RID), None)
    if not scope or scope.get("Status") != "Active" or float(scope.get("Max_Project_Run_Days") or 0) != 90:
        raise RuntimeError(f"EXS000001 前置状态异常: {scope}")
    t14 = record_get("Performance_Result", T14_RESULT_RID, ["Source", "Actual_ID", "Revenue_Actual_ID"])
    if t14.get("Source") != "SIMULATED_T14_D010_NONZERO" or one_link(t14.get("Actual_ID")) != T14_ACTUAL_RID:
        raise RuntimeError(f"T14 前置记录异常: {t14}")
    projects = records("Project", ["Project_ID", "Source"])
    actuals = records("Actual", ["Actual_ID", "Source"])
    results = records("Performance_Result", ["Result_ID", "Source"])
    batches = records("Import_Batch", ["Batch_ID", "Source"])
    existing = [r for r in projects + actuals + results + batches if r.get("Source") == SOURCE]
    if existing:
        raise RuntimeError("已存在 T23 模拟来源记录，拒绝重复写入；请先按回滚清单处理")
    # 每个用例使用独立期间，避免同一员工的 Monthly_Total 交叉累加；开始日期均由该期月末反推。
    cases = [
        {"case_id": "T23-EXEMPT-AT-LIMIT", "period": "2027-07", "start_date": "2027-06-17", "revenue": 1000000, "expected_days": 44, "expected_exempt": True, "expected_ratio": 0.003, "expected_amount": 3000},
        {"case_id": "T23-REVENUE-OVER-LIMIT", "period": "2027-08", "start_date": "2027-07-18", "revenue": 1000001, "expected_days": 44, "expected_exempt": False, "expected_ratio": 0.0018, "expected_amount": 1800.0018},
        {"case_id": "T23-DAYS-AT-90", "period": "2027-09", "start_date": "2027-07-02", "revenue": 500000, "expected_days": 90, "expected_exempt": False, "expected_ratio": 0.0018, "expected_amount": 900},
    ]
    plan = {
        "task": "T23", "source": SOURCE, "mode": "PREFLIGHT", "unit": "元（CNY）",
        "scope": {"record_id": SCOPE_RID, "id": SCOPE_ID, "max_project_run_days": 90, "max_monthly_revenue": 1000000},
        "batches": {"actual": ACTUAL_BATCH, "calc": CALC_BATCH},
        "id_starts": {"project": next_id(projects, "Project_ID", "PROJ"), "actual": next_id(actuals, "Actual_ID", "ACT"), "result": next_id(results, "Result_ID", "RST")},
        "t14_backfill": {"result_record_id": T14_RESULT_RID, "revenue_actual_record_id": T14_ACTUAL_RID}, "cases": cases,
        "rollback": "仅删除本任务来源 SIMULATED_T23_D010_R3 的 Project、Actual、Performance_Result、Import_Batch；EXS000001.Max_Monthly_Revenue恢复为空、Rule_Version恢复为V04+D-010-R2；T14 Revenue_Actual_ID恢复为空。",
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = build_plan()
    if not args.apply:
        print(json.dumps({"status": "PREFLIGHT_PASSED", "plan": str(PLAN.relative_to(ROOT)), "cases": len(plan["cases"])}, ensure_ascii=False))
        return
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    # Use the existing T14 simulated operations employee; tests are different periods and dedicated projects.
    t14 = record_get("Performance_Result", T14_RESULT_RID, ["Employee_ID"])
    employee = one_link(t14.get("Employee_ID"))
    if not employee:
        raise RuntimeError("T14 模拟结果缺少 Employee_ID")
    batch_rows = [
        {"Batch_ID": ACTUAL_BATCH, "Batch_Type": "ACTUAL", "Source_Type": "SIMULATED", "Source_File": PLAN.name, "Import_Time": now, "Operator": "data-engineer/T23", "Total_Count": 3, "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
        {"Batch_ID": CALC_BATCH, "Batch_Type": "CALC", "Source_Type": "SIMULATED", "Source_File": PLAN.name, "Import_Time": now, "Operator": "data-engineer/T23", "Total_Count": 3, "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
    ]
    batch_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", T["Import_Batch"], "--json", json.dumps({"create_records": batch_rows}, ensure_ascii=False)])["record_id_list"]
    if len(batch_rids) != 2:
        raise RuntimeError(f"批次创建异常: {batch_rids}")
    project_rows = []
    for index, case in enumerate(plan["cases"]):
        case["project_id"] = f"PROJ{plan['id_starts']['project'] + index:06d}"
        project_rows.append({"Project_ID": case["project_id"], "Project_Name": case["case_id"], "Start_Date": case["start_date"], "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active", "Note": "T23 D-010-R3可回滚模拟项目"})
    project_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", T["Project"], "--json", json.dumps({"create_records": project_rows}, ensure_ascii=False)])["record_id_list"]
    actual_rows = []
    for index, (case, project_rid) in enumerate(zip(plan["cases"], project_rids)):
        case["actual_id"] = f"ACT{plan['id_starts']['actual'] + index:06d}"
        actual_rows.append({"Actual_ID": case["actual_id"], "Metric_ID": [{"id": OPS_METRIC_RID}], "Period": case["period"], "Employee_ID": [{"id": employee}], "Project_ID": [{"id": project_rid}], "Channel_ID": [{"id": CHANNEL_DOUYIN_RID}], "Actual_Value": case["revenue"], "Unit": "元", "Source_Type": "MANUAL_ENTRY", "Source_Ref": f"{SOURCE};{case['case_id']};当月退货后GSV", "Collected_By": [{"id": employee}], "Collected_Time": now, "Validation_Status": "通过", "Import_Batch_ID": [{"id": batch_rids[0]}], "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"})
    actual_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", T["Actual"], "--json", json.dumps({"create_records": actual_rows}, ensure_ascii=False)])["record_id_list"]
    result_rows = []
    for index, (case, project_rid, actual_rid) in enumerate(zip(plan["cases"], project_rids, actual_rids)):
        # Manual score creates a deterministic 95-point normal-tier test while Auto_Score still uses GSV Actual.
        manual = (95 / 0.3) - 100
        result_rows.append({"Result_ID": f"RST{plan['id_starts']['result'] + index:06d}", "Period": case["period"], "Employee_ID": [{"id": employee}], "Metric_ID": [{"id": OPS_METRIC_RID}], "Actual_ID": [{"id": actual_rid}], "Revenue_Actual_ID": [{"id": actual_rid}], "Project_ID": [{"id": project_rid}], "Exemption_Scope_ID": [{"id": SCOPE_RID}], "Target_Value_Snapshot": case["revenue"], "Rate_T1": 1, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": .8, "Score_T2": 90, "Rate_T3": .6, "Score_T3": 60, "Score_Floor": 0, "Manual_Score": manual, "Commission_Base_Type": "GSV", "Commission_Base": case["revenue"], "Commission_Ratio": case["expected_ratio"], "Rule_Version": "V04+D-010-R3", "Calc_Batch_ID": [{"id": batch_rids[1]}], "Review_Status": "待复核", "Status": "Active", "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Note": json.dumps({"t23_case": case["case_id"], "expected": {k: case[k] for k in ("expected_days", "expected_exempt", "expected_ratio", "expected_amount")}}, ensure_ascii=False)})
    result_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", T["Performance_Result"], "--json", json.dumps({"create_records": result_rows}, ensure_ascii=False)])["record_id_list"]
    call(["+record-batch-update", "--base-token", BASE, "--table-id", T["Exemption_Scope"], "--json", json.dumps({"update_records": {SCOPE_RID: {"Max_Monthly_Revenue": 1000000, "Rule_Version": "V04+D-010-R3", "Update_Time": now, "Note": "D-010-R2来源规则经 CHG-D010-R3-001 升级：阈值=1,000,000元；营收未知时结果留空待确认。"}}}, ensure_ascii=False)])
    call(["+record-batch-update", "--base-token", BASE, "--table-id", T["Performance_Result"], "--json", json.dumps({"update_records": {T14_RESULT_RID: {"Revenue_Actual_ID": [{"id": T14_ACTUAL_RID}], "Update_Time": now}}}, ensure_ascii=False)])
    for rid, count in ((batch_rids[0], 3), (batch_rids[1], 3)):
        call(["+record-batch-update", "--base-token", BASE, "--table-id", T["Import_Batch"], "--json", json.dumps({"update_records": {rid: {"Success_Count": count, "Fail_Count": 0, "Status": "Success", "Update_Time": now}}}, ensure_ascii=False)])
    execution = {"task": "T23", "status": "APPLY_PASSED", "source": SOURCE, "created_at": now, "scope_record_id": SCOPE_RID, "scope_threshold": 1000000, "batches": batch_rids, "project_record_ids": project_rids, "actual_record_ids": actual_rids, "performance_result_record_ids": result_rids, "t14_revenue_backfill": {"result_record_id": T14_RESULT_RID, "revenue_actual_record_id": T14_ACTUAL_RID}, "cases": plan["cases"]}
    EXEC.write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ROLLBACK.write_text(json.dumps({"task": "T23", "rollback_scope": "仅删除本任务来源SIMULATED_T23_D010_R3的 Project、Actual、Performance_Result、Import_Batch；EXS000001.Max_Monthly_Revenue恢复为空；T14 Revenue_Actual_ID恢复为空。", **execution}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "APPLY_PASSED", "execution": str(EXEC.relative_to(ROOT)), "rollback": str(ROLLBACK.relative_to(ROOT)), "counts": {"projects": 3, "actuals": 3, "results": 3, "batches": 2}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        ERROR.write_text(json.dumps({"task": "T23", "status": "FAILED", "error": str(exc), "timestamp": datetime.now().astimezone().isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED", "error": str(exc), "error_log": str(ERROR.relative_to(ROOT))}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
