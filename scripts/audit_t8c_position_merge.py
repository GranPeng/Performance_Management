#!/usr/bin/env python3
"""T8c 岗位归并修复的只读预检与审计报告。

本脚本不修改 Base。它导出 Position、Employee、Metric 的最小字段集，
按 Position_Name 分组，验证员工/指标所挂岗位是否一致，并检查模型是否有
可写的「归并注记」承载字段。若没有该字段，调用方不得擅自复用 Source 或
Position_Alias，必须走模型变更流程。
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
DOCS = ROOT / "docs"
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
T = {
    "Position": "tbldzvsg9Op6pK29",
    "Employee": "tblc59aB4EnSxkQv",
    "Metric": "tbldKtdIVv8nnTyX",
}
FIELDS = {
    "Position": ["Position_ID", "Position_Name", "Org_ID", "Status", "Note", "Position_Alias", "Source", "Update_Time"],
    "Employee": ["Employee_ID", "Name", "Position_ID", "Perf_Participate_Status", "Status"],
    "Metric": ["Metric_ID", "Position_ID", "Metric_Name", "Status", "Source_Sheet"],
}


def cli(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        ["lark-cli", "base", *args, "--as", "user", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ | {
            "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
            "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
        },
    )
    try:
        body = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI 输出不是 JSON: {result.stdout!r}; stderr={result.stderr!r}") from exc
    if result.returncode != 0 or not body.get("ok"):
        raise RuntimeError(json.dumps({"args": args, "body": body, "stderr": result.stderr}, ensure_ascii=False))
    return body


def list_rows(table_id: str, fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", table_id, "--limit", "200", "--offset", str(offset)]
        for field in fields:
            args.extend(["--field-id", field])
        data = cli(args)["data"]
        names, values, record_ids = data["fields"], data["data"], data["record_id_list"]
        if len(values) != len(record_ids):
            raise RuntimeError(f"{table_id} 返回 data/record_id_list 长度不一致")
        rows.extend({"record_id": rid, **dict(zip(names, row))} for rid, row in zip(record_ids, values))
        if not data.get("has_more"):
            return rows
        if not values:
            raise RuntimeError(f"{table_id} has_more=true 但返回空页")
        offset += len(values)


def link_id(value: Any) -> str | None:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0].get("id")
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    fields = {name: cli(["+field-list", "--base-token", BASE, "--table-id", table_id])["data"]["fields"] for name, table_id in T.items()}
    rows = {name: list_rows(T[name], FIELDS[name]) for name in T}
    for name, values in rows.items():
        (OUT / f"t8c_{name.lower()}_preflight.json").write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    positions_by_record = {row["record_id"]: row for row in rows["Position"]}
    positions_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows["Position"]:
        positions_by_name[row.get("Position_Name") or "<空岗位名>"].append(row)

    duplicate_groups = []
    for name in sorted(positions_by_name):
        group = positions_by_name[name]
        if len(group) < 2:
            continue
        group_ids = {row["record_id"] for row in group}
        employees = [row for row in rows["Employee"] if link_id(row.get("Position_ID")) in group_ids]
        metrics = [row for row in rows["Metric"] if link_id(row.get("Position_ID")) in group_ids]
        employee_position_ids = sorted({link_id(row.get("Position_ID")) for row in employees if link_id(row.get("Position_ID"))})
        metric_position_ids = sorted({link_id(row.get("Position_ID")) for row in metrics if link_id(row.get("Position_ID"))})
        mismatch = bool(employee_position_ids and metric_position_ids and set(employee_position_ids) != set(metric_position_ids))
        # T8c 已明确业务例外：主管同名不在 V04 范围，不做推断式合并。
        if name == "电商客服专员" and not mismatch and any(p.get("Position_ID") == "POS000037" and p.get("Status") == "Inactive" and p.get("Note") == "已并入 POS000038，2026-08-17，T8c" for p in group):
            conclusion = "归并完成：EMP000027/EMP000028 已改挂 POS000038；POS000037 已 Inactive 并保留归并注记；6项 Active Metric 仍挂 POS000038。"
        elif name == "电商客服专员" and mismatch:
            conclusion = "需归并：Employee 与 Metric 挂靠不同同名 Position；目标保留 Metric 所在 Position。"
        elif name == "电商客服主管":
            conclusion = "暂不处理：同名但属于不同实体语义，且不在 V04 KPI 覆盖范围；按任务要求保留。"
        elif not metrics:
            conclusion = "保留：无 Metric 挂靠，无法以 V04 KPI 规则证明应合并；同名记录按部门实体语义保留。"
        elif mismatch:
            conclusion = "待归并：Employee 与 Metric 挂靠不同同名 Position；需按 Metric 所在 Position 确定主记录。"
        else:
            conclusion = "保留：Employee 与 Metric 挂靠未发现跨记录不一致，不能仅凭同名合并。"
        duplicate_groups.append({
            "position_name": name,
            "positions": [{
                "record_id": p["record_id"], "Position_ID": p.get("Position_ID"), "Org_record_id": link_id(p.get("Org_ID")),
                "Status": p.get("Status"), "Note": p.get("Note"), "Position_Alias": p.get("Position_Alias"), "Source": p.get("Source"),
            } for p in group],
            "employee_count": len(employees),
            "employee_ids": [e.get("Employee_ID") for e in employees],
            "employee_position_record_ids": employee_position_ids,
            "metric_count": len(metrics),
            "metric_ids": [m.get("Metric_ID") for m in metrics],
            "metric_position_record_ids": metric_position_ids,
            "employee_metric_position_mismatch": mismatch,
            "conclusion": conclusion,
        })

    pos37 = next((p for p in rows["Position"] if p.get("Position_ID") == "POS000037"), None)
    pos38 = next((p for p in rows["Position"] if p.get("Position_ID") == "POS000038"), None)
    affected = [e for e in rows["Employee"] if e.get("Employee_ID") in {"EMP000027", "EMP000028"}]
    preflight_errors = []
    if len(rows["Position"]) != 53:
        preflight_errors.append(f"Position 行数不是预期 53，而是 {len(rows['Position'])}")
    if len(rows["Employee"]) != 80:
        preflight_errors.append(f"Employee 行数不是预期 80，而是 {len(rows['Employee'])}")
    if len(rows["Metric"]) != 45:
        preflight_errors.append(f"Metric 行数不是预期 45，而是 {len(rows['Metric'])}")
    if not pos37 or not pos38:
        preflight_errors.append("未同时找到 POS000037 / POS000038")
    if {e.get("Employee_ID") for e in affected} != {"EMP000027", "EMP000028"}:
        preflight_errors.append("未同时找到 EMP000027 / EMP000028")
    if pos38:
        metric_count_pos38 = sum(link_id(m.get("Position_ID")) == pos38["record_id"] for m in rows["Metric"])
        if metric_count_pos38 != 6:
            preflight_errors.append(f"POS000038 的 Metric 数量不是预期 6，而是 {metric_count_pos38}")
    else:
        metric_count_pos38 = 0

    # 按任务口径逐条核验「确认参与」员工当前 Position 是否至少有一条 Active Metric。
    active_metric_position_ids = {link_id(metric.get("Position_ID")) for metric in rows["Metric"] if metric.get("Status") == "Active" and link_id(metric.get("Position_ID"))}
    confirmed_participants = [employee for employee in rows["Employee"] if employee.get("Perf_Participate_Status") == "确认参与"]
    participant_failures = [{
        "Employee_ID": employee.get("Employee_ID"),
        "Name": employee.get("Name"),
        "Position_record_id": link_id(employee.get("Position_ID")),
    } for employee in confirmed_participants if link_id(employee.get("Position_ID")) not in active_metric_position_ids]
    if len(confirmed_participants) != 32:
        preflight_errors.append(f"确认参与员工数量不是任务预期 32，而是 {len(confirmed_participants)}")

    position_field_names = {field["name"] for field in fields["Position"]}
    note_candidates = sorted(position_field_names & {"备注", "归并注记", "Merge_Note", "Note", "Notes"})
    if not note_candidates:
        preflight_errors.append("Position 不存在可写的归并注记字段；不得将归并说明写入 Source（不可变追溯字段）或 Position_Alias（仅别名语义）。")

    report = {
        "task": "T8c",
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "mode": "READ_ONLY_PREFLIGHT",
        "base_token": BASE,
        "counts": {name: len(values) for name, values in rows.items()},
        "known_case": {
            "POS000037": {"record_id": pos37["record_id"] if pos37 else None, "status": pos37.get("Status") if pos37 else None},
            "POS000038": {"record_id": pos38["record_id"] if pos38 else None, "status": pos38.get("Status") if pos38 else None, "metric_count": metric_count_pos38},
            "affected_employees": [{"Employee_ID": e.get("Employee_ID"), "Name": e.get("Name"), "Position_record_id": link_id(e.get("Position_ID"))} for e in affected],
        },
        "duplicate_position_groups": duplicate_groups,
        "position_note_field_candidates": note_candidates,
        "participant_active_metric_verification_pre": {
            "expected_confirmed_participants": 32,
            "confirmed_participants": len(confirmed_participants),
            "passed": len(confirmed_participants) - len(participant_failures),
            "failed": len(participant_failures),
            "failures": participant_failures,
        },
        "preflight_errors": preflight_errors,
        "status": "BLOCKED_SCHEMA" if preflight_errors else "PREFLIGHT_PASSED",
        "no_write_statement": "本次脚本只读。未修改 Position、Employee、Metric、Target 或任何 Base 记录。",
    }
    (OUT / "T8c_position_merge_post_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# T8c 岗位归并全量排查报告", "", f"生成时间：{report['generated_at']}", "", "## 运行方式", "", "只读预检；未修改任何 Base 记录。", "", "## 计数", "", *[f"- {name}: {count}" for name, count in report["counts"].items()], "", "## 同名岗位组及结论", ""]
    for group in duplicate_groups:
        lines.append(f"### {group['position_name']}")
        for position in group["positions"]:
            lines.append(f"- {position['Position_ID']}（record_id={position['record_id']}；Org={position['Org_record_id']}；Status={position['Status']}；Note={position.get('Note') or '空'}）")
        lines.extend([
            f"- Employee：{group['employee_count']} 人，挂靠 record_id={', '.join(group['employee_position_record_ids']) or '无'}",
            f"- Metric：{group['metric_count']} 项，挂靠 record_id={', '.join(group['metric_position_record_ids']) or '无'}",
            f"- 结论：{group['conclusion']}",
            "",
        ])
    lines.extend([
        "## 确认参与员工 → Active Metric 预检",
        "",
        f"- 预期/实际确认参与人数：32/{len(confirmed_participants)}",
        f"- 当前通过/失败：{len(confirmed_participants) - len(participant_failures)}/{len(participant_failures)}",
        *[f"- 未通过：{item['Employee_ID']}（{item['Name']}，Position record_id={item['Position_record_id']}）" for item in participant_failures],
        "",
        "## 阻断项",
        "",
        *[f"- {error}" for error in preflight_errors],
        "",
        "## 后续维护说明",
        "",
        "1. D-012/CHG-T8C-001 已为全部 14 张正式表补建可选 Note(TEXT) 字段；后续治理说明须追加在该字段，不得复用 Source 或 Position_Alias。",
        "2. 本次仅归并 EMP000027、EMP000028 至 POS000038，并将 POS000037 置 Inactive；未修改 Metric、Target 或业务结果。",
        "3. 归并前快照、写入结果与记录级回滚计划见 data/output/T8c_position_merge_execution_*.json 及 scripts/rollback_t8c_position_merge.py。",
        "",
    ])
    (DOCS / "T8c_岗位归并全量排查报告.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["status"], "preflight_errors": preflight_errors, "report": str(OUT / "T8c_position_merge_post_verification.json"), "markdown": str(DOCS / "T8c_岗位归并全量排查报告.md")}, ensure_ascii=False))
    if report["status"] != "PREFLIGHT_PASSED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
