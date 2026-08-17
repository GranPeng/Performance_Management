#!/usr/bin/env python3
"""将已验证的 V60 预算目标 JSON 幂等写入飞书 Base Target 长表。

唯一数据源：data/output/预算目标结构化提取.json。
不修改源 Excel；Target_ID 与 Batch_ID 均由源文件 SHA-256 确定性生成。
重跑时先读取 Target_ID 全表：完全相同的记录不重复创建；同 ID 内容冲突会写 Error_Log 并失败退出。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSON = ROOT / "data/output/预算目标结构化提取.json"
REPORT = ROOT / "data/output/T7迁移校验报告.json"
PAYLOAD_DIR = ROOT / "data/output/.t7_payloads"
MEMORY = ROOT / ".hermes/memory/data_memory.md"

BASE_TOKEN = "FCxObLU6yao5jgsciZfcWHKwnjh"
TARGET_TABLE = "tblydZkf17kmzrO0"
BATCH_TABLE = "tblHV3JoVR9AEETw"
ERROR_TABLE = "tbl4ZpuuOxZacWgj"
AUTHORITATIVE_CHANNELS = {"抖音", "视频号", "天猫淘宝", "京东POP", "京东自营", "拼多多", "私域", "达播", "外部分销"}
# Target 同时承载多个关联字段；25 条可规避 Base 内部关联解析的瞬时限流。
BATCH_SIZE = 25


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cli(args: list[str], payload: dict[str, Any] | None = None, name: str = "payload") -> dict[str, Any]:
    """调用 CLI；所有失败均抛出，避免静默跳过。"""
    # 所有命令统一请求 JSON 输出；写入命令的 --json @file 仍用于请求体。
    cmd = ["lark-cli", "base", *args, "--as", "user", "--format", "json"]
    if payload is not None:
        PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = PAYLOAD_DIR / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        cmd.extend(["--json", f"@{path.relative_to(ROOT)}"])
    env = os.environ | {
        "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
        "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
    }
    # 限流是平台瞬态异常，不静默忽略：按退避重试，超过上限仍将原始错误写入 Error_Log。
    for attempt in range(5):
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=env)
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError:
            body = {"ok": False, "raw_stdout": result.stdout, "raw_stderr": result.stderr}
        if result.returncode == 0 and body.get("ok"):
            return body
        combined = result.stdout + result.stderr
        if "onOverQPSLimit" in combined and attempt < 4:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise RuntimeError(json.dumps({"command": cmd[:4], "exit_code": result.returncode, "result": body, "stderr": result.stderr}, ensure_ascii=False))
    raise RuntimeError("限流重试流程异常退出")


def list_all(table_id: str, fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE_TOKEN, "--table-id", table_id, "--limit", "200", "--offset", str(offset)]
        for field in fields:
            args.extend(["--field-id", field])
        out = cli(args)
        data = out["data"]
        fields = data.get("fields", [])
        record_ids = data.get("record_id_list", [])
        raw_rows = data.get("data", [])
        if len(raw_rows) != len(record_ids):
            raise RuntimeError(f"{table_id} 返回 data/record_id_list 长度不一致：{len(raw_rows)}/{len(record_ids)}")
        # +record-list 的 JSON rows 是按 fields 顺序排列的数组，record_id 位于平行数组。
        for record_id, raw in zip(record_ids, raw_rows):
            if not isinstance(raw, list) or len(raw) != len(fields):
                raise RuntimeError(f"{table_id} 返回行结构异常，无法安全映射字段")
            rows.append({"record_id": record_id, "fields": dict(zip(fields, raw))})
        if not data.get("has_more"):
            return rows
        offset += len(raw_rows)
        if not raw_rows:
            raise RuntimeError(f"{table_id} 返回 has_more=true 但本页为空，停止以避免漏读")


def chunks(items: list[Any], size: int = BATCH_SIZE):
    for i in range(0, len(items), size):
        yield i // size + 1, items[i : i + size]


def target_id(source_sha: str, row: int, channel: str, period: str) -> str:
    key = f"V60|{source_sha}|{row}|{channel}|{period}".encode("utf-8")
    return "TGT-V60-" + hashlib.sha256(key).hexdigest()[:20].upper()


def make_error(batch_record_id: str, batch_id: str, err_type: str, obj_id: str, content: str, stamp: str) -> dict[str, Any]:
    digest = hashlib.sha256(f"{batch_id}|{err_type}|{obj_id}|{content}".encode()).hexdigest()[:16].upper()
    return {
        "Error_ID": f"ERR-T7-{digest}", "Batch_ID": [{"id": batch_record_id}],
        "Object_Type": "Target", "Object_ID": obj_id, "Error_Type": err_type,
        "Error_Content": content, "Process_Status": "待处理", "Status": "Active",
        "Source": "T7 import_targets_to_base.py", "Create_Time": stamp, "Update_Time": stamp,
    }


def same_number(left: Any, right: Any) -> bool:
    """允许 API JSON 序列化产生的微小二进制浮点差，不容忍业务数值差异。"""
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
        return abs(float(left) - float(right)) <= 1e-10
    return left == right


def main() -> int:
    report: dict[str, Any] = {"task": "T7", "started_at": now(), "status": "running", "errors": []}
    try:
        data = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
        source_sha = data["source"]["sha256"]
        source_file = data["source"]["file"]
        batch_id = f"IB-V60-{source_sha[:16].upper()}"
        stamp = now()
        records: list[dict[str, Any]] = []
        pending_channels: set[str] = set()
        rejected_channels: list[dict[str, Any]] = []
        null_values = 0
        for item in data["budget_targets"]:
            for channel_block in item["channels"]:
                channel = channel_block["channel"]
                if channel not in AUTHORITATIVE_CHANNELS:
                    rejected_channels.append({"channel": channel, "source_row": item["source_row"], "reason": "非V60权威渠道，禁止写入Target"})
                    continue
                pending_channels.add(channel)  # Channel 表为空，按任务要求暂留 Channel_ID 空值。
                for monthly in channel_block["monthly_values"]:
                    src = monthly["source"]
                    value = monthly["value"]
                    if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                        raise ValueError(f"不可写入 number Target_Value：{src['source_cell']}={value!r}")
                    if value is None:
                        null_values += 1
                    # 数值以 T2 JSON 原值写入；Base 字段显示精度为4位，但 API 保留原始小数。
                    # 原公式和缓存值另存，保证逐值追溯。
                    stored_value = value
                    stored_cached = src.get("cached_value")
                    record = {
                        "Target_ID": target_id(source_sha, item["source_row"], channel, monthly["month"]),
                        "Budget_Item_Name": item["line_item"], "V60_Source_Row": item["source_row"],
                        "Period": monthly["month"], "Target_Value": stored_value, "Unit": item["unit"],
                        "Source_File": source_file, "Source_Sheet": src["source_sheet"],
                        "Source_Cell": src["source_cell"], "Source_Formula": src.get("formula"),
                        "Source_Cached_Value": stored_cached, "Source_SHA256": source_sha,
                        "Import_Status": "待确认" if value is None else "成功",
                        "Source": "V60 Excel / T2结构化JSON / T7迁移", "Status": "Active",
                        "Create_Time": stamp, "Update_Time": stamp,
                    }
                    records.append(record)
        if len(records) != 6156:
            raise ValueError(f"源JSON展开记录数应为6156，实际为{len(records)}；拒绝写入")

        # 先确保确定性的 Batch 存在，Target 需要该 Batch 的 record_id 作为 link。
        batches = list_all(BATCH_TABLE, ["Batch_ID", "Total_Count", "Source_SHA256"])
        batch_matches = [x for x in batches if x.get("fields", {}).get("Batch_ID") == batch_id]
        if len(batch_matches) > 1:
            raise RuntimeError(f"发现重复 Batch_ID：{batch_id}，拒绝继续")
        if batch_matches:
            batch_record_id = batch_matches[0]["record_id"]
            batch_created = False
        else:
            batch_payload = {
                "Batch_ID": batch_id, "Batch_Type": "BUDGET", "Total_Count": len(records),
                "Success_Count": 0, "Fail_Count": 0, "Import_Time": stamp, "Operator": "data-engineer/T7",
                "Source": "T2结构化JSON；D-001权威V60", "Source_Type": "Excel文件",
                "Source_File": source_file, "Source_SHA256": source_sha, "Status": "Active",
                "Create_Time": stamp, "Update_Time": stamp,
            }
            out = cli(["+record-upsert", "--base-token", BASE_TOKEN, "--table-id", BATCH_TABLE], batch_payload, "batch_create")
            batch_record_id = out["data"]["record"]["record_id"]
            batch_created = True

        for r in records:
            r["Import_Batch_ID"] = [{"id": batch_record_id}]

        existing_rows = list_all(TARGET_TABLE, ["Target_ID", "Target_Value", "Source_Cell", "Source_SHA256", "Import_Batch_ID"])
        existing = {x.get("fields", {}).get("Target_ID"): x for x in existing_rows if x.get("fields", {}).get("Target_ID")}
        source_ids = {r["Target_ID"] for r in records}
        duplicate_source_ids = len(source_ids) != len(records)
        if duplicate_source_ids:
            raise RuntimeError("源JSON生成了重复Target_ID，拒绝写入")
        conflicts = []
        missing = []
        for r in records:
            old = existing.get(r["Target_ID"])
            if old is None:
                missing.append(r)
                continue
            oldf = old.get("fields", {})
            old_value = oldf.get("Target_Value")
            if not same_number(old_value, r["Target_Value"]) or oldf.get("Source_Cell") != r["Source_Cell"] or oldf.get("Source_SHA256") != r["Source_SHA256"]:
                conflicts.append({"target_id": r["Target_ID"], "record_id": old["record_id"], "expected": {"Target_Value": r["Target_Value"], "Source_Cell": r["Source_Cell"], "Source_SHA256": r["Source_SHA256"]}, "actual": oldf})
        if conflicts:
            error_records = [make_error(batch_record_id, batch_id, "ID存在性", x["target_id"], "幂等键冲突：同一Target_ID对应内容不一致；未覆盖原记录。", stamp) for x in conflicts]
            for n, group in chunks(error_records):
                cli(["+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", ERROR_TABLE], {"create_records": group}, f"error_conflict_{n}")
            raise RuntimeError(f"发现 {len(conflicts)} 条Target_ID内容冲突；已写Error_Log，未覆盖旧数据")

        created = 0
        failures: list[dict[str, Any]] = []
        for n, group in chunks(missing):
            try:
                out = cli(["+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", TARGET_TABLE], {"create_records": group}, f"target_create_{n}")
                got = len(out["data"].get("record_id_list", []))
                if got != len(group):
                    raise RuntimeError(f"批次 {n} 返回记录数 {got}，期望 {len(group)}")
                created += got
            except Exception as exc:
                failures.extend(make_error(batch_record_id, batch_id, "写入失败", r["Target_ID"], str(exc)[:1500], stamp) for r in group)
                break
        if failures:
            for n, group in chunks(failures):
                cli(["+record-batch-create", "--base-token", BASE_TOKEN, "--table-id", ERROR_TABLE], {"create_records": group}, f"error_write_{n}")
            raise RuntimeError(f"Target 写入失败 {len(failures)} 条；已写 Error_Log，停止后续批次")

        # 读回全部 Target，执行条数、键唯一性、抽样源值/定位核验。
        after_rows = list_all(TARGET_TABLE, ["Target_ID", "Target_Value", "Source_Cell", "Source_Formula", "Source_Cached_Value", "Source_SHA256", "Import_Batch_ID"])
        migrated = [x for x in after_rows if x.get("fields", {}).get("Target_ID") in source_ids]
        by_id = {x["fields"]["Target_ID"]: x for x in migrated}
        sample_indexes = [0, len(records)//2, len(records)-1]
        samples = []
        for i in sample_indexes:
            expected = records[i]
            actual = by_id.get(expected["Target_ID"], {}).get("fields", {})
            samples.append({"target_id": expected["Target_ID"], "source_cell": expected["Source_Cell"], "expected_value": expected["Target_Value"], "actual_value": actual.get("Target_Value"), "matched": same_number(actual.get("Target_Value"), expected["Target_Value"]) and actual.get("Source_Cell") == expected["Source_Cell"] and actual.get("Source_Formula") == expected["Source_Formula"] and same_number(actual.get("Source_Cached_Value"), expected["Source_Cached_Value"])})
        mismatch_count = sum(1 for r in records if (r["Target_ID"] not in by_id or not same_number(by_id[r["Target_ID"]].get("fields", {}).get("Target_Value"), r["Target_Value"]) or by_id[r["Target_ID"]].get("fields", {}).get("Source_Cell") != r["Source_Cell"]))
        if len(migrated) != 6156 or mismatch_count or not all(x["matched"] for x in samples):
            raise RuntimeError(f"读回校验失败：migrated={len(migrated)} mismatch={mismatch_count} samples={samples}")

        # 批次最终对账。所有 6156 行都已落库；空缓存值不等于写入失败。
        cli(["+record-upsert", "--base-token", BASE_TOKEN, "--table-id", BATCH_TABLE, "--record-id", batch_record_id], {
            "Success_Count": 6156, "Fail_Count": 0, "Update_Time": now(),
        }, "batch_reconcile")
        report.update({
            "status": "success", "finished_at": now(), "base_token": BASE_TOKEN,
            "batch_id": batch_id, "batch_record_id": batch_record_id, "batch_created_this_run": batch_created,
            "source_json_sha256": sha256(SOURCE_JSON), "source_excel_sha256": source_sha,
            "source_value_count": len(records), "base_target_count_for_source": len(migrated),
            "difference": len(migrated) - len(records), "created_this_run": created,
            "already_present_this_run": len(records) - len(missing), "null_target_value_count": null_values,
            "pending_channel_mapping": sorted(pending_channels), "rejected_non_authoritative_channels": rejected_channels,
            "sample_checks": samples, "error_log_created": 0,
        })
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        MEMORY.parent.mkdir(parents=True, exist_ok=True)
        MEMORY.write_text(
            "# 数据迁移记忆\n\n"
            "- T7 将 `预算目标结构化提取.json` 的 V60 57×9×12=6156 行迁入 Target。\n"
            "- 幂等键：`TGT-V60-` + source SHA/源行/渠道/月度的 SHA-256 前20位；批次：`IB-V60-` + 源 SHA 前16位。\n"
            "- Channel 表为空时 Target.Channel_ID 暂空；待 Channel 主数据迁入后按报告的 pending_channel_mapping 回填关联。\n"
            "- `Target_Value=null` 表示源 Excel 缓存为空（常见 `=\"\"`），不是写入失败；原公式和缓存值保留追溯。\n"
            "- 脚本先读回 Target_ID：同键同内容跳过，冲突写 Error_Log 且拒绝覆盖；每次完成读回 6156 行与三点抽样。\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        report.update({"status": "failed", "finished_at": now(), "errors": [str(exc)]})
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
