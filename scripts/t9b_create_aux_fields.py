#!/usr/bin/env python3
"""T9b helper: create Performance_Result auxiliary parameter snapshot columns."""
import json, shutil, subprocess, sys
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"  # Performance_Result
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

FIELDS = [
    {"type": "number", "name": "Target_Value_Snapshot",
     "description": "评分参数快照 · 目标值快照（无 Target_ID 可关联时供达成率计算；取自 T9a target_value_used）"},
    {"type": "number", "name": "Score_Cap",
     "description": "评分参数快照 · 达成率型封顶值（V04 最高档封顶，如 150/120/110/100）"},
    {"type": "number", "name": "Score_Floor",
     "description": "评分参数快照 · 保底值（各类型兜底得分，通常 0）"},
    {"type": "number", "name": "Rate_T1",
     "description": "评分参数快照 · 档1阈值（达成率型=达成率下限；次数阈值型=次数上限）"},
    {"type": "number", "name": "Score_T1",
     "description": "评分参数快照 · 档1得分（达成率型 0=按实际达成率×100 封顶计入；非 0=固定分）"},
    {"type": "number", "name": "Rate_T2",
     "description": "评分参数快照 · 档2阈值（达成率型=达成率下限；次数阈值型=次数上限）"},
    {"type": "number", "name": "Score_T2",
     "description": "评分参数快照 · 档2得分"},
    {"type": "number", "name": "Rate_T3",
     "description": "评分参数快照 · 档3阈值（达成率型=达成率下限；次数阈值型不用）"},
    {"type": "number", "name": "Score_T3",
     "description": "评分参数快照 · 档3得分"},
    {"type": "number", "name": "Deduct_Per",
     "description": "评分参数快照 · 扣分制单次扣分值（V04 原文单次扣除 5 分）"},
]

def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result

def main():
    payload = json.dumps(FIELDS, ensure_ascii=False)
    r = cli(["+field-create", "--base-token", BASE, "--table-id", TABLE, "--json", payload])
    created = r["data"].get("created", [])
    print(json.dumps({"status": "CREATED", "count": len(created), "fields": [f.get("name") or f for f in created]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
