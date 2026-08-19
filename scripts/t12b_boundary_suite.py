#!/usr/bin/env python3
"""T12b：精确边界/异常分支模拟数据。

默认只生成可审计计划；--apply 才创建独立的 ACTUAL/SIMULATED 批次、Actual 和
Performance_Result。绝不更新既有业务记录或公式。所有新增记录使用 2026-08~11，
避开 T9a 的 2026-07 业务键；执行结果及可回滚记录清单写入 data/output。
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
TABLE = {
    "Employee": "tblc59aB4EnSxkQv", "Metric": "tbldKtdIVv8nnTyX",
    "Actual": "tbli9VhcUFjVDeNd", "Performance_Result": "tbl6tFtVKExFUTWo",
    "Import_Batch": "tblHV3JoVR9AEETw", "Error_Log": "tbl4ZpuuOxZacWgj",
}
SOURCE = "SIMULATED_T12B_BOUNDARY"
ACTUAL_BATCH_ID = "IB-T12B-ACTUAL-20260817-01"
CALC_BATCH_ID = "IB-T12B-CALC-20260817-01"
PLAN = ROOT / "data/output/T12b边界异常模拟计划.json"
EXECUTION = ROOT / "data/output/T12b边界异常执行结果.json"
ROLLBACK = ROOT / "data/output/T12b边界异常回滚清单.json"
ERROR_OUT = ROOT / "data/output/T12b边界异常错误日志.json"
CORRECTION = ROOT / "data/output/T12b梯度精确边界修正记录.json"
BASELINE = ROOT / "data/output/T12b提成基数零值补充记录.json"
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

# 从 V04 原文转写的结果行参数快照；仅用于创建测试结果，不修改 Base 公式。
GENERIC = {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": .8, "Score_T2": 90, "Rate_T3": .6, "Score_T3": 60, "Score_Floor": 0}
LIVE001 = GENERIC
LIVE002 = {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 80, "Score_Floor": 0}
LIVE003 = {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 60, "Score_Floor": 0}


def call(args: list[str]) -> dict[str, Any]:
    p = subprocess.run([CLI, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        response = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli 非 JSON 输出：{p.stdout[-500:]} / {p.stderr[-500:]}") from exc
    if p.returncode != 0 or not response.get("ok"):
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response["data"]


def records(table: str, fields: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLE[table], "--limit", "200", "--format", "json", "--offset", str(offset)]
        for field in fields:
            args += ["--field-id", field]
        data = call(args)
        for rid, values in zip(data["record_id_list"], data["data"]):
            result.append({**dict(zip(data["fields"], values)), "_record_id": rid})
        if not data.get("has_more"):
            return result
        offset += len(data["record_id_list"])


def one_link(value: Any) -> str | None:
    return value[0]["id"] if isinstance(value, list) and value else None


def next_id(rows: list[dict[str, Any]], field: str, prefix: str) -> int:
    pattern = re.compile(rf"^{prefix}(\d{{6}})$")
    values, malformed = [], []
    for row in rows:
        value = row.get(field)
        if value in (None, ""):
            continue
        match = pattern.fullmatch(str(value))
        (values if match else malformed).append(int(match.group(1)) if match else value)
    if malformed:
        raise RuntimeError(f"{field} 存在非标准编号，拒绝分配新编号：{malformed[:10]}")
    return max(values, default=0) + 1


def build_plan() -> dict[str, Any]:
    employees = records("Employee", ["Employee_ID", "Position_ID", "Perf_Participate_Status", "Status"])
    metrics = records("Metric", ["Metric_ID", "Position_ID", "Scoring_Type", "Status"])
    actuals = records("Actual", ["Actual_ID", "Employee_ID", "Metric_ID", "Period", "Source", "Status"])
    results = records("Performance_Result", ["Result_ID", "Employee_ID", "Metric_ID", "Period", "Source", "Status"])
    active_metrics = {m["Metric_ID"]: m for m in metrics if m.get("Status") == "Active"}
    required = ["MET-V04-IE-OPS-001", "MET-V04-IE-LIVE-001", "MET-V04-IE-LIVE-002", "MET-V04-IE-LIVE-003"]
    missing = [mid for mid in required if mid not in active_metrics]
    if missing:
        raise RuntimeError(f"缺少 Active Metric：{missing}")
    participant_by_pos: dict[str, list[dict[str, Any]]] = {}
    for employee in employees:
        pos = one_link(employee.get("Position_ID"))
        if employee.get("Status") == "Active" and employee.get("Perf_Participate_Status") == "确认参与" and pos:
            participant_by_pos.setdefault(pos, []).append(employee)
    ops = participant_by_pos.get(one_link(active_metrics["MET-V04-IE-OPS-001"].get("Position_ID")) or "", [])
    live = participant_by_pos.get(one_link(active_metrics["MET-V04-IE-LIVE-001"].get("Position_ID")) or "", [])
    if len(ops) < 1 or len(live) < 1:
        raise RuntimeError(f"参与绩效的 OPS/LIVE 人员不足：OPS={len(ops)} LIVE={len(live)}")
    # 同一人员可跨月复用；每一业务键（员工、指标、期间）均须无既有 Active 记录。
    ops_employee, live_employee = ops[0], live[0]
    cases: list[dict[str, Any]] = []
    for period, label, actual, expected in [
        ("2026-08", "达成率精确临界 rate=1.0", 100.0, 100.0),
        ("2026-09", "达成率精确临界 rate=0.8", 80.0, 90.0),
        ("2026-10", "达成率精确临界 rate=0.6", 60.0, 60.0),
        ("2026-11", "达成率型 Actual=0", 0.0, 0.0),
    ]:
        cases.append({"case_id": f"T12B-RATE-{period[-2:]}", "kind": "rate", "label": label, "period": period,
                      "employee": ops_employee, "metric": active_metrics["MET-V04-IE-OPS-001"], "actual_value": actual,
                      "target_snapshot": 100.0, "expected_auto_score": expected, "params": GENERIC})
    for period, label, target in [("2026-12", "Target=null：无错误得分", None), ("2027-01", "Target=0：除零保护、无错误得分", 0.0)]:
        cases.append({"case_id": f"T12B-TARGET-{period[-2:]}", "kind": "target_exception", "label": label, "period": period,
                      "employee": ops_employee, "metric": active_metrics["MET-V04-IE-OPS-001"], "actual_value": 100.0,
                      "target_snapshot": target, "expected_auto_score": None, "params": GENERIC})
    # LIVE 每期三指标；三项自动得分的固定贡献=50，LIVE-001 的 Manual_Score 补足到精确总分。
    # LIVE 三项自动分的固定贡献为 50；LIVE-001 权重=0.1，故人工补分为
    # (目标总分-50)/0.1，确保 Monthly_Total 落在每个精确临界点。
    for period, total, manual in [("2026-08", 60.0, 100.0), ("2026-09", 80.0, 300.0), ("2026-10", 100.0, 500.0), ("2026-11", 160.0, 1100.0)]:
        cases.extend([
            {"case_id": f"T12B-TIER-{period[-2:]}-01", "kind": "tier", "label": f"梯度精确边界/超上限：总分={total}", "period": period, "employee": live_employee, "metric": active_metrics["MET-V04-IE-LIVE-001"], "actual_value": 100.0, "target_snapshot": 100.0, "expected_auto_score": 100.0, "manual_score": manual, "params": LIVE001, "expected_total": total},
            {"case_id": f"T12B-TIER-{period[-2:]}-02", "kind": "tier", "label": f"梯度精确边界/超上限：总分={total}", "period": period, "employee": live_employee, "metric": active_metrics["MET-V04-IE-LIVE-002"], "actual_value": 0, "target_snapshot": None, "expected_auto_score": 100.0, "params": LIVE002, "expected_total": total},
            {"case_id": f"T12B-TIER-{period[-2:]}-03", "kind": "tier", "label": f"梯度精确边界/超上限：总分={total}", "period": period, "employee": live_employee, "metric": active_metrics["MET-V04-IE-LIVE-003"], "actual_value": 0, "target_snapshot": None, "expected_auto_score": 100.0, "params": LIVE003, "expected_total": total},
        ])
    # 定性类无 Actual：选择 ACTIVE LIVE 岗位不存在该类型，故以任一参与人员所属的定性 Metric 为准。
    qualitative = next((m for m in active_metrics.values() if m.get("Scoring_Type") == "定性等级型"), None)
    if not qualitative:
        raise RuntimeError("缺少定性等级型 Active Metric")
    q_people = participant_by_pos.get(one_link(qualitative.get("Position_ID")) or "", [])
    if not q_people:
        raise RuntimeError("定性等级型 Metric 无确认参与员工")
    cases.append({"case_id": "T12B-MANUAL-QUAL-08", "kind": "qualitative", "label": "定性指标无 Actual，按 D-009.3 人工分场景", "period": "2026-08", "employee": q_people[0], "metric": qualitative, "actual_value": None, "target_snapshot": None, "expected_auto_score": None, "manual_score": 70.0, "params": {}})
    existing_actual_keys = {(one_link(a.get("Employee_ID")), one_link(a.get("Metric_ID")), a.get("Period")) for a in actuals if a.get("Status") == "Active"}
    existing_result_keys = {(one_link(r.get("Employee_ID")), one_link(r.get("Metric_ID")), r.get("Period")) for r in results if r.get("Status") == "Active"}
    all_case_keys = [(c["employee"]["_record_id"], c["metric"]["_record_id"], c["period"]) for c in cases]
    duplicate_case_keys = {key for key in all_case_keys if all_case_keys.count(key) > 1}
    collisions = [c["case_id"] for c, key in zip(cases, all_case_keys) if key in duplicate_case_keys or key in existing_actual_keys or key in existing_result_keys]
    if collisions:
        raise RuntimeError(f"发现既有 Active 业务键冲突，拒绝写入：{collisions}")
    actual_cases = [c for c in cases if c["actual_value"] is not None]
    serializable = [{k: (v["Employee_ID"] if k == "employee" else v["Metric_ID"] if k == "metric" else v) for k, v in c.items() if k not in {"params"}} | {"parameter_snapshot": c["params"]} for c in cases]
    return {"task": "T12b", "generated_at": datetime.now().astimezone().isoformat(), "mode": "PREFLIGHT", "source": SOURCE,
            "actual_batch_id": ACTUAL_BATCH_ID, "calc_batch_id": CALC_BATCH_ID, "counts": {"cases": len(cases), "actuals": len(actual_cases), "results": len(cases)},
            "actual_id_start": next_id(actuals, "Actual_ID", "ACT"), "result_id_start": next_id(results, "Result_ID", "RST"), "cases": serializable, "_cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="通过预检后创建新批次及测试记录")
    parser.add_argument("--correct-tier-manual-scores", action="store_true", help="仅修正本任务已创建四条 LIVE 精确临界结果的人工补分")
    parser.add_argument("--set-zero-commission-base", action="store_true", help="仅为本任务测试结果补写显式0提成基数")
    args = parser.parse_args()
    if sum(bool(x) for x in (args.apply, args.correct_tier_manual_scores, args.set_zero_commission_base)) > 1:
        parser.error("--apply、--correct-tier-manual-scores、--set-zero-commission-base 不能同时使用")
    if not Path(CLI).is_file():
        raise RuntimeError(f"lark-cli 不可用：{CLI}")
    if args.correct_tier_manual_scores:
        wanted = {"RST000168": (50.0, 100.0), "RST000171": (150.0, 300.0), "RST000174": (250.0, 500.0), "RST000177": (550.0, 1100.0)}
        rows = records("Performance_Result", ["Result_ID", "Manual_Score", "Source", "Status"])
        selected = {row.get("Result_ID"): row for row in rows if row.get("Result_ID") in wanted}
        if set(selected) != set(wanted):
            raise RuntimeError(f"未找到全部 T12b 梯度结果：{sorted(set(wanted)-set(selected))}")
        updates = {}
        for result_id, (prior, replacement) in wanted.items():
            row = selected[result_id]
            if row.get("Source") != SOURCE or row.get("Status") != "Active" or float(row.get("Manual_Score")) != prior:
                raise RuntimeError(f"{result_id} 前置状态不符，拒绝覆盖：{row}")
            updates[row["_record_id"]] = {"Manual_Score": replacement, "Update_Time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")}
        call(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE["Performance_Result"], "--json", json.dumps({"update_records": updates}, ensure_ascii=False)])
        CORRECTION.write_text(json.dumps({"task": "T12b", "type": "精确边界人工补分修正", "reason": "首次执行未按 LIVE-001 的实际权重0.1换算；只更新本任务四条测试结果，不改 Base 公式", "updates": [{"result_id": key, "prior_manual_score": prior, "new_manual_score": replacement} for key, (prior, replacement) in wanted.items()], "rollback": "将四条 Manual_Score 依次恢复为 50/150/250/550 后重跑独立校验"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "CORRECTION_APPLIED", "record_count": len(updates), "record": str(CORRECTION.relative_to(ROOT))}, ensure_ascii=False)); return
    if args.set_zero_commission_base:
        rows = records("Performance_Result", ["Result_ID", "Commission_Base", "Source", "Status"])
        selected = [row for row in rows if row.get("Source") == SOURCE and row.get("Status") == "Active"]
        if len(selected) != 19 or any(row.get("Commission_Base") not in (None, "") for row in selected):
            raise RuntimeError(f"T12b 测试结果提成基数前置不符：数量={len(selected)}")
        now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        call(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE["Performance_Result"], "--json", json.dumps({"update_records": {row["_record_id"]: {"Commission_Base": 0, "Update_Time": now} for row in selected}}, ensure_ascii=False)])
        BASELINE.write_text(json.dumps({"task": "T12b", "type": "测试提成基数显式0补充", "reason": "边界用例不测试金额；显式0使 Commission_Ratio/Amount 的空值语义与既有 161 条一致", "updated_result_ids": [row["Result_ID"] for row in selected], "prior_value": None, "new_value": 0, "rollback": "将 listed Result_ID 的 Commission_Base 恢复为空后重跑独立校验"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ZERO_COMMISSION_BASE_APPLIED", "record_count": len(selected), "record": str(BASELINE.relative_to(ROOT))}, ensure_ascii=False)); return
    plan = build_plan()
    PLAN.write_text(json.dumps({k: v for k, v in plan.items() if k != "_cases"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.apply:
        print(json.dumps({"status": "PREFLIGHT_PASSED", "plan": str(PLAN.relative_to(ROOT)), "counts": plan["counts"]}, ensure_ascii=False)); return
    cases = plan["_cases"]
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    # 批次先行，确保每条 Actual/Result 的来源可追溯。
    batch_rows = [
        {"Batch_ID": ACTUAL_BATCH_ID, "Batch_Type": "ACTUAL", "Source_Type": "SIMULATED", "Source_File": PLAN.name, "Import_Time": now, "Operator": "data-engineer/T12b", "Total_Count": plan["counts"]["actuals"], "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
        {"Batch_ID": CALC_BATCH_ID, "Batch_Type": "CALC", "Source_Type": "SIMULATED", "Source_File": PLAN.name, "Import_Time": now, "Operator": "data-engineer/T12b", "Total_Count": plan["counts"]["results"], "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
    ]
    batch_ids = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Import_Batch"], "--json", json.dumps({"create_records": batch_rows}, ensure_ascii=False)]).get("record_id_list", [])
    if len(batch_ids) != 2:
        raise RuntimeError(f"Import_Batch 创建确认数异常：{batch_ids}")
    actual_batch_rid, calc_batch_rid = batch_ids
    actual_seq, result_seq = plan["actual_id_start"], plan["result_id_start"]
    actual_rows, actual_case_ids = [], []
    for case in cases:
        if case["actual_value"] is None:
            continue
        case["actual_id"] = f"ACT{actual_seq:06d}"; actual_seq += 1; actual_case_ids.append(case["case_id"])
        actual_rows.append({"Actual_ID": case["actual_id"], "Metric_ID": [{"id": case["metric"]["_record_id"]}], "Period": case["period"], "Employee_ID": [{"id": case["employee"]["_record_id"]}], "Actual_Value": case["actual_value"], "Unit": "测试", "Source_Type": "MANUAL_ENTRY", "Source_Ref": f"{SOURCE}; {case['case_id']}; {case['label']}", "Collected_By": [{"id": case["employee"]["_record_id"]}], "Collected_Time": now, "Validation_Status": "通过", "Import_Batch_ID": [{"id": actual_batch_rid}], "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"})
    actual_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Actual"], "--json", json.dumps({"create_records": actual_rows}, ensure_ascii=False)]).get("record_id_list", [])
    if len(actual_rids) != len(actual_rows):
        raise RuntimeError(f"Actual 创建确认数异常：期望{len(actual_rows)}，收到{len(actual_rids)}")
    actual_rid_by_id = {row["Actual_ID"]: rid for row, rid in zip(actual_rows, actual_rids)}
    result_rows = []
    for case in cases:
        row = {"Result_ID": f"RST{result_seq:06d}", "Period": case["period"], "Employee_ID": [{"id": case["employee"]["_record_id"]}], "Metric_ID": [{"id": case["metric"]["_record_id"]}], "Actual_ID": [{"id": actual_rid_by_id[case["actual_id"]]}] if case.get("actual_id") else None, "Target_ID": None, "Target_Value_Snapshot": case["target_snapshot"], "Rule_Version": "V04", "Calc_Batch_ID": [{"id": calc_batch_rid}], "Manual_Score": case.get("manual_score"), "Commission_Base": 0, "Review_Status": "待复核", "Status": "Active", "Source": SOURCE, "Create_Time": now, "Update_Time": now}
        row.update(case["params"]); result_rows.append(row); case["result_id"] = row["Result_ID"]; result_seq += 1
    result_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Performance_Result"], "--json", json.dumps({"create_records": result_rows}, ensure_ascii=False)]).get("record_id_list", [])
    if len(result_rids) != len(result_rows):
        raise RuntimeError(f"Performance_Result 创建确认数异常：期望{len(result_rows)}，收到{len(result_rids)}")
    for rid, total in ((actual_batch_rid, len(actual_rows)), (calc_batch_rid, len(result_rows))):
        call(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE["Import_Batch"], "--json", json.dumps({"update_records": {rid: {"Success_Count": total, "Fail_Count": 0, "Status": "Success", "Update_Time": now}}}, ensure_ascii=False)])
    execution = {"task": "T12b", "status": "APPLY_PASSED", "source": SOURCE, "created_at": now, "batches": {"actual": {"id": ACTUAL_BATCH_ID, "record_id": actual_batch_rid}, "calc": {"id": CALC_BATCH_ID, "record_id": calc_batch_rid}}, "created": {"actual_record_ids": actual_rids, "performance_result_record_ids": result_rids}, "cases": [{"case_id": c["case_id"], "actual_id": c.get("actual_id"), "result_id": c["result_id"], "expected_auto_score": c["expected_auto_score"], "expected_total": c.get("expected_total")} for c in cases]}
    EXECUTION.write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ROLLBACK.write_text(json.dumps({"task": "T12b", "rollback_scope": "仅删除本任务创建的两批次、Actual 和 Performance_Result；不修改任何既有记录或 Base 公式", "execution": EXECUTION.name, "actual_record_ids": actual_rids, "performance_result_record_ids": result_rids, "import_batch_record_ids": batch_ids}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "APPLY_PASSED", "execution": str(EXECUTION.relative_to(ROOT)), "rollback": str(ROLLBACK.relative_to(ROOT)), "counts": plan["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        ERROR_OUT.write_text(json.dumps({"task": "T12b", "status": "FAILED", "error": str(exc), "timestamp": datetime.now().astimezone().isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED", "error": str(exc), "error_log": str(ERROR_OUT.relative_to(ROOT))}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
