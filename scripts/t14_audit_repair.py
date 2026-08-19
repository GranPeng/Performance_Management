#!/usr/bin/env python3
"""T14：审计链对齐与 D-010 非零比例豁免验证。

默认生成只读的最终参数快照；--apply-d010 经预检后仅创建独立的
ACTUAL/SIMULATED Project、Import_Batch、Actual、Performance_Result 测试记录。
不更新既有业务记录、Base 公式或规则。每次写入均写入执行记录和回滚清单；
异常会写入错误日志并返回非零退出码。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from base_rate_config import resolve_base_rate

ROOT = Path(__file__).resolve().parents[1]
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = {
    "Employee": "tblc59aB4EnSxkQv", "Metric": "tbldKtdIVv8nnTyX",
    "Actual": "tbli9VhcUFjVDeNd", "Performance_Result": "tbl6tFtVKExFUTWo",
    "Import_Batch": "tblHV3JoVR9AEETw", "Project": "tbl1GO2vR9ZAqPbr",
    "Commission_Tier": "tblkZUoHYwBIvDYe",
}
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
SOURCE = "SIMULATED_T14_D010_NONZERO"
ACTUAL_BATCH_ID = "IB-T14-ACTUAL-20260817-01"
CALC_BATCH_ID = "IB-T14-CALC-20260817-01"
PROJECT_ID = "PROJ900014"
PERIOD = "2027-02"
SNAPSHOT = ROOT / "data/output/T14最终参数快照.json"
D010_PLAN = ROOT / "data/output/T14_D010非零比例豁免计划.json"
D010_EXECUTION = ROOT / "data/output/T14_D010非零比例豁免执行结果.json"
D010_ROLLBACK = ROOT / "data/output/T14_D010非零比例豁免回滚清单.json"
ERROR_OUT = ROOT / "data/output/T14审计链修复错误日志.json"
CORRECTION = ROOT / "data/output/T12b梯度精确边界修正记录.json"
EPS = 1e-6
GENERIC = {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": .8, "Score_T2": 90, "Rate_T3": .6, "Score_T3": 60, "Score_Floor": 0}


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
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLE[table], "--limit", "200", "--format", "json", "--offset", str(offset)]
        for field in fields:
            args += ["--field-id", field]
        data = call(args)
        for rid, vals in zip(data["record_id_list"], data["data"]):
            out.append({**dict(zip(data["fields"], vals)), "_record_id": rid})
        if not data.get("has_more"):
            return out
        offset += len(data["record_id_list"])


def link_id(value: Any) -> str | None:
    return value[0]["id"] if isinstance(value, list) and value else None


def num(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def next_id(rows: list[dict[str, Any]], field: str, prefix: str) -> int:
    pat = re.compile(rf"^{prefix}(\d{{6}})$")
    ids = []
    for row in rows:
        value = row.get(field)
        if value in (None, ""):
            continue
        matched = pat.fullmatch(str(value))
        if not matched:
            raise RuntimeError(f"{field} 存在非标准编号，拒绝分配新编号：{value}")
        ids.append(int(matched.group(1)))
    return max(ids, default=0) + 1


def exact_t12b_snapshot() -> dict[str, Any]:
    correction = json.loads(CORRECTION.read_text(encoding="utf-8"))
    corrected = {x["result_id"]: x for x in correction["updates"]}
    wanted = set(corrected)
    results = records("Performance_Result", ["Result_ID", "Achievement_Rate", "Auto_Score", "Manual_Score", "Final_Score", "Weight", "Weighted_Score", "Monthly_Total", "Source", "Status"])
    found = {r.get("Result_ID"): r for r in results if r.get("Result_ID") in wanted}
    if set(found) != wanted:
        raise RuntimeError(f"缺少 T12b 修正结果：{sorted(wanted-set(found))}")
    lines = []
    for result_id in sorted(wanted):
        r, c = found[result_id], corrected[result_id]
        manual = num(r.get("Manual_Score"))
        if r.get("Source") != "SIMULATED_T12B_BOUNDARY" or r.get("Status") != "Active":
            raise RuntimeError(f"{result_id} 来源或状态不符：{r}")
        if manual is None or abs(manual - float(c["new_manual_score"])) > EPS:
            raise RuntimeError(f"{result_id} Base 人工分未对齐修正记录：Base={manual}, correction={c}")
        rate, auto, weight, total = num(r.get("Achievement_Rate")), num(r.get("Auto_Score")), num(r.get("Weight")), num(r.get("Monthly_Total"))
        expected_final = (auto or 0.0) + manual
        expected_weighted = expected_final * (weight or 0.0)
        if abs((num(r.get("Final_Score")) or 0.0) - expected_final) > EPS or abs((num(r.get("Weighted_Score")) or 0.0) - expected_weighted) > EPS:
            raise RuntimeError(f"{result_id} Base 公式结果无法由快照复算：{r}")
        lines.append({
            "result_id": result_id, "base_record_id": r["_record_id"], "achievement_rate": rate,
            "auto_score": auto, "manual_score": manual, "weight": weight,
            "formula": "Final_Score=Auto_Score+Manual_Score；Weighted_Score=Final_Score×Weight；Monthly_Total=同员工同期间各 Weighted_Score 合计",
            "final_score": num(r.get("Final_Score")), "weighted_score": num(r.get("Weighted_Score")), "monthly_total": total,
            "correction_reason": correction["reason"], "correction_prior_manual_score": c["prior_manual_score"],
        })
    return {
        "task": "T14", "type": "T12b审计链最终参数快照", "generated_at": datetime.now().astimezone().isoformat(),
        "source_documents": ["T12b边界异常模拟计划.json", CORRECTION.name, "T12b边界异常执行结果.json"],
        "rule_basis": "V04；LIVE-001 实际权重为0.1，三项自动分固定加权贡献50，Manual_Score=(目标总分-50)/0.1",
        "reason_for_plan_difference": correction["reason"], "records": lines,
        "verification": "逐条读取 Base 结果，确认人工分与修正记录一致，并以快照公式复算 Final_Score/Weighted_Score；Monthly_Total 取同一 Base 读取值，交由独立全量校验器复核。",
    }


def build_d010_plan(base_rate_override: float | None = None) -> dict[str, Any]:
    employees = records("Employee", ["Employee_ID", "Position_ID", "Perf_Participate_Status", "Status"])
    metrics = records("Metric", ["Metric_ID", "Position_ID", "Weight", "Scoring_Type", "Status"])
    actuals = records("Actual", ["Actual_ID", "Employee_ID", "Metric_ID", "Period", "Status"])
    results = records("Performance_Result", ["Result_ID", "Employee_ID", "Metric_ID", "Period", "Status"])
    tiers = records("Commission_Tier", ["Position_ID", "Score_Lower", "Coefficient", "Ratio_Value", "Base_Rate", "Status"])
    metric = next((m for m in metrics if m.get("Metric_ID") == "MET-V04-IE-OPS-001" and m.get("Status") == "Active"), None)
    if not metric:
        raise RuntimeError("缺少 Active MET-V04-IE-OPS-001")
    position = link_id(metric.get("Position_ID"))
    employee = next((e for e in employees if e.get("Status") == "Active" and e.get("Perf_Participate_Status") == "确认参与" and link_id(e.get("Position_ID")) == position), None)
    if not employee:
        raise RuntimeError("缺少可用于 D-010 的确认参与运营岗位员工")
    key = (employee["_record_id"], metric["_record_id"], PERIOD)
    existing_actual = {(link_id(x.get("Employee_ID")), link_id(x.get("Metric_ID")), x.get("Period")) for x in actuals if x.get("Status") == "Active"}
    existing_result = {(link_id(x.get("Employee_ID")), link_id(x.get("Metric_ID")), x.get("Period")) for x in results if x.get("Status") == "Active"}
    if key in existing_actual or key in existing_result:
        raise RuntimeError(f"D-010 业务键已存在，拒绝重复写入：{key}")
    weight = num(metric.get("Weight"))
    if weight is None or weight <= 0:
        raise RuntimeError(f"D-010 Metric 权重非法：{metric.get('Weight')}")
    regular_total = 100.0 * weight
    # D-010-R1 豁免提成为该岗位配置的 Base_Rate×达成GSV，直接跳过梯度和考核系数。
    # --base-rate 只覆盖本地预检预期，不修改任何 Base 数据或公式。
    matched = next((tier for tier in tiers if tier.get("Status") == "Active" and link_id(tier.get("Position_ID")) == position), None)
    if not matched:
        raise RuntimeError("D-010 缺少运营岗 Active Commission_Tier，无法确认提成模型已配置")
    ratio = resolve_base_rate(tiers, position, base_rate_override)
    return {
        "task": "T14", "case_id": "T14-D010-EXEMPT-NONZERO-01", "mode": "PREFLIGHT", "source": SOURCE,
        "actual_batch_id": ACTUAL_BATCH_ID, "calc_batch_id": CALC_BATCH_ID, "period": PERIOD,
        "project": {"project_id": PROJECT_ID, "start_date": "2027-01-15", "expected_project_run_days_lt": 90},
        "employee": {"employee_id": employee["Employee_ID"], "record_id": employee["_record_id"]},
        "metric": {"metric_id": metric["Metric_ID"], "record_id": metric["_record_id"], "weight": weight},
        "input": {"actual_value": 100.0, "target_snapshot": 100.0, "commission_base": 100.0, "commission_ratio": ratio, "expected_commission_amount": 100.0 * ratio},
        "regular_score_for_tier_selection": regular_total,
        "tier_selection": {"score_lower": num(matched.get("Score_Lower")), "coefficient": num(matched.get("Coefficient")), "ratio_value": num(matched.get("Ratio_Value"))},
        "expected": {"is_exempt": True, "auto_score": 100.0, "weighted_score": 100.0 * weight, "commission_amount_gt": 0.0, "commission_rule": "D-010-R1：Commission_Tier.Base_Rate×达成GSV，跳过梯度和考核系数"},
        "actual_id_start": next_id(actuals, "Actual_ID", "ACT"), "result_id_start": next_id(results, "Result_ID", "RST"),
    }


def read_result(result_rid: str) -> dict[str, Any]:
    fields = ["Result_ID", "Project_Run_Days", "Is_Exempt", "Auto_Score", "Final_Score", "Weighted_Score", "Monthly_Total", "Commission_Base", "Commission_Ratio", "Commission_Amount", "Status", "Source"]
    return next((x for x in records("Performance_Result", fields) if x["_record_id"] == result_rid), None)


def apply_d010(plan: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    batches = records("Import_Batch", ["Batch_ID"])
    existing_batch_ids = {x.get("Batch_ID") for x in batches}
    if ACTUAL_BATCH_ID in existing_batch_ids or CALC_BATCH_ID in existing_batch_ids:
        raise RuntimeError("T14 批次 ID 已存在，拒绝覆盖")
    projects = records("Project", ["Project_ID", "Status"])
    if any(x.get("Project_ID") == PROJECT_ID for x in projects):
        raise RuntimeError("T14 项目 ID 已存在，拒绝覆盖")
    project_payload = {"Project_ID": PROJECT_ID, "Project_Name": "T14模拟新项目（D-010非零提成验证）", "Start_Date": plan["project"]["start_date"], "Brand": "SIMULATED", "Source": SOURCE, "Note": "D-010 豁免且非零比例提成验证；按回滚清单删除", "Status": "Active"}
    project_rid = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Project"], "--json", json.dumps({"create_records": [project_payload]}, ensure_ascii=False)]).get("record_id_list", [None])[0]
    if not project_rid:
        raise RuntimeError("T14 模拟项目创建失败")
    try:
        batch_rows = [
            {"Batch_ID": ACTUAL_BATCH_ID, "Batch_Type": "ACTUAL", "Source_Type": "SIMULATED", "Source_File": D010_PLAN.name, "Import_Time": now, "Operator": "data-engineer/T14", "Total_Count": 1, "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
            {"Batch_ID": CALC_BATCH_ID, "Batch_Type": "CALC", "Source_Type": "SIMULATED", "Source_File": D010_PLAN.name, "Import_Time": now, "Operator": "data-engineer/T14", "Total_Count": 1, "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"},
        ]
        batch_rids = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Import_Batch"], "--json", json.dumps({"create_records": batch_rows}, ensure_ascii=False)]).get("record_id_list", [])
        if len(batch_rids) != 2:
            raise RuntimeError(f"T14 批次创建异常：{batch_rids}")
        actual_id = f"ACT{plan['actual_id_start']:06d}"
        actual_payload = {"Actual_ID": actual_id, "Metric_ID": [{"id": plan["metric"]["record_id"]}], "Period": PERIOD, "Employee_ID": [{"id": plan["employee"]["record_id"]}], "Actual_Value": plan["input"]["actual_value"], "Unit": "测试", "Source_Type": "MANUAL_ENTRY", "Source_Ref": "T14-D010-EXEMPT-NONZERO-01", "Collected_By": [{"id": plan["employee"]["record_id"]}], "Collected_Time": now, "Validation_Status": "通过", "Import_Batch_ID": [{"id": batch_rids[0]}], "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"}
        actual_rid = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Actual"], "--json", json.dumps({"create_records": [actual_payload]}, ensure_ascii=False)]).get("record_id_list", [None])[0]
        if not actual_rid:
            raise RuntimeError("T14 Actual 创建失败")
        result_id = f"RST{plan['result_id_start']:06d}"
        result_payload = {"Result_ID": result_id, "Period": PERIOD, "Employee_ID": [{"id": plan["employee"]["record_id"]}], "Metric_ID": [{"id": plan["metric"]["record_id"]}], "Actual_ID": [{"id": actual_rid}], "Project_ID": [{"id": project_rid}], "Target_ID": None, "Target_Value_Snapshot": plan["input"]["target_snapshot"], "Rule_Version": "V04", "Calc_Batch_ID": [{"id": batch_rids[1]}], "Commission_Base": plan["input"]["commission_base"], "Commission_Ratio": plan["input"]["commission_ratio"], "Review_Status": "待复核", "Status": "Active", "Source": SOURCE, "Create_Time": now, "Update_Time": now}
        result_payload.update(GENERIC)
        result_rid = call(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE["Performance_Result"], "--json", json.dumps({"create_records": [result_payload]}, ensure_ascii=False)]).get("record_id_list", [None])[0]
        if not result_rid:
            raise RuntimeError("T14 Performance_Result 创建失败")
        time.sleep(8)
        readback = read_result(result_rid)
        if not readback:
            raise RuntimeError("T14 创建结果无法读取")
        days, auto, weighted = num(readback.get("Project_Run_Days")), num(readback.get("Auto_Score")), num(readback.get("Weighted_Score"))
        base, ratio, amount = num(readback.get("Commission_Base")), num(readback.get("Commission_Ratio")), num(readback.get("Commission_Amount"))
        expected_weighted = plan["expected"]["weighted_score"]
        checks = {"project_run_days_lt_90": days is not None and days < 90, "is_exempt": str(readback.get("Is_Exempt")).lower() == "true", "auto_score_100": auto is not None and abs(auto - 100.0) <= EPS, "weighted_score_normal": weighted is not None and abs(weighted - expected_weighted) <= EPS, "ratio_matches_configured_base_rate": ratio is not None and abs(ratio - plan["input"]["commission_ratio"]) <= EPS, "amount_equals_base_rate_times_gsv": base is not None and ratio is not None and amount is not None and abs(amount - base * ratio) <= EPS, "amount_positive": amount is not None and amount > 0}
        if not all(checks.values()):
            raise RuntimeError(f"T14 D-010 读回断言失败：{checks}，readback={readback}")
        for rid in batch_rids:
            call(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE["Import_Batch"], "--json", json.dumps({"update_records": {rid: {"Success_Count": 1, "Fail_Count": 0, "Status": "Success", "Update_Time": now}}}, ensure_ascii=False)])
        return {"task": "T14", "status": "APPLY_PASSED", "source": SOURCE, "case_id": plan["case_id"], "created_at": now, "batches": {"actual": {"id": ACTUAL_BATCH_ID, "record_id": batch_rids[0]}, "calc": {"id": CALC_BATCH_ID, "record_id": batch_rids[1]}}, "created": {"project_record_id": project_rid, "actual_record_id": actual_rid, "performance_result_record_id": result_rid}, "input": plan["input"], "read_back": readback, "assertions": checks}
    except Exception:
        # 不做自动删除：保留失败现场供审计；错误日志与可执行回滚清单由外层记录。
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-d010", action="store_true")
    parser.add_argument("--base-rate", type=float, help="只读验证用 Base_Rate 覆盖值；禁止与 --apply-d010 同用")
    args = parser.parse_args()
    if not Path(CLI).is_file():
        raise RuntimeError(f"lark-cli 不可用：{CLI}")
    if args.apply_d010 and args.base_rate is not None:
        raise RuntimeError("--base-rate 只用于只读预检，禁止与 --apply-d010 同用")
    snapshot = exact_t12b_snapshot()
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan = build_d010_plan(args.base_rate)
    D010_PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.apply_d010:
        print(json.dumps({"status": "PREFLIGHT_PASSED", "snapshot": str(SNAPSHOT.relative_to(ROOT)), "plan": str(D010_PLAN.relative_to(ROOT)), "nonzero_ratio": plan["input"]["commission_ratio"]}, ensure_ascii=False))
        return
    execution = apply_d010(plan)
    D010_EXECUTION.write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rollback = {"task": "T14", "rollback_scope": "仅删除 T14 创建的 SIMULATED Project、两批次、Actual 和 Performance_Result；不修改既有业务记录或公式", "execution": D010_EXECUTION.name, "project_record_id": execution["created"]["project_record_id"], "actual_record_ids": [execution["created"]["actual_record_id"]], "performance_result_record_ids": [execution["created"]["performance_result_record_id"]], "import_batch_record_ids": [execution["batches"]["actual"]["record_id"], execution["batches"]["calc"]["record_id"]], "rollback_order": ["Performance_Result", "Actual", "Import_Batch", "Project"]}
    D010_ROLLBACK.write_text(json.dumps(rollback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "APPLY_PASSED", "snapshot": str(SNAPSHOT.relative_to(ROOT)), "execution": str(D010_EXECUTION.relative_to(ROOT)), "rollback": str(D010_ROLLBACK.relative_to(ROOT)), "assertions": execution["assertions"]}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        ERROR_OUT.write_text(json.dumps({"task": "T14", "status": "FAILED", "timestamp": datetime.now().astimezone().isoformat(), "error": str(exc)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED", "error": str(exc), "error_log": str(ERROR_OUT.relative_to(ROOT))}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
