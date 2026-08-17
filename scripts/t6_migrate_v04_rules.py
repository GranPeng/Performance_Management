#!/usr/bin/env python3
"""T6 V04 rules migration: validated, auditable and replay-safe at the batch level."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSON = ROOT / "data/output/绩效框架结构化规则.json"
OUT_DIR = ROOT / "data/output"
BASE_TOKEN = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {
    "Metric": "tbldKtdIVv8nnTyX",
    "Commission_Tier": "tblkZUoHYwBIvDYe",
    "Import_Batch": "tblHV3JoVR9AEETw",
    "Error_Log": "tbl4ZpuuOxZacWgj",
}


def cli(args: list[str]) -> dict:
    result = subprocess.run(args, text=True, capture_output=True, cwd=ROOT)
    try:
        body = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI returned non-JSON (rc={result.returncode}): {result.stdout}\n{result.stderr}") from exc
    if result.returncode != 0 or not body.get("ok"):
        raise RuntimeError(json.dumps(body, ensure_ascii=False))
    return body


def json_file_arg(path: Path) -> str:
    """lark-cli only accepts JSON @files relative to its current directory."""
    return "@./" + str(path.relative_to(ROOT))


def target_source_type(metric: dict) -> str:
    text = "\n".join(str(metric.get(k) or "") for k in ("name", "target", "calculation_formula", "data_source"))
    if any(x in text for x in ("GSV", "营收", "ROI")):
        return "BUDGET_V60"
    if "项目组人数" in text:
        return "AUTO_COMPUTE"
    if metric.get("data_source") in {"平台数据", "云视频管家", "平台客服后台数据"}:
        return "PLATFORM_IMPORT"
    return "MANUAL"


def budget_ref(metric: dict) -> str | None:
    text = "\n".join(str(metric.get(k) or "") for k in ("name", "target", "calculation_formula"))
    if "ROI" in text:
        return "V60.ROI表.签收ROI（D-005）"
    if "GSV" in text or "营收" in text:
        return "V60.主营业务收入=退货后GSV（D-005）"
    if "消耗" in text:
        return "V60.广告投流费=消耗（D-006）"
    return None


def scope_for_tier(sheet_code: str, commission_source: str) -> str:
    is_consumption = "消耗" in commission_source
    if is_consumption and sheet_code in {"PROD-DIR", "PROD-EDIT", "PROD-CAM"}:
        return "D-006：广告投流费=消耗；仅抖音/视频号内容制作团队可从消耗中分奖金。"
    if is_consumption:
        return "不适用D-006消耗分奖金范围（本梯度非内容制作团队）。"
    return "不适用D-006消耗分奖金范围。"


def build(now: str) -> tuple[dict, list[dict], list[dict], list[dict]]:
    source_doc = json.loads(SOURCE_JSON.read_text())
    source = source_doc["source"]
    source_file = source["file"]
    sha = source["sha256"]
    trace = f"Excel文件|{source_file}|SHA256:{sha}|T6-V04"
    batch_id = "IB-T6-V04-20260814-01"
    metrics, tiers, warnings = [], [], []

    for pos in source_doc["positions"]:
        code = pos["source_sheet_code"]
        for idx, metric in enumerate(pos["metrics"], start=1):
            metric_id = f"MET-V04-{code}-{idx:03d}"
            m = {
                "Metric_ID": metric_id,
                "Metric_Number": str(metric["source_metric_number"]),
                "Metric_Name": metric["name"],
                "Dimension": metric["dimension"],
                "Weight": metric["weight"],
                "Unit": metric.get("unit"),
                "Target_Description": metric.get("target"),
                "Calc_Rule_Text": metric.get("calculation_formula"),
                "Scoring_Standard_Text": metric["scoring_standard"],
                "Reward_Condition_Text": metric.get("reward_condition"),
                "Penalty_Condition_Text": metric.get("penalty_condition"),
                "Data_Source_Text": metric["data_source"],
                "Evaluation_Period_Text": metric["evaluation_period"],
                "Scoring_Type": metric["scoring_type"],
                "Scoring_Rule_Payload": json.dumps({"source_score_formula": metric.get("source_score_formula"), "score_cap_or_floor": metric.get("score_cap_or_floor")}, ensure_ascii=False, separators=(",", ":")),
                "Score_Cap_Is_Open": False,
                "Target_Source_Type": target_source_type(metric),
                "Budget_Field_Ref": budget_ref(metric),
                "Rule_Version": "V04",
                "Source_Sheet": pos["source_sheet"],
                "Source_Cell": metric["source_cell"],
                "Source_SHA256": sha,
                "Source": trace,
                "Create_Time": now,
                "Update_Time": now,
                "Status": "Active",
                # Position_ID deliberately omitted: Position table is empty; never replace relation with position name.
            }
            metrics.append({k: v for k, v in m.items() if v is not None})
            if metric.get("source_metric_number_raw") is None:
                warnings.append({"Object_Type": "Metric", "Object_ID": metric_id, "Error_Type": "SOURCE_DATA_MISSING", "Error_Content": f"源单元格 {pos['source_sheet']}!{metric['source_cell']} 的KPI编号为空；已按源JSON原样写入 Metric_Number={metric['source_metric_number']}，待业务方补齐。"})

        for rule in pos["commission_rules"]:
            for level, tier in enumerate(rule["tiers"], start=1):
                values = tier["values"]
                source_col = "I" if values.get("I") is not None else "H"
                lower_col = next(c["column"] for c in rule["columns"] if c.get("header") and "得分下限" in c["header"])
                upper_col = next(c["column"] for c in rule["columns"] if c.get("header") and "得分上限" in c["header"])
                lower = values.get(lower_col)
                upper = values.get(upper_col)
                ratio = values.get("M")
                open_upper = upper == "♾️"
                tier_id = f"CT-V04-{code}-{level:03d}"
                coefficient_col = next((c["column"] for c in rule["columns"] if c.get("header") and "系数比例" in c["header"]), None)
                rule_note = "D-009.5：超梯度上限得分按最高一档处理；不修改本梯度边界或比例数据。"
                if upper is not None and not open_upper and not isinstance(upper, (int, float)):
                    rule_note += f" 源表得分上限列原文={upper}，非数值，未写入 Score_Upper。"
                    warnings.append({"Object_Type": "Commission_Tier", "Object_ID": tier_id, "Error_Type": "VALUE_TYPE", "Error_Content": f"源单元格 {pos['source_sheet']}!{tier['source_cell']} 的得分上限原文为“{upper}”，不符合 Commission_Tier.Score_Upper 数字字段；已保留到 Rule_Note，待业务方补齐。"})
                t = {
                    "Commission_Tier_ID": tier_id,
                    "Tier_Level": level,
                    "Commission_Source_Text": values[source_col],
                    "Score_Lower": lower,
                    "Score_Upper": upper if isinstance(upper, (int, float)) else None,
                    "Upper_Is_Open": open_upper,
                    "Coefficient": values.get(coefficient_col) if coefficient_col and isinstance(values.get(coefficient_col), (int, float)) else None,
                    "Ratio_Value": ratio if isinstance(ratio, (int, float)) else None,
                    "Ratio_Text": str(ratio) if ratio is not None else None,
                    "Applicable_Scope": scope_for_tier(code, values[source_col]),
                    "Rule_Note": rule_note,
                    "Rule_Version": "V04",
                    "Source_Sheet": pos["source_sheet"],
                    "Source_Cell": tier["source_cell"],
                    "Source_SHA256": sha,
                    "Source": trace,
                    "Create_Time": now,
                    "Update_Time": now,
                    "Status": "Active",
                    # Position_ID and Metric_ID deliberately omitted pending referenced-table record IDs.
                }
                tiers.append({k: v for k, v in t.items() if v is not None})
                if lower is None:
                    warnings.append({"Object_Type": "Commission_Tier", "Object_ID": tier_id, "Error_Type": "SOURCE_DATA_MISSING", "Error_Content": f"源单元格 {pos['source_sheet']}!{tier['source_cell']} 未提供得分下限；保留为空，不以魔法数值替代，待业务方补齐。"})

    assert len(metrics) == 45, len(metrics)
    assert len(tiers) == 42, len(tiers)
    assert len({m['Metric_ID'] for m in metrics}) == 45
    assert len({t['Commission_Tier_ID'] for t in tiers}) == 42
    assert all("Position_ID" not in x for x in metrics + tiers)
    assert sum(x["Upper_Is_Open"] for x in tiers) == 2
    assert all(x.get("Score_Upper") is None for x in tiers if x["Upper_Is_Open"])

    batch = {
        "Batch_ID": batch_id, "Batch_Type": "MASTER_DATA", "Total_Count": 87, "Success_Count": 0, "Fail_Count": 0,
        "Import_Time": now, "Create_Time": now, "Update_Time": now, "Operator": "data-engineer/T6-V04-ETL",
        "Source": trace, "Source_Type": "Excel文件", "Source_File": source_file, "Source_SHA256": sha, "Status": "Active",
    }
    return batch, metrics, tiers, warnings


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true", help="Actually call lark-cli after preflight and payload persistence")
    args = p.parse_args()
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    batch, metrics, tiers, warnings = build(now)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_dir = OUT_DIR / "t6_payloads"
    payload_dir.mkdir(exist_ok=True)
    write_json(payload_dir / "metric_batch_create.json", {"create_records": metrics})
    write_json(payload_dir / "commission_tier_batch_create.json", {"create_records": tiers})
    write_json(payload_dir / "import_batch_create.json", {"create_records": [batch]})
    report = {
        "task": "T6", "status": "PREFLIGHT_PASSED" if not args.execute else "RUNNING", "source_file": json.loads(SOURCE_JSON.read_text())["source"],
        "batch_id": batch["Batch_ID"], "source_counts": {"Metric": len(metrics), "Commission_Tier": len(tiers)},
        "preflight": {"unique_metric_ids": len({x['Metric_ID'] for x in metrics}), "unique_tier_ids": len({x['Commission_Tier_ID'] for x in tiers}), "open_upper_tiers": sum(x['Upper_Is_Open'] for x in tiers), "position_links_deferred": 87, "warnings": warnings},
        "write_result": {}, "rollback": {"created_record_ids": {}, "method": "Use lark-cli base +record-delete with the recorded IDs and --yes if an approved rollback is required."},
    }
    report_path = OUT_DIR / "T6迁移校验报告.json"
    if not args.execute:
        write_json(report_path, report)
        print(json.dumps({"status": "PREFLIGHT_PASSED", "Metric": len(metrics), "Commission_Tier": len(tiers), "warnings": len(warnings), "report": str(report_path)}, ensure_ascii=False))
        return 0

    try:
        b = cli(["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", TABLES["Import_Batch"], "--as", "user", "--json", json_file_arg(payload_dir / "import_batch_create.json")])
        batch_record_id = b["data"]["record_id_list"][0]
        report["write_result"]["Import_Batch"] = b["data"]
        report["rollback"]["created_record_ids"]["Import_Batch"] = [batch_record_id]
        for entity, table, payload_name in [("Metric", TABLES["Metric"], "metric_batch_create.json"), ("Commission_Tier", TABLES["Commission_Tier"], "commission_tier_batch_create.json")]:
            r = cli(["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", table, "--as", "user", "--json", json_file_arg(payload_dir / payload_name)])
            ids = r["data"]["record_id_list"]
            report["write_result"][entity] = r["data"]
            report["rollback"]["created_record_ids"][entity] = ids
        # Write source completeness warnings only after batch record ID exists. These are data-quality warnings, not ETL write failures.
        error_records = []
        for n, w in enumerate(warnings, 1):
            error_records.append({"Error_ID": f"ERR-T6-V04-{n:03d}", "Batch_ID": [{"id": batch_record_id}], "Object_Type": w["Object_Type"], "Object_ID": w["Object_ID"], "Error_Type": w["Error_Type"], "Error_Content": w["Error_Content"], "Process_Status": "待处理", "Status": "Active", "Source": batch["Source"], "Create_Time": now, "Update_Time": now})
        if error_records:
            err_payload = payload_dir / "error_log_batch_create.json"
            write_json(err_payload, {"create_records": error_records})
            er = cli(["lark-cli", "base", "+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", TABLES["Error_Log"], "--as", "user", "--json", json_file_arg(err_payload)])
            report["write_result"]["Error_Log"] = er["data"]
            report["rollback"]["created_record_ids"]["Error_Log"] = er["data"]["record_id_list"]
        # All requested records were written; warnings are source-quality records and do not reduce ETL success count.
        update = {"update_records": {batch_record_id: {"Success_Count": 87, "Fail_Count": 0, "Update_Time": now}}}
        update_path = payload_dir / "import_batch_final_counts_update.json"
        write_json(update_path, update)
        ur = cli(["lark-cli", "base", "+record-batch-update", "--base-token", BASE_TOKEN, "--table-id", TABLES["Import_Batch"], "--as", "user", "--json", json_file_arg(update_path)])
        report["write_result"]["Import_Batch_update"] = ur["data"]
        report["status"] = "WRITE_COMPLETED"
    except Exception as exc:
        report["status"] = "WRITE_FAILED"
        report["write_error"] = str(exc)
        write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    write_json(report_path, report)
    print(json.dumps({"status": report["status"], "report": str(report_path), "created": {k: len(v) for k,v in report["rollback"]["created_record_ids"].items()}}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
