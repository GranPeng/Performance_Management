#!/usr/bin/env python3
"""T9a simulated Actual generator. Default mode is preflight only; --apply writes after validation."""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {
    "Employee": "tblc59aB4EnSxkQv", "Metric": "tbldKtdIVv8nnTyX",
    "Target": "tblydZkf17kmzrO0", "Actual": "tbli9VhcUFjVDeNd",
    "Import_Batch": "tblHV3JoVR9AEETw", "Error_Log": "tbl4ZpuuOxZacWgj",
}
PERIOD = "2026-07"
SOURCE = "SIMULATED_T9A"
OUT = Path("data/output/T9a模拟Actual清单.json")
ERROR_OUT = Path("data/output/T9a模拟Actual错误日志.json")
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")


def cli(args: list[str]) -> dict:
    if not Path(CLI_BIN).is_file():
        raise RuntimeError(f"lark-cli is unavailable: {CLI_BIN}")
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON output: {p.stdout[-500:]}\nstderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result["data"]


def records(table: str, fields: list[str]) -> list[dict]:
    out = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLES[table], "--limit", "200", "--format", "json"]
        for f in fields:
            args += ["--field-id", f]
        args += ["--offset", str(offset)]
        data = cli(args)
        names = data["fields"]
        ids = data["record_id_list"]
        for rid, values in zip(ids, data["data"]):
            row = dict(zip(names, values)); row["_record_id"] = rid; out.append(row)
        if not data.get("has_more"):
            return out
        offset += len(ids)


def link_id(value):
    return value[0]["id"] if value else None


def add_error(errors, code, detail):
    errors.append({"error_type": code, "detail": detail, "source": SOURCE, "period": PERIOD})


def next_numeric_id(rows: list[dict], field: str, prefix: str) -> int:
    """Return the next canonical six-digit ID sequence; reject malformed IDs rather than overwrite."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{6}})$")
    values = []
    malformed = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        match = pattern.fullmatch(str(value))
        if match:
            values.append(int(match.group(1)))
        else:
            malformed.append(value)
    if malformed:
        raise RuntimeError(f"{field} contains malformed values; refusing ID allocation: {malformed[:10]}")
    return max(values, default=0) + 1


def score_achievement(metric_id: str, rate: float) -> float:
    # V04 rules expressed per registered Metric_ID. This is expected-result evidence, not a rule change.
    if metric_id.endswith("-002") and "IE-OPS" in metric_id:  # OPS ROI 90/85/80 boundaries, cap 110
        return min(rate * 100, 110) if rate >= .90 else (85 if rate >= .85 else (80 if rate >= .80 else 0))
    if metric_id.endswith("-002") and ("IE-SUP" in metric_id or "IE-ADS" in metric_id):
        return min(rate * 100, 150) if rate >= .90 else (60 if rate >= .80 else 0)
    if metric_id == "MET-V04-PROD-DIR-002":
        return min(rate * 100, 120) if rate >= 1 else (80 if rate >= 120/140 else 0)
    if metric_id == "MET-V04-PROD-EDIT-002":
        return min(rate * 100, 120) if rate >= 1 else (80 if rate > .80 else 0)
    if metric_id == "MET-V04-PROD-CAM-002":
        return 100 if rate >= 1 else 0
    if metric_id in {"MET-V04-PROD-DIR-003", "MET-V04-PROD-EDIT-003"}:
        cap = 150
        return min(rate * 100, cap) if rate >= 1 else (90 if rate > .80 else 0)
    # GSV / host ROI / director and editor/camera revenue: V04 common 100/80/60/0, cap 150.
    return min(rate * 100, 150) if rate >= 1 else (90 if rate >= .80 else (60 if rate >= .60 else 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="create Import_Batch and Actual records after successful preflight")
    ap.add_argument("--refresh-manifest", action="store_true", help="只按当前 V04 规则重建本地预期清单；不创建或更新任何 Base 记录")
    args = ap.parse_args()
    if args.apply and args.refresh_manifest:
        ap.error("--apply 与 --refresh-manifest 不能同时使用")
    errors = []
    employees = records("Employee", ["Employee_ID", "Position_ID", "Perf_Participate_Status", "Status"])
    metrics = records("Metric", ["Metric_ID", "Position_ID", "Metric_Name", "Scoring_Type", "Unit", "Status"])
    targets = records("Target", ["Target_ID", "V60_Source_Row", "Period", "Channel_ID", "Target_Value", "Unit", "Status"])
    existing_actuals = records("Actual", ["Actual_ID", "Period", "Employee_ID", "Metric_ID", "Source", "Status"])

    participants = [r for r in employees if r.get("Perf_Participate_Status") == "确认参与" and r.get("Status") == "Active"]
    if len(participants) != 32:
        add_error(errors, "PARTICIPANT_COUNT_MISMATCH", {"expected": 32, "actual": len(participants)})
    if not args.refresh_manifest and any(r.get("Source") == SOURCE and r.get("Period") == PERIOD and r.get("Status") == "Active" for r in existing_actuals):
        add_error(errors, "DUPLICATE_SIMULATION_BATCH", "Active T9a simulated Actual already exists for 2026-07; refusing non-idempotent duplicate write")
    try:
        actual_sequence = next_numeric_id(existing_actuals, "Actual_ID", "ACT")
    except RuntimeError as exc:
        add_error(errors, "ACTUAL_ID_ALLOCATION_FAILED", str(exc))
        actual_sequence = None
    # Refresh mode is evidence-only: preserve online Actual_ID by business key rather
    # than synthesizing new IDs in the local manifest.
    existing_actual_by_business_key = {
        (link_id(r.get("Employee_ID")), link_id(r.get("Metric_ID")), r.get("Period")): r.get("Actual_ID")
        for r in existing_actuals
        if r.get("Source") == SOURCE and r.get("Status") == "Active" and r.get("Actual_ID")
    }
    by_position = defaultdict(list)
    for m in metrics:
        if m.get("Status") == "Active":
            by_position[link_id(m.get("Position_ID"))].append(m)
    for emp in participants:
        if not by_position[link_id(emp.get("Position_ID"))]:
            add_error(errors, "NO_ACTIVE_POSITION_METRIC", emp["Employee_ID"])

    # Target lookup: use July first active channel's V60 rows 3 (revenue) and 11 (spend);
    # ROI is derived from the same channel's revenue/spend, per D-005.
    july = [t for t in targets if t.get("Period") == PERIOD and t.get("Status") == "Active"]
    by_channel_row = {(link_id(t.get("Channel_ID")), t.get("V60_Source_Row")): t for t in july}
    revenue_targets = [t for t in july if t.get("V60_Source_Row") == 3]
    spend_targets = [t for t in july if t.get("V60_Source_Row") == 11]
    if not revenue_targets or not spend_targets:
        add_error(errors, "TARGET_REFERENCE_MISSING", {"period": PERIOD, "revenue_row3": len(revenue_targets), "spend_row11": len(spend_targets)})
    ref_channel = link_id(revenue_targets[0].get("Channel_ID")) if revenue_targets else None
    revenue_target = revenue_targets[0] if revenue_targets else None
    spend_target = by_channel_row.get((ref_channel, 11)) if ref_channel else None
    if ref_channel and not spend_target:
        add_error(errors, "TARGET_CHANNEL_PAIR_MISSING", {"channel_record_id": ref_channel, "required_row": 11})

    batch_id = "IB-T9A-SIM-20260817-01"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # 1.60 is deliberately above every V04 automatic-score cap used here (110/120/150), so this is a true cap test.
    rate_cycle = [(1.60, "达成率>1.0，封顶触发样本"), (.90, "达成率0.8-1.0样本"), (.70, "达成率0.6-0.8样本"), (.50, "达成率<0.6样本")]
    count_cycle = [(0, "0次样本", 100), (2, "阈值内样本", 80), (3, "超阈值样本", 0)]
    deduction_cycle = [(0, "无违规样本", 100), (1, "部分扣分样本", 95), (20, "扣到保底样本", 0)]
    manual_cycle = ["差", "合格", "优秀"]
    reward_cycle = ["奖励触发", "处罚触发", "均不触发"]
    actual_rows, manifest = [], []
    seq = actual_sequence
    kind_index = Counter()
    for emp in participants:
        emp_rid, position_rid = emp["_record_id"], link_id(emp.get("Position_ID"))
        for metric in by_position[position_rid]:
            typ, mid, unit = metric.get("Scoring_Type"), metric["Metric_ID"], metric.get("Unit") or "/"
            existing_actual_id = existing_actual_by_business_key.get((emp_rid, metric["_record_id"], PERIOD)) if args.refresh_manifest else None
            actual_id = existing_actual_id or f"ACT{seq:06d}"
            common = {"employee_id": emp["Employee_ID"], "employee_record_id": emp_rid, "metric_id": mid,
                      "metric_record_id": metric["_record_id"], "period": PERIOD, "scoring_type": typ,
                      "metric_name": metric["Metric_Name"], "source": SOURCE}
            if typ == "达成率/进度型":
                rate, intent = rate_cycle[kind_index[typ] % len(rate_cycle)]; kind_index[typ] += 1
                # Select a target source grounded in the Metric ID/known V04 reference.
                if mid.endswith("-002") and ("IE-OPS" in mid or "IE-SUP" in mid or "IE-ADS" in mid or "IE-HOST" in mid):
                    target_value = (revenue_target["Target_Value"] / spend_target["Target_Value"]) if revenue_target and spend_target and spend_target["Target_Value"] else 1
                    actual_value, target_ref = target_value * rate, "V60行3主营业务收入÷行11广告投流费（D-005派生）"
                elif mid in {"MET-V04-PROD-DIR-002", "MET-V04-PROD-EDIT-002", "MET-V04-PROD-CAM-002"}:
                    target_value = 140 if mid.endswith("DIR-002") else (150 if mid.endswith("EDIT-002") else 100)
                    actual_value, target_ref = target_value * rate, "V04评分标准明确基准值；非V60预算字段，模拟参照"
                elif mid in {"MET-V04-PROD-DIR-003", "MET-V04-PROD-EDIT-003"}:
                    target_value = spend_target["Target_Value"] if spend_target else 100
                    actual_value, target_ref = target_value * rate, "V60行11广告投流费=消耗（D-006）"
                else:
                    target_value = revenue_target["Target_Value"] if revenue_target else 100
                    actual_value, target_ref = target_value * rate, "V60行3主营业务收入=退货后GSV（D-005）"
                expected = score_achievement(mid, rate)
                design = intent
                row = {"Actual_ID": actual_id, "Metric_ID": [{"id": metric["_record_id"]}], "Period": PERIOD,
                       "Employee_ID": [{"id": emp_rid}], "Actual_Value": round(actual_value, 4), "Unit": unit,
                       "Source_Type": "MANUAL_ENTRY", "Source_Ref": f"{SOURCE}; {target_ref}; target={target_value}; rate={rate}",
                       "Collected_By": [{"id": emp_rid}], "Collected_Time": now, "Validation_Status": "通过",
                       "Import_Batch_ID": None, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"}
                expected_kind = "achievement_rate"
            elif typ == "次数阈值型":
                value, design, expected = count_cycle[kind_index[typ] % len(count_cycle)]; kind_index[typ] += 1
                # V04 直播中控「客户服务与答疑」明确规定：0次=100、少于3次=60、≥3次=0。
                # 不能复用 LIVE-002 的通用中档80分预期。
                if mid == "MET-V04-IE-LIVE-003" and 0 < value < 3:
                    expected = 60
                row = {"Actual_ID": actual_id, "Metric_ID": [{"id": metric["_record_id"]}], "Period": PERIOD,
                       "Employee_ID": [{"id": emp_rid}], "Actual_Value": value, "Unit": "次", "Source_Type": "MANUAL_ENTRY",
                       "Source_Ref": f"{SOURCE}; V04次数阈值场景", "Collected_By": [{"id": emp_rid}], "Collected_Time": now,
                       "Validation_Status": "通过", "Import_Batch_ID": None, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"}
                rate, target_value, target_ref, expected_kind = None, None, None, "threshold_count"
            elif typ == "扣分制":
                value, design, expected = deduction_cycle[kind_index[typ] % len(deduction_cycle)]; kind_index[typ] += 1
                row = {"Actual_ID": actual_id, "Metric_ID": [{"id": metric["_record_id"]}], "Period": PERIOD,
                       "Employee_ID": [{"id": emp_rid}], "Actual_Value": value, "Unit": "次", "Source_Type": "MANUAL_ENTRY",
                       "Source_Ref": f"{SOURCE}; V04单次扣5分；测试基准100分、下限0分", "Collected_By": [{"id": emp_rid}], "Collected_Time": now,
                       "Validation_Status": "通过", "Import_Batch_ID": None, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Active"}
                rate, target_value, target_ref, expected_kind = None, None, None, "deduction"
            elif typ == "定性等级型":
                design = manual_cycle[kind_index[typ] % 3]; kind_index[typ] += 1
                manifest.append({**common, "requires_actual": False, "design_intent": design, "expected_result": "【无需Actual】负责人Manual_Score输入；本卡不造实际值", "expected_result_type": "manual_qualitative"})
                continue
            elif typ == "奖惩制":
                design = reward_cycle[kind_index[typ] % 3]; kind_index[typ] += 1
                manifest.append({**common, "requires_actual": False, "design_intent": design, "expected_result": "【无需Actual】D-009.3：客服奖惩由负责人Manual_Score录入，不进入自动公式", "expected_result_type": "manual_reward_penalty"})
                continue
            else:
                add_error(errors, "UNKNOWN_SCORING_TYPE", {"metric": mid, "type": typ}); continue
            manifest.append({**common, "actual_id": row["Actual_ID"], "requires_actual": True, "actual_value": row["Actual_Value"], "unit": row["Unit"],
                             "design_intent": design, "expected_result": expected, "expected_result_type": expected_kind,
                             "expected_achievement_rate": rate, "target_reference": target_ref, "target_value_used": target_value})
            actual_rows.append(row); seq += 1

    coverage = defaultdict(set)
    for entry in manifest:
        coverage[entry["scoring_type"]].add(entry["design_intent"])
    required = {"达成率/进度型": {x[1] for x in rate_cycle}, "次数阈值型": {x[1] for x in count_cycle},
                "扣分制": {x[1] for x in deduction_cycle}, "定性等级型": set(manual_cycle), "奖惩制": set(reward_cycle)}
    missing = {k: sorted(v - coverage[k]) for k, v in required.items() if v - coverage[k]}
    if missing: add_error(errors, "SCENARIO_COVERAGE_GAP", missing)
    payload = {"task": "T9a", "generated_at": now, "mode": "APPLY" if args.apply else ("REFRESH_MANIFEST" if args.refresh_manifest else "PREFLIGHT"), "base_token": BASE,
               "period": PERIOD, "source": SOURCE, "batch_id": batch_id, "participant_count": len(participants),
               "actual_count": len(actual_rows), "manifest_count": len(manifest), "coverage": {k: sorted(v) for k, v in coverage.items()},
               "errors": errors, "records": manifest}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ERROR_OUT.write_text(json.dumps({"task": "T9a", "errors": errors, "generated_at": now}, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        print(json.dumps({"status": "PREFLIGHT_FAILED", "errors": errors, "manifest": str(OUT)}, ensure_ascii=False, indent=2)); sys.exit(2)
    if not args.apply:
        print(json.dumps({"status": "PREFLIGHT_PASSED", "participant_count": len(participants), "actual_count": len(actual_rows), "manifest": str(OUT)}, ensure_ascii=False, indent=2)); return

    # Write batch first, then Actual chunks. Never silently transform or overwrite source rows.
    batch_record = {"Batch_ID": batch_id, "Batch_Type": "ACTUAL", "Source_Type": "SIMULATED", "Source_File": OUT.name,
                    "Import_Time": now, "Operator": "data-engineer/T9a", "Total_Count": len(actual_rows), "Success_Count": 0,
                    "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"}
    batch_data = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Import_Batch"], "--json", json.dumps({"create_records": [batch_record]}, ensure_ascii=False)])
    batch_rid = batch_data.get("record_id_list", [None])[0]
    if not batch_rid: raise RuntimeError(f"Import_Batch create did not return record id: {batch_data}")
    for row in actual_rows: row["Import_Batch_ID"] = [{"id": batch_rid}]
    created = []
    try:
        for i in range(0, len(actual_rows), 200):
            d = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Actual"], "--json", json.dumps({"create_records": actual_rows[i:i+200]}, ensure_ascii=False)])
            created += d.get("record_id_list", [])
        if len(created) != len(actual_rows): raise RuntimeError(f"Actual create acknowledgement mismatch: expected {len(actual_rows)}, got {len(created)}")
        update = {"update_records": {batch_rid: {"Success_Count": len(created), "Fail_Count": 0, "Status": "Success", "Update_Time": now}}}
        cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLES["Import_Batch"], "--json", json.dumps(update, ensure_ascii=False)])
    except Exception as exc:
        # A durable local error artifact is written even if online Error_Log write cannot safely be completed.
        ERROR_OUT.write_text(json.dumps({"task": "T9a", "batch_record_id": batch_rid, "error": str(exc), "created_actual_record_ids": created}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    payload["apply_result"] = {"import_batch_record_id": batch_rid, "actual_record_ids": created}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "APPLY_PASSED", "batch_record_id": batch_rid, "actual_count": len(created), "manifest": str(OUT)}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
