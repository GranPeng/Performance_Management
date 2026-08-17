#!/usr/bin/env python3
"""只读拉取飞书 Base 20 张表结构与记录快照，供 T3 审计使用。

边界：
- 只调用 lark-cli base 的 table-list / field-list / record-list 读命令；
- 不创建、更新、删除任何 Base 资源；
- 输出本地 JSON 快照，避免在模型上下文中堆积大量原始记录。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

BASE_TOKEN = "FCxObLU6yao5jgsciZfcWHKwnjh"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "output" / "base_audit"
SNAPSHOT_FILE = OUT_DIR / "base_snapshot.json"
SUMMARY_FILE = OUT_DIR / "base_snapshot_summary.json"


def run_lark(args: list[str]) -> dict:
    cmd = ["lark-cli", "base", *args, "--as", "user"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(
            f"lark-cli failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON: {' '.join(cmd)}\n{proc.stdout[:2000]}") from exc
    if not payload.get("ok"):
        raise RuntimeError(f"lark-cli returned ok=false: {' '.join(cmd)}\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
    return payload


def safe_name(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", name).strip("_")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    table_payload = run_lark(["+table-list", "--base-token", BASE_TOKEN])
    tables = table_payload["data"]["tables"]

    snapshot_tables = []
    summary_tables = []

    for table in tables:
        table_id = table["id"]
        table_name = table["name"]
        field_payload = run_lark(["+field-list", "--base-token", BASE_TOKEN, "--table-id", table_id])
        fields = field_payload["data"]["fields"]

        record_payload = run_lark(
            [
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--limit",
                "200",
                "--format",
                "json",
            ]
        )
        record_data = record_payload["data"]
        field_names = record_data.get("fields", [])
        rows = record_data.get("data", [])
        record_ids = record_data.get("record_id_list", [])
        records = []
        for idx, row in enumerate(rows):
            record = {field_names[col_idx]: row[col_idx] if col_idx < len(row) else None for col_idx in range(len(field_names))}
            record["record_id"] = record_ids[idx] if idx < len(record_ids) else None
            records.append(record)

        table_snapshot = {
            "table_id": table_id,
            "table_name": table_name,
            "table_rev": table.get("rev"),
            "records_count_reported": table.get("records_count"),
            "records_count_read": len(records),
            "has_more": record_data.get("has_more"),
            "fields": fields,
            "records": records,
        }
        snapshot_tables.append(table_snapshot)

        per_table_file = OUT_DIR / f"{safe_name(table_name)}.snapshot.json"
        per_table_file.write_text(json.dumps(table_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_tables.append(
            {
                "table_id": table_id,
                "table_name": table_name,
                "table_rev": table.get("rev"),
                "records_count_reported": table.get("records_count"),
                "records_count_read": len(records),
                "has_more": record_data.get("has_more"),
                "field_count": len(fields),
                "field_names": [field.get("name") for field in fields],
                "snapshot_file": str(per_table_file.relative_to(ROOT)),
            }
        )

    snapshot = {
        "base_token": BASE_TOKEN,
        "table_count": len(snapshot_tables),
        "tables": snapshot_tables,
    }
    summary = {
        "base_token": BASE_TOKEN,
        "table_count": len(snapshot_tables),
        "tables": summary_tables,
    }

    SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"snapshot": str(SNAPSHOT_FILE), "summary": str(SUMMARY_FILE), "table_count": len(snapshot_tables)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
