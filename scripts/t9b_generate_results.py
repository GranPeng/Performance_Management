#!/usr/bin/env python3
"""T9b: create Performance_Result rows from T9a simulated Actual manifest.
- Creates a CALC Import_Batch.
- For each T9a manifest record: create Performance_Result row with scoring-parameter snapshot columns.
- Auto_Score / Final_Score / Achievement_Rate / Weight are computed by Base formulas (not written).
"""
from __future__ import annotations
import json, re, shutil, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {
    "Performance_Result": "tbl6tFtVKExFUTWo",
    "Import_Batch": "tblHV3JoVR9AEETw",
    "Actual": "tbli9VhcUFjVDeNd",
}
PERIOD = "2026-07"
SOURCE = "SIMULATED_T9B"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
MANIFEST = Path("data/output/T9a模拟Actual清单.json")

# V04 scoring parameters per Metric_ID (transcribed from V04 Scoring_Standard_Text; mirrors T9a score_achievement evidence)
# Score_T1 == 0 means "按实际达成率×100 封顶计入" (PROPORTIONAL); non-zero means fixed score.
ACH_PARAMS = {
    # GSV / revenue common: rate>=1 -> min(rate*100,150); >=0.8 -> 90; >=0.6 -> 60; else 0
    "MET-V04-IE-OPS-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-SUP-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-ADS-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-LIVE-001":  {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-HOST-001":  {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-DIR-001": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-001":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-CAM-001": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    # OPS-002 ROI: rate>=0.9 -> min(rate*100,110); >=0.85 -> 85; >=0.8 -> 80; else 0
    "MET-V04-IE-OPS-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 110, "Rate_T2": 0.85, "Score_T2": 85, "Rate_T3": 0.8, "Score_T3": 80, "Score_Floor": 0},
    # SUP/ADS-002 ROI: rate>=0.9 -> min(rate*100,150); >=0.8 -> 60; else 0
    "MET-V04-IE-SUP-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 60, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-IE-ADS-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 60, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    # DIR-002 团队产出数量 (基准 140): rate>=1 -> min(rate*100,120); >=120/140 -> 80; else 0
    "MET-V04-PROD-DIR-002": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 120, "Rate_T2": 120/140, "Score_T2": 80, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    # EDIT-002 个人成片数量 (基准 150): rate>=1 -> min(rate*100,120); >0.8 -> 80; else 0
    "MET-V04-PROD-EDIT-002":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 120, "Rate_T2": 0.8, "Score_T2": 80, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    # CAM-002 个人素材数量 (基准 100): rate>=1 -> 100; else 0 (FIXED 100)
    "MET-V04-PROD-CAM-002": {"Rate_T1": 1.0, "Score_T1": 100, "Score_Cap": 100, "Rate_T2": 0, "Score_T2": 0, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    # DIR/EDIT-003 消耗金额: rate>=1 -> min(rate*100,150); >0.8 -> 90; else 0
    "MET-V04-PROD-DIR-003": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-003":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
}

# 次数阈值型: count<=Rate_T1 -> Score_T1; count<Rate_T2 -> Score_T2; else Score_Floor
THRESHOLD_PARAMS = {
    "MET-V04-IE-LIVE-002": {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 80, "Score_Floor": 0},
    "MET-V04-IE-LIVE-003": {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 60, "Score_Floor": 0},
}

# 扣分制: MAX(100 - count*Deduct_Per, Score_Floor)
DEDUCTION_PARAMS = {
    "MET-V04-PROD-CAM-003": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-CAM-004": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-CAM-005": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-004":{"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-005":{"Deduct_Per": 5, "Score_Floor": 0},
}

# Target records (2026-07, 高个子抖音 channel recvsls7z4BhTA)
TARGET_ROW3 = {"record_id": "recvsgqeVgqMU2", "value": 187.836055845743}
TARGET_ROW11 = {"record_id": "recvsgqhEO9IU9", "value": 68.304020307543}


def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]}\nstderr={p.stderr[-500:]}") from exc
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


def next_numeric_id(rows, field, prefix):
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{6}})$")
    values, malformed = [], []
    for row in rows:
        v = row.get(field)
        if v is None:
            continue
        m = pattern.fullmatch(str(v))
        if m:
            values.append(int(m.group(1)))
        else:
            malformed.append(v)
    if malformed:
        raise RuntimeError(f"{field} malformed: {malformed[:10]}")
    return max(values, default=0) + 1


def target_ref_for(metric_id: str, target_value_used):
    """Return (target_record_id_or_None, target_snapshot_value)."""
    if metric_id in ACH_PARAMS:
        if metric_id in {"MET-V04-PROD-DIR-002", "MET-V04-PROD-EDIT-002", "MET-V04-PROD-CAM-002"}:
            # 基准值在 V04 评分标准内，无 Target 记录 → 快照
            return None, target_value_used
        if metric_id in {"MET-V04-PROD-DIR-003", "MET-V04-PROD-EDIT-003"}:
            return TARGET_ROW11["record_id"], target_value_used
        if metric_id.endswith("-002") and ("IE-OPS" in metric_id or "IE-SUP" in metric_id or "IE-ADS" in metric_id or "IE-HOST" in metric_id):
            # ROI 派生目标（收入÷投流费）→ 无 Target 记录 → 快照
            return None, target_value_used
        # GSV 类 → row3
        return TARGET_ROW3["record_id"], target_value_used
    return None, None


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recs = manifest["records"]
    existing_pr = records("Performance_Result", ["Result_ID"])
    seq = next_numeric_id(existing_pr, "Result_ID", "RST")
    existing_actuals = records("Actual", ["Actual_ID", "Period", "Source", "Status"])
    actual_by_id = {r["Actual_ID"]: r["_record_id"] for r in existing_actuals if r.get("Actual_ID")}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    batch_id = "IB-T9B-CALC-20260817-01"

    # 1. Create CALC Import_Batch
    batch_row = {"Batch_ID": batch_id, "Batch_Type": "CALC", "Source_Type": "SIMULATED", "Source_File": MANIFEST.name,
                 "Import_Time": now, "Operator": "feishu-builder/T9b", "Total_Count": len(recs),
                 "Success_Count": 0, "Fail_Count": 0, "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"}
    batch_data = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Import_Batch"],
                      "--json", json.dumps({"create_records": [batch_row]}, ensure_ascii=False)])
    batch_rid = batch_data.get("record_id_list", [None])[0]
    if not batch_rid:
        raise RuntimeError(f"Import_Batch create failed: {batch_data}")

    # 2. Build Performance_Result rows
    rows = []
    for r in recs:
        typ = r["scoring_type"]
        params = {}
        if typ == "达成率/进度型":
            params = ACH_PARAMS.get(r["metric_id"])
            if params is None:
                raise RuntimeError(f"missing ACH params for {r['metric_id']}")
        elif typ == "次数阈值型":
            params = THRESHOLD_PARAMS.get(r["metric_id"])
            if params is None:
                raise RuntimeError(f"missing THRESHOLD params for {r['metric_id']}")
        elif typ == "扣分制":
            params = DEDUCTION_PARAMS.get(r["metric_id"])
            if params is None:
                raise RuntimeError(f"missing DEDUCTION params for {r['metric_id']}")
        # 定性等级型 / 奖惩制 → 无自动评分参数（Auto_Score 留空，Manual_Score 人工录入）

        target_rid, target_snap = (None, None)
        if r["requires_actual"]:
            target_rid, target_snap = target_ref_for(r["metric_id"], r.get("target_value_used"))
            actual_rid = actual_by_id.get(r.get("actual_id"))
            if actual_rid is None:
                raise RuntimeError(f"missing Actual record for {r.get('actual_id')}")
        else:
            actual_rid = None

        row = {
            "Result_ID": f"RST{seq:06d}",
            "Period": PERIOD,
            "Employee_ID": [{"id": r["employee_record_id"]}],
            "Metric_ID": [{"id": r["metric_record_id"]}],
            "Actual_ID": [{"id": actual_rid}] if actual_rid else None,
            "Target_ID": [{"id": target_rid}] if target_rid else None,
            "Target_Value_Snapshot": target_snap,
            "Rule_Version": "V04",
            "Calc_Batch_ID": [{"id": batch_rid}],
            "Review_Status": "待复核",
            "Status": "Active",
            "Source": SOURCE,
            "Create_Time": now,
            "Update_Time": now,
        }
        row.update({k: v for k, v in params.items()})
        rows.append(row)
        seq += 1

    # 3. Batch create (200/chunk)
    created = []
    for i in range(0, len(rows), 200):
        d = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
                 "--json", json.dumps({"create_records": rows[i:i+200]}, ensure_ascii=False)])
        created += d.get("record_id_list", [])
    if len(created) != len(rows):
        raise RuntimeError(f"ack mismatch: expected {len(rows)}, got {len(created)}")
    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLES["Import_Batch"],
         "--json", json.dumps({"update_records": {batch_rid: {"Success_Count": len(rows), "Fail_Count": 0, "Status": "Success", "Update_Time": now}}}, ensure_ascii=False)])

    print(json.dumps({"status": "APPLY_PASSED", "batch_record_id": batch_rid, "result_count": len(rows),
                      "result_ids": [f"RST{r['Result_ID'][3:]}" for r in rows][:5],
                      "last_result_id": rows[-1]["Result_ID"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
