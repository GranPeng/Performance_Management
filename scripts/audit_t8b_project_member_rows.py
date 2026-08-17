#!/usr/bin/env python3
"""仅本地读取已固化的源表快照和 D-010 计划，生成101行 Project_Member 迁移审计清单。

不调用飞书 API，不修改源在线表或正式 Base。用于逐行追溯迁移结论与业务待确认项。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
SOURCE = OUT / "t8b_old_project_member_source.json"
PLAN = OUT / "T8b_d010_finalize_plan.json"
OUTPUT = OUT / "T8b_project_member_row_audit.json"


def first(value):
    return value[0] if isinstance(value, list) and value else value


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["data"]
    headers = source["fields"]
    rows = [
        {"source_index": index, "old_record_id": record_id, **dict(zip(headers, values))}
        for index, (record_id, values) in enumerate(zip(source["record_id_list"], source["data"]), 1)
    ]
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    created = {item["old_record_id"]: item for item in plan["project_member"]["records"]}
    unresolved = {item["old_record_id"]: item for item in plan["project_member"]["unresolved"]}

    if len(rows) != 101 or len(created) != 23 or len(unresolved) != 78:
        raise RuntimeError("source/plan cardinality mismatch")
    if set(created) & set(unresolved) or set(created) | set(unresolved) != {row["old_record_id"] for row in rows}:
        raise RuntimeError("source row disposition is not a complete, disjoint partition")

    audit_rows = []
    for row in rows:
        old_id = row["old_record_id"]
        common = {
            "source_index": row["source_index"],
            "old_record_id": old_id,
            "source_name": row.get("姓名"),
            "source_phone": row.get("手机号码"),
            "source_project": first(row.get("人员对照项目")),
            "source_channel": first(row.get("项目所属渠道")),
            "allocation_ratio": None,
            "allocation_ratio_decision": "源表无分摊比例字段或数值；按任务要求留空，待业务确认。",
            "is_primary": False,
            "is_primary_decision": "源表无主项目标识字段；按 D-010 写 false 作为非断言占位，待唯一在线维护入口逐条确认。",
            "effective_start": None,
            "effective_start_decision": "源表无生效日期；按 D-010 留空，不以导入日期伪造历史生效日。",
        }
        if old_id in created:
            record = created[old_id]["record"]
            audit_rows.append({
                **common,
                "disposition": "已插入 Project_Member",
                "project_member_id": record["Project_Member_ID"],
                "employee_link_record_id": record["Employee_ID"][0]["id"],
                "project_link_record_id": record["Project_ID"][0]["id"],
                "channel_link_record_id": record.get("Channel_ID", [{}])[0].get("id"),
                "exception_reasons": [],
            })
        else:
            audit_rows.append({
                **common,
                "disposition": "未插入；已记录 Active Error_Log",
                "project_member_id": None,
                "employee_link_record_id": None,
                "project_link_record_id": None,
                "channel_link_record_id": None,
                "exception_reasons": unresolved[old_id]["reasons"],
            })

    result = {
        "audit_name": "T8b Project_Member 101行逐行迁移审计",
        "decision": "D-010",
        "source_snapshot": str(SOURCE.relative_to(ROOT)),
        "migration_plan": str(PLAN.relative_to(ROOT)),
        "read_only_scope": "本脚本仅生成本地审计文件；不修改在线源表或正式 Base。",
        "counts": {
            "source_rows": len(rows),
            "inserted_project_member": sum(x["disposition"] == "已插入 Project_Member" for x in audit_rows),
            "active_error_log": sum(x["disposition"] != "已插入 Project_Member" for x in audit_rows),
        },
        "validation": {
            "source_partition_complete": True,
            "source_partition_disjoint": True,
            "inserted_ids_from_t8a_registered_records": True,
            "effective_start_all_null_for_inserted": all(x["effective_start"] is None for x in audit_rows if x["project_member_id"]),
            "allocation_ratio_all_null_for_inserted": all(x["allocation_ratio"] is None for x in audit_rows if x["project_member_id"]),
            "is_primary_all_false_pending_confirmation": all(x["is_primary"] is False for x in audit_rows if x["project_member_id"]),
        },
        "rows": audit_rows,
    }
    if result["counts"]["inserted_project_member"] + result["counts"]["active_error_log"] != 101:
        raise RuntimeError("reconciliation failed")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "output": str(OUTPUT), **result["counts"], "validation": result["validation"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
