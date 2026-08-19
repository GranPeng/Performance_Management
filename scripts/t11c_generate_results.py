#!/usr/bin/env python3
"""T11c: idempotent Performance_Result generation (upsert by business key Employee_ID+Metric_ID+Period).

Changes vs T9b (t9b_generate_results.py):
- Business-key upsert: existing rows (Employee_ID+Metric_ID+Period) are UPDATEd, missing rows CREATEd.
  Running twice keeps row count and Monthly_Total unchanged (Q-10-03).
- Commission snapshot columns written by script per D-009 (Q-10-02):
  Commission_Base_Type / Commission_Base / Commission_Ratio are storage snapshots (随批次固定);
  Commission_Amount is a Base formula field (Base×Ratio) set by t11c_set_formula_fields.py.
- Project_ID / Project_Run_Days / Is_Exempt stay formula-driven; no fabrication of Start_Date.

Two-phase flow:
  Phase 1: create missing rows + update existing rows (business-key upsert).
  Phase 2: read back Monthly_Total (Base formula result), compute Commission snapshots, write back.
"""
from __future__ import annotations
import json, re, shutil, subprocess, sys, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {
    "Performance_Result": "tbl6tFtVKExFUTWo",
    "Import_Batch": "tblHV3JoVR9AEETw",
    "Actual": "tbli9VhcUFjVDeNd",
    "Metric": "tbldKtdIVv8nnTyX",
    "Commission_Tier": "tblkZUoHYwBIvDYe",
    "Position": "tbldzvsg9Op6pK29",
}
PERIOD = "2026-07"
SOURCE = "SIMULATED_T11C"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
MANIFEST = Path("data/output/T9a模拟Actual清单.json")
BATCH_ID = "IB-T11C-CALC-20260817-01"

# V04 scoring parameters per Metric_ID (same as T9b; used for snapshot columns on create)
ACH_PARAMS = {
    "MET-V04-IE-OPS-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-SUP-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-ADS-001":   {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-LIVE-001":  {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-HOST-001":  {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-DIR-001": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-001":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-PROD-CAM-001": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0.6, "Score_T3": 60, "Score_Floor": 0},
    "MET-V04-IE-OPS-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 110, "Rate_T2": 0.85, "Score_T2": 85, "Rate_T3": 0.8, "Score_T3": 80, "Score_Floor": 0},
    "MET-V04-IE-SUP-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 60, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-IE-ADS-002":   {"Rate_T1": 0.9, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 60, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-DIR-002": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 120, "Rate_T2": 120/140, "Score_T2": 80, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-002":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 120, "Rate_T2": 0.8, "Score_T2": 80, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-CAM-002": {"Rate_T1": 1.0, "Score_T1": 100, "Score_Cap": 100, "Rate_T2": 0, "Score_T2": 0, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-DIR-003": {"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-003":{"Rate_T1": 1.0, "Score_T1": 0, "Score_Cap": 150, "Rate_T2": 0.8, "Score_T2": 90, "Rate_T3": 0, "Score_T3": 0, "Score_Floor": 0},
}
THRESHOLD_PARAMS = {
    "MET-V04-IE-LIVE-002": {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 80, "Score_Floor": 0},
    "MET-V04-IE-LIVE-003": {"Rate_T1": 0, "Score_T1": 100, "Rate_T2": 3, "Score_T2": 60, "Score_Floor": 0},
}
DEDUCTION_PARAMS = {
    "MET-V04-PROD-CAM-003": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-CAM-004": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-CAM-005": {"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-004":{"Deduct_Per": 5, "Score_Floor": 0},
    "MET-V04-PROD-EDIT-005":{"Deduct_Per": 5, "Score_Floor": 0},
}
TARGET_ROW3 = {"record_id": "recvsgqeVgqMU2", "value": 187.836055845743}
TARGET_ROW11 = {"record_id": "recvsgqhEO9IU9", "value": 68.304020307543}

# D-009 / business_rules.md §1: Position_ID -> Commission_Base_Type + which Metrics carry the base amount
POSITION_BASE_MAP = {
    "POS000013": {"type": "GSV", "metrics": ["MET-V04-IE-OPS-001"]},
    "POS000017": {"type": "GSV", "metrics": ["MET-V04-IE-SUP-001"]},
    "POS000006": {"type": "个人营收", "metrics": ["MET-V04-IE-HOST-001"]},
    "POS000018": {"type": "个人消耗", "metrics": ["MET-V04-PROD-DIR-003"]},
    "POS000044": {"type": "个人消耗", "metrics": ["MET-V04-PROD-EDIT-003"]},
    "POS000035": {"type": "个人消耗", "metrics": []},
    "POS000032": {"type": "投放消耗", "metrics": []},
    "POS000041": {"type": "不适用", "metrics": []},
    "POS000038": {"type": "不适用", "metrics": []},
}


def cli(args, retries=5):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last


def records(table: str, fields: list[str]) -> list[dict]:
    out = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLES[table], "--limit", "200", "--format", "json"]
        for f in fields:
            args += ["--field-id", f]
        if offset:
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
    values = [int(m.group(1)) for row in rows if (m := pattern.fullmatch(str(row.get(field) or "")))]
    return max(values, default=0) + 1


def target_ref_for(metric_id: str, target_value_used):
    if metric_id in ACH_PARAMS:
        if metric_id in {"MET-V04-PROD-DIR-002", "MET-V04-PROD-EDIT-002", "MET-V04-PROD-CAM-002"}:
            return None, target_value_used
        if metric_id in {"MET-V04-PROD-DIR-003", "MET-V04-PROD-EDIT-003"}:
            return TARGET_ROW11["record_id"], target_value_used
        if metric_id.endswith("-002") and ("IE-OPS" in metric_id or "IE-SUP" in metric_id or "IE-ADS" in metric_id or "IE-HOST" in metric_id):
            return None, target_value_used
        return TARGET_ROW3["record_id"], target_value_used
    return None, None


def params_for(metric_id, typ):
    if typ == "达成率/进度型":
        return ACH_PARAMS.get(metric_id) or {}
    if typ == "次数阈值型":
        return THRESHOLD_PARAMS.get(metric_id) or {}
    if typ == "扣分制":
        return DEDUCTION_PARAMS.get(metric_id) or {}
    return {}


def build_row(r, actual_by_id, batch_rid):
    """Build one payload row for create/update (no Result_ID)."""
    typ = r["scoring_type"]
    params = params_for(r["metric_id"], typ)
    target_rid, target_snap = (None, None)
    actual_rid = None
    if r["requires_actual"]:
        target_rid, target_snap = target_ref_for(r["metric_id"], r.get("target_value_used"))
        actual_rid = actual_by_id.get(r.get("actual_id"))
        if actual_rid is None:
            raise RuntimeError(f"missing Actual record for {r.get('actual_id')}")
    row = {
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
    }
    row.update({k: v for k, v in params.items()})
    return row


def resolve_position_metric_map(metric_records):
    """Map metric record_id -> Position_ID text (from Metric->Position link)."""
    pos_records = records("Position", ["Position_ID"])
    pos_by_rid = {r["_record_id"]: r.get("Position_ID") for r in pos_records}
    out = {}
    for m in metric_records:
        pos_rid = link_id(m.get("Position_ID"))
        out[m["_record_id"]] = pos_by_rid.get(pos_rid)
    return out


def compute_commission_snapshots(result_rows, metric_pos_map, metric_rid_by_id, metric_records, actual_rows, tier_rows):
    """Compute Commission_Base_Type / Commission_Base / Commission_Ratio per result row.

    Base (D-009): position type via Metric->Position; value = Actual_Value of the position's
    base metric for same Employee+Period (snapshot, not formula — Base formula can't chain link fields
    inside FILTER conditions; verified in T11c scratch).
    Ratio: tier match on Monthly_Total (Base formula result read back). 运营族=Commission_Tier.Base_Rate×Coefficient,
    others=Ratio_Value (Commission_Tier), LIVE/CS empty.
    Returns {record_id: {Commission_Base_Type, Commission_Base, Commission_Ratio}}.
    """
    # metric record_id -> position record_id (link value in Metric table)
    metric_pos_rid = {}
    for m in metric_records:
        pr = link_id(m.get("Position_ID"))
        if pr:
            metric_pos_rid[m["_record_id"]] = pr

    actual_by_emp_met = defaultdict(list)
    for a in actual_rows:
        emp = link_id(a.get("Employee_ID"))
        met = link_id(a.get("Metric_ID"))
        actual_by_emp_met[(emp, met)].append(a)

    # tier rows indexed by position rid
    tier_by_pos = defaultdict(list)
    for t in tier_rows:
        pos_rid = link_id(t.get("Position_ID"))
        if pos_rid and t.get("Status") == "Active":
            tier_by_pos[pos_rid].append(t)

    snap = {}
    for row in result_rows:
        emp = link_id(row.get("Employee_ID"))
        met = link_id(row.get("Metric_ID"))
        if not emp or not met:
            continue
        pos_id = metric_pos_map.get(met)
        base_cfg = POSITION_BASE_MAP.get(pos_id)
        base_type = base_cfg["type"] if base_cfg else None
        base_val = None
        if base_cfg and base_cfg["metrics"]:
            for base_met in base_cfg["metrics"]:
                base_rid = metric_rid_by_id.get(base_met)
                if base_rid:
                    cands = actual_by_emp_met.get((emp, base_rid), [])
                    if cands:
                        base_val = cands[0].get("Actual_Value")
                        break
        # ratio: tier match by position rid of the row's metric
        ratio = None
        pos_rid = metric_pos_rid.get(met)
        mt = row.get("Monthly_Total")
        if pos_rid and mt not in (None, ""):
            mt_f = float(mt)
            tiers = tier_by_pos.get(pos_rid, [])
            matched = None
            for t in tiers:
                lower = t.get("Score_Lower")
                if lower is not None and float(lower) <= mt_f:
                    if matched is None or float(t["Score_Lower"]) > float(matched["Score_Lower"]):
                        matched = t
            if matched is not None:
                coef = matched.get("Coefficient")
                rv = matched.get("Ratio_Value")
                if coef is not None:
                    base_rate = matched.get("Base_Rate")
                    if base_rate is None:
                        raise RuntimeError(
                            f"运营族梯度缺少 Base_Rate 配置: {matched.get('Commission_Tier_ID')}"
                        )
                    ratio = round(float(base_rate) * float(coef), 6)
                elif rv is not None:
                    ratio = float(rv)
        snap[row["_record_id"]] = {"Commission_Base_Type": base_type, "Commission_Base": base_val, "Commission_Ratio": ratio}
    return snap


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recs = manifest["records"]

    existing_pr = records("Performance_Result", ["Result_ID", "Period", "Employee_ID", "Metric_ID"])
    existing_actuals = records("Actual", ["Actual_ID", "Period", "Source", "Status"])
    actual_by_id = {r["Actual_ID"]: r["_record_id"] for r in existing_actuals if r.get("Actual_ID")}
    metric_records = records("Metric", ["Metric_ID", "Position_ID"])
    metric_rid_by_id = {r.get("Metric_ID"): r["_record_id"] for r in metric_records if r.get("Metric_ID")}
    metric_pos_map = resolve_position_metric_map(metric_records)

    # business key -> existing record_id
    key_to_rid = {}
    for r in existing_pr:
        emp = link_id(r.get("Employee_ID"))
        met = link_id(r.get("Metric_ID"))
        if emp and met:
            key_to_rid[(emp, met, r.get("Period"))] = r["_record_id"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Import_Batch: upsert by Batch_ID (idempotent)
    batches = records("Import_Batch", ["Batch_ID", "Batch_Type", "Source", "Status"])
    batch_rid = None
    for b in batches:
        if b.get("Batch_ID") == BATCH_ID:
            batch_rid = b["_record_id"]
            break
    if batch_rid is None:
        d = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Import_Batch"],
                 "--json", json.dumps({"create_records": [{
                     "Batch_ID": BATCH_ID, "Batch_Type": "CALC", "Source_Type": "SIMULATED",
                     "Source_File": MANIFEST.name, "Import_Time": now, "Operator": "feishu-builder/T11c",
                     "Total_Count": len(recs), "Success_Count": 0, "Fail_Count": 0,
                     "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Running"}]}, ensure_ascii=False)])
        batch_rid = d.get("record_id_list", [None])[0]
        if not batch_rid:
            raise RuntimeError(f"Import_Batch create failed: {d}")

    rows_to_create = []
    updates = {}
    seq = next_numeric_id(existing_pr, "Result_ID", "RST")
    for r in recs:
        key = (r["employee_record_id"], r["metric_record_id"], PERIOD)
        payload = build_row(r, actual_by_id, batch_rid)
        if key in key_to_rid:
            updates[key_to_rid[key]] = payload
        else:
            payload["Result_ID"] = f"RST{seq:06d}"
            seq += 1
            rows_to_create.append(payload)

    # Phase 1: upsert
    created_ids = []
    for i in range(0, len(rows_to_create), 200):
        d = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
                 "--json", json.dumps({"create_records": rows_to_create[i:i+200]}, ensure_ascii=False)])
        created_ids += d.get("record_id_list", [])
    # batch update existing rows (200/批)
    upd_items = list(updates.items())
    for i in range(0, len(upd_items), 200):
        chunk = dict(upd_items[i:i+200])
        cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
             "--json", json.dumps({"update_records": chunk}, ensure_ascii=False)])

    total = len(created_ids) + len(updates)
    cli(["+record-upsert", "--base-token", BASE, "--table-id", TABLES["Import_Batch"],
         "--record-id", batch_rid,
         "--json", json.dumps({"Success_Count": total, "Fail_Count": 0, "Status": "Success", "Update_Time": now}, ensure_ascii=False)])

    # Phase 2: read back Monthly_Total + commission snapshots, then write back (batch update)
    time.sleep(3)  # let formula engine settle after writes
    pr_fields = ["Result_ID", "Period", "Employee_ID", "Metric_ID", "Monthly_Total"]
    pr_rows = records("Performance_Result", pr_fields)
    actual_rows = records("Actual", ["Actual_ID", "Employee_ID", "Metric_ID", "Actual_Value", "Period", "Status"])
    tier_rows = records("Commission_Tier", ["Commission_Tier_ID", "Position_ID", "Tier_Level", "Score_Lower", "Coefficient", "Ratio_Value", "Base_Rate", "Status"])
    snap = compute_commission_snapshots(pr_rows, metric_pos_map, metric_rid_by_id, metric_records, actual_rows, tier_rows)
    written = 0
    snap_payloads = {}
    for rid, vals in snap.items():
        if vals.get("Commission_Base_Type") is None and vals.get("Commission_Base") is None and vals.get("Commission_Ratio") is None:
            continue
        payload = {k: v for k, v in vals.items() if v is not None}
        snap_payloads[rid] = payload
        written += 1
    items = list(snap_payloads.items())
    for i in range(0, len(items), 200):
        chunk = dict(items[i:i+200])
        cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
             "--json", json.dumps({"update_records": chunk}, ensure_ascii=False)])

    print(json.dumps({"status": "APPLY_PASSED", "batch_record_id": batch_rid,
                      "created": len(created_ids), "updated": len(updates), "total": total,
                      "commission_snapshot_written": written,
                      "created_ids_sample": created_ids[:3]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
