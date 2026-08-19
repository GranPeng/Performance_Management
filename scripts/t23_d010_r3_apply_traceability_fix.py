#!/usr/bin/env python3
"""校验 T23 D-010-R3 规则追溯修正；仅在仍为 R2 前置态时执行最小更新。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/output/T23_D010_R3追溯修正计划.json"
EXEC = ROOT / "data/output/T23_D010_R3追溯修正执行结果.json"
ERROR = ROOT / "data/output/T23_D010_R3错误日志.json"
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")


def invoke(args: list[str]) -> dict[str, Any]:
    process = subprocess.run([CLI, "base", *args, "--as", "user"], capture_output=True, text=True)
    try:
        raw = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI_NON_JSON: {process.stderr[-1000:]}") from exc
    if process.returncode != 0 or not raw.get("ok"):
        raise RuntimeError(json.dumps(raw, ensure_ascii=False))
    return raw["data"]


def record_snapshot(scope: dict[str, str]) -> dict[str, Any]:
    data = invoke([
        "+record-get", "--base-token", scope["base_token"], "--table-id", scope["table_id"],
        "--record-id", scope["record_id"], "--field-id", "Exemption_Scope_ID",
        "--field-id", "Rule_Version", "--field-id", "Note", "--field-id", "Max_Monthly_Revenue",
        "--format", "json",
    ])
    return dict(zip(data["fields"], data["data"][0]))


def field_snapshot(scope: dict[str, str]) -> dict[str, Any]:
    return invoke([
        "+field-get", "--base-token", scope["base_token"], "--table-id", scope["table_id"],
        "--field-id", scope["field_id"], "--format", "json",
    ])["field"]


def normalized_field(field: dict[str, Any]) -> dict[str, Any]:
    """比较可写字段定义；Base 返回的只读 id 不纳入目标状态。"""
    return {key: field.get(key) for key in ("name", "type", "default_value", "style", "description")}


def is_target(
    record: dict[str, Any], field: dict[str, Any], target_record: dict[str, Any], target_field: dict[str, Any]
) -> bool:
    return (
        record.get("Exemption_Scope_ID") == "EXS000001"
        and record.get("Rule_Version") == target_record["Rule_Version"]
        and record.get("Note") == target_record["Note"]
        and record.get("Max_Monthly_Revenue") == 1000000
        and normalized_field(field) == target_field
    )


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scope = plan["scope"]
    before_record = record_snapshot(scope)
    before_field = field_snapshot(scope)
    target_record = plan["record_update_payload"]
    target_field = plan["field_update_payload"]

    if is_target(before_record, before_field, target_record, target_field):
        outcome = "ALREADY_APPLIED_VERIFIED"
        after_record, after_field = before_record, before_field
    elif (
        before_record.get("Exemption_Scope_ID") == plan["legacy_precondition"]["Exemption_Scope_ID"]
        and before_record.get("Rule_Version") == plan["legacy_precondition"]["Rule_Version"]
        and before_field.get("description") == plan["legacy_precondition"]["Rule_Version_field_description"]
    ):
        invoke([
            "+record-upsert", "--base-token", scope["base_token"], "--table-id", scope["table_id"],
            "--record-id", scope["record_id"], "--json", json.dumps(target_record, ensure_ascii=False),
        ])
        invoke([
            "+field-update", "--base-token", scope["base_token"], "--table-id", scope["table_id"],
            "--field-id", scope["field_id"], "--json", json.dumps(target_field, ensure_ascii=False), "--yes",
        ])
        after_record, after_field = record_snapshot(scope), field_snapshot(scope)
        if not is_target(after_record, after_field, target_record, target_field):
            raise RuntimeError("READBACK_VALIDATION_FAILED")
        outcome = "APPLY_PASSED"
    else:
        raise RuntimeError("PRECONDITION_OR_TARGET_STATE_MISMATCH")

    EXEC.write_text(json.dumps({
        "change_id": plan["change_id"], "task": "T23", "status": outcome,
        "verified_at": datetime.now().astimezone().isoformat(),
        "before_record": before_record, "before_field": before_field,
        "after_record": after_record, "after_field": after_field,
        "rollback": plan["rollback"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": outcome, "execution": str(EXEC.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        ERROR.write_text(json.dumps({
            "task": "T23", "status": "FAILED", "step": "traceability_fix",
            "error": str(exc), "timestamp": datetime.now().astimezone().isoformat(),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAILED", "error": str(exc), "error_log": str(ERROR.relative_to(ROOT))}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
