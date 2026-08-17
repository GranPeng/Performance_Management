#!/usr/bin/env python3
"""Read-only verification for the T9a simulated Actual batch."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
ACTUAL_TABLE = "tbli9VhcUFjVDeNd"
BATCH_TABLE = "tblHV3JoVR9AEETw"
PERIOD = "2026-07"
SOURCE = "SIMULATED_T9A"
BATCH_ID = "IB-T9A-SIM-20260817-01"
MANIFEST = Path("data/output/T9a模拟Actual清单.json")
OUT = Path("data/output/T9a模拟Actual验证报告.json")
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")


def cli(args: list[str]) -> dict:
    p = subprocess.run([CLI, "base", *args, "--as", "user"], text=True, capture_output=True)
    payload = json.loads(p.stdout)
    if p.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(payload)
    return payload["data"]


def list_records(table_id: str, fields: list[str]) -> list[dict]:
    rows, offset = [], 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", table_id, "--limit", "200", "--offset", str(offset), "--format", "json"]
        for field in fields:
            args += ["--field-id", field]
        data = cli(args)
        for record_id, values in zip(data["record_id_list"], data["data"]):
            row = dict(zip(data["fields"], values))
            row["_record_id"] = record_id
            rows.append(row)
        if not data.get("has_more"):
            return rows
        offset += len(data["record_id_list"])


def link_id(value):
    return value[0]["id"] if value else None


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = [r for r in manifest["records"] if r.get("requires_actual")]
    actual_rows = list_records(ACTUAL_TABLE, ["Actual_ID", "Metric_ID", "Employee_ID", "Period", "Source", "Status", "Import_Batch_ID", "Actual_Value"])
    batch_rows = list_records(BATCH_TABLE, ["Batch_ID", "Batch_Type", "Source_Type", "Total_Count", "Success_Count", "Fail_Count", "Status"])
    selected = [r for r in actual_rows if r.get("Period") == PERIOD and r.get("Source") == SOURCE and r.get("Status") == "Active"]
    batches = [r for r in batch_rows if r.get("Batch_ID") == BATCH_ID]
    expected_ids = {r["actual_id"] for r in expected}
    actual_ids = {r.get("Actual_ID") for r in selected}
    required_coverage = {
        "达成率/进度型": {"达成率>1.0，封顶触发样本", "达成率0.8-1.0样本", "达成率0.6-0.8样本", "达成率<0.6样本"},
        "定性等级型": {"差", "合格", "优秀"},
        "次数阈值型": {"0次样本", "阈值内样本", "超阈值样本"},
        "奖惩制": {"奖励触发", "处罚触发", "均不触发"},
        "扣分制": {"无违规样本", "部分扣分样本", "扣到保底样本"},
    }
    cap_samples = [r for r in expected if r.get("design_intent") == "达成率>1.0，封顶触发样本"]
    checks = {
        "manifest_errors_empty": not manifest.get("errors"),
        "manifest_participants_32": manifest.get("participant_count") == 32,
        "manifest_actual_count_93": len(expected) == 93,
        "all_five_scoring_type_scenarios_covered": all(set(manifest.get("coverage", {}).get(kind, [])) >= intents for kind, intents in required_coverage.items()),
        "true_score_cap_case_present": bool(cap_samples) and all(r.get("expected_achievement_rate") == 1.6 for r in cap_samples),
        "actual_readback_count_matches": len(selected) == len(expected),
        "actual_id_set_matches_manifest": actual_ids == expected_ids,
        "all_actuals_have_employee_and_metric_links": all(link_id(r.get("Employee_ID")) and link_id(r.get("Metric_ID")) for r in selected),
        "all_actuals_link_to_t9a_batch": len(batches) == 1 and all(link_id(r.get("Import_Batch_ID")) == batches[0]["_record_id"] for r in selected),
        "batch_matches_counts_and_status": len(batches) == 1 and batches[0].get("Batch_Type") == "ACTUAL" and batches[0].get("Source_Type") == "SIMULATED" and batches[0].get("Total_Count") == 93 and batches[0].get("Success_Count") == 93 and batches[0].get("Fail_Count") == 0 and batches[0].get("Status") == "Success",
    }
    result = {
        "task": "T9a",
        "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": "READ_ONLY",
        "period": PERIOD,
        "source": SOURCE,
        "batch_id": BATCH_ID,
        "batch_record_id": batches[0]["_record_id"] if len(batches) == 1 else None,
        "readback": {"actual_count": len(selected), "batch_count": len(batches), "actual_ids": sorted(actual_ids)},
        "checks": checks,
        "status": "PASSED" if all(checks.values()) else "FAILED",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASSED":
        sys.exit(2)


if __name__ == "__main__":
    main()
