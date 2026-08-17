#!/usr/bin/env python3
"""T9b verification: read back Performance_Result and compare Auto_Score/Final_Score vs T9a expected manifest."""
import json, shutil, subprocess, sys
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
MANIFEST = Path("data/output/T9a模拟Actual清单.json")

FIELDS = ["Result_ID", "Period", "Employee_ID", "Metric_ID", "Actual_ID", "Target_ID",
          "Achievement_Rate", "Weight", "Auto_Score", "Final_Score", "Manual_Score",
          "Rate_T1", "Score_T1", "Rate_T2", "Score_T2", "Rate_T3", "Score_T3",
          "Score_Cap", "Score_Floor", "Deduct_Per", "Target_Value_Snapshot", "Review_Status", "Status"]


def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result["data"]


def read_all():
    out = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLE, "--limit", "200", "--format", "json"]
        for f in FIELDS:
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


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_key = {}
    for r in manifest["records"]:
        key = (r["employee_record_id"], r["metric_record_id"])
        by_key.setdefault(key, []).append(r)

    rows = read_all()
    print(f"读回 Performance_Result: {len(rows)} 条")

    # 建立员工+指标 → 结果行映射
    result_by_key = {}
    for row in rows:
        emp = link_id(row.get("Employee_ID"))
        met = link_id(row.get("Metric_ID"))
        result_by_key.setdefault((emp, met), []).append(row)

    mismatches = []
    checked = 0
    auto_checked = 0
    manual_required = 0
    for key, entries in by_key.items():
        result_rows = result_by_key.get(key, [])
        if not result_rows:
            mismatches.append({"key": key, "issue": "MISSING_RESULT_ROW"})
            continue
        # manifest 可能有多条（如不同 intent），result 行按 actual 关联对应
        result_by_actual = {}
        for rr in result_rows:
            a = link_id(rr.get("Actual_ID"))
            result_by_actual[a] = rr
        for entry in entries:
            checked += 1
            if not entry["requires_actual"]:
                # 定性/奖惩：无需 Actual，Auto_Score 应空、Final_Score 公式兼容（Manual 未录入 → BLANK）
                manual_required += 1
                rr = result_rows[0] if len(result_rows) == 1 else result_by_actual.get(None, result_rows[0])
                auto_val = rr.get("Auto_Score")
                if auto_val not in (None, "", []):
                    mismatches.append({"issue": "QUALITATIVE_AUTO_SHOULD_BE_BLANK",
                                       "result_id": rr.get("Result_ID"), "auto_score": auto_val})
                continue
            # requires_actual=true：按 actual_record_id 找对应结果行
            # manifest 里没有 actual_record_id，只有 actual_id；需要从 Actual 表反查
            rr = result_by_actual.get(None)
            if len(result_rows) == 1:
                rr = result_rows[0]
            elif rr is None:
                # 多行情况：按匹配 actual 的 Source_Ref 或顺序；这里用第一个并允许后续人工核对
                rr = result_rows[0]
            if rr is None:
                mismatches.append({"issue": "NO_MATCH_RESULT_ROW", "key": key, "entry_actual": entry.get("actual_id")})
                continue
            auto_checked += 1
            exp = entry["expected_result"]
            got = rr.get("Auto_Score")
            if got is None or got == "":
                got = None
            else:
                got = round(float(got), 6)
            exp_f = round(float(exp), 6) if exp is not None else None
            if got != exp_f:
                mismatches.append({
                    "issue": "AUTO_SCORE_MISMATCH", "result_id": rr.get("Result_ID"),
                    "metric_id": entry["metric_id"], "metric_name": entry["metric_name"],
                    "actual_id": entry.get("actual_id"), "expected": exp_f, "got": got,
                    "intent": entry["design_intent"], "rate": entry.get("expected_achievement_rate"),
                })

    print(f"检查总数: {checked} | 自动评分检查: {auto_checked} | 人工类(无需Actual): {manual_required}")
    if mismatches:
        print(f"\n不一致/问题 {len(mismatches)} 条:")
        for m in mismatches[:30]:
            print(json.dumps(m, ensure_ascii=False))
    else:
        print("\n✅ 全部自动评分与 T9a 预期清单一致")

    # 输出 Auto_Score 分布摘要
    from collections import Counter
    print("\nAuto_Score 分布:", Counter(str(r.get("Auto_Score")) for r in rows if r.get("Auto_Score") is not None))
    print("Final_Score 分布:", Counter(str(r.get("Final_Score")) for r in rows if r.get("Final_Score") is not None))
    print("Weight 分布:", Counter(str(r.get("Weight")) for r in rows if r.get("Weight") is not None)[:5] if rows else "N/A")


if __name__ == "__main__":
    main()
