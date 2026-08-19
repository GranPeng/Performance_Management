#!/usr/bin/env python3
"""T11c: end-to-end exemption verification v2 (uses record-list read-back, not record-get).
Temporary SIMULATED project linked to EDIT-003 row (ACT000056), then cleanup.
"""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {"Performance_Result": "tbl6tFtVKExFUTWo", "Project": "tbl1GO2vR9ZAqPbr"}
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=5):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last

def records(table_id, fields, limit=200):
    out = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", table_id, "--limit", str(limit), "--format", "json"]
        for f in fields:
            args += ["--field-id", f]
        if offset:
            args += ["--offset", str(offset)]
        d = cli(args)
        names = d["fields"]; ids = d["record_id_list"]
        for rid, vals in zip(ids, d["data"]):
            row = dict(zip(names, vals)); row["_id"] = rid; out.append(row)
        if not d.get("has_more"):
            return out
        offset += len(ids)

def link_id(v):
    return v[0]["id"] if v else None

def read_row(rid):
    rows = records(TABLES["Performance_Result"],
                   ["Result_ID", "Employee_ID", "Metric_ID", "Actual_ID", "Project_ID", "Project_Run_Days",
                    "Is_Exempt", "Auto_Score", "Final_Score", "Weighted_Score", "Monthly_Total", "Commission_Base", "Commission_Ratio", "Commission_Amount"])
    for r in rows:
        if r["_id"] == rid:
            return r
    return None

def main():
    pr = records(TABLES["Performance_Result"],
                 ["Result_ID", "Employee_ID", "Metric_ID", "Actual_ID", "Project_ID", "Is_Exempt", "Auto_Score", "Final_Score", "Weighted_Score", "Monthly_Total", "Commission_Base", "Commission_Ratio", "Commission_Amount"])
    target = None
    for r in pr:
        if link_id(r.get("Actual_ID")) == "recvswHlTB0MK1":
            target = r
            break
    if target is None:
        print("ERROR: no result row linked to ACT000056")
        return
    emp = link_id(target.get("Employee_ID"))
    print("target:", json.dumps({"Result_ID": target.get("Result_ID"), "emp": emp,
                                 "MT_before": target.get("Monthly_Total"),
                                 "IsExempt_before": target.get("Is_Exempt"),
                                 "Auto_before": target.get("Auto_Score"),
                                 "WS_before": target.get("Weighted_Score")}, ensure_ascii=False))
    mt_before = target.get("Monthly_Total")

    c = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLES["Project"],
             "--json", json.dumps({"create_records": [{
                 "Project_ID": "PROJ900001", "Project_Name": "T11C模拟新项目（验证豁免）",
                 "Start_Date": "2026-05-15", "Brand": "SIMULATED", "Status": "Active",
                 "Source": "SIMULATED_T11C", "Note": "T11c 豁免分支端到端验证临时项目，验证后删除"}]}, ensure_ascii=False)])
    proj_rid = c.get("record_id_list", [None])[0]
    print("temp project:", proj_rid)

    try:
        cli(["+record-upsert", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
             "--record-id", target["_id"], "--json", json.dumps({"Project_ID": [{"id": proj_rid}]}, ensure_ascii=False)])
        time.sleep(6)
        r = read_row(target["_id"])
        print("AFTER EXEMPT LINK:")
        print(json.dumps({"Result_ID": r.get("Result_ID"), "Project_Run_Days": r.get("Project_Run_Days"),
                          "Is_Exempt": r.get("Is_Exempt"), "Auto_Score": r.get("Auto_Score"),
                          "Final_Score": r.get("Final_Score"), "Weighted_Score": r.get("Weighted_Score"),
                          "Monthly_Total": r.get("Monthly_Total"), "Commission_Base": r.get("Commission_Base"),
                          "Commission_Ratio": r.get("Commission_Ratio"), "Commission_Amount": r.get("Commission_Amount")}, ensure_ascii=False))
        ok = True
        if str(r.get("Is_Exempt")).lower() != "true":
            print("FAIL: Is_Exempt != true"); ok = False
        if str(r.get("Auto_Score")) != "100":
            print("FAIL: Auto_Score != 100"); ok = False
        if str(r.get("Weighted_Score")) != "0":
            print("FAIL: Weighted_Score != 0"); ok = False
        try:
            mtf = float(r.get("Monthly_Total")) if r.get("Monthly_Total") not in (None, "") else None
        except (TypeError, ValueError):
            mtf = None
        try:
            mbf = float(mt_before) if mt_before not in (None, "") else None
        except (TypeError, ValueError):
            mbf = None
        if mbf is not None and mtf is not None and abs(mtf - mbf) > 1e-6:
            print(f"FAIL: Monthly_Total changed {mbf} -> {mtf}"); ok = False
        base, ratio, amount = r.get("Commission_Base"), r.get("Commission_Ratio"), r.get("Commission_Amount")
        if base not in (None, "") and ratio not in (None, ""):
            expected_amount = float(base) * float(ratio)
            if amount in (None, "") or abs(float(amount) - expected_amount) > 1e-8:
                print(f"FAIL: Commission_Amount != Base×Ratio ({amount} != {expected_amount})"); ok = False
        else:
            print("FAIL: D-010 验证目标缺少 Commission_Base 或 Commission_Ratio"); ok = False
        print("EXEMPTION VERIFY:", "PASS" if ok else "FAIL")
    finally:
        cli(["+record-upsert", "--base-token", BASE, "--table-id", TABLES["Performance_Result"],
             "--record-id", target["_id"], "--json", json.dumps({"Project_ID": None}, ensure_ascii=False)])
        cli(["+record-delete", "--base-token", BASE, "--table-id", TABLES["Project"],
             "--record-id", proj_rid, "--yes"])
        print("cleanup done")

if __name__ == "__main__":
    main()
