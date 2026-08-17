#!/usr/bin/env python3
"""T9b: update formula fields replacing BLANK() with empty-string fallback (BLANK() breaks runtime)."""
import json, shutil, subprocess
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

achievement_expr = (
    'IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), "", '
    'IFERROR(FIRST([Actual_ID].[Actual_Value]) / IFBLANK(FIRST([Target_ID].[Target_Value]), [Target_Value_Snapshot]), ""))'
)

auto_expr = (
    'SWITCH(FIRST([Metric_ID].[Scoring_Type]), '
    '"达成率/进度型", IF(ISBLANK([Achievement_Rate]), "", '
    'IF([Achievement_Rate] >= [Rate_T1], IF([Score_T1] = 0, MIN([Achievement_Rate] * 100, [Score_Cap]), [Score_T1]), '
    'IF([Achievement_Rate] >= [Rate_T2], [Score_T2], IF([Achievement_Rate] >= [Rate_T3], [Score_T3], [Score_Floor])))), '
    '"次数阈值型", IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), "", '
    'IF(FIRST([Actual_ID].[Actual_Value]) <= [Rate_T1], [Score_T1], '
    'IF(FIRST([Actual_ID].[Actual_Value]) < [Rate_T2], [Score_T2], [Score_Floor]))), '
    '"扣分制", IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), "", '
    'MAX(100 - FIRST([Actual_ID].[Actual_Value]) * [Deduct_Per], [Score_Floor])))'
)

final_expr = (
    'IF(ISBLANK([Auto_Score]) && ISBLANK([Manual_Score]), "", '
    'IFBLANK([Auto_Score], 0) + IFBLANK([Manual_Score], 0))'
)

UPDATES = [
    ("Achievement_Rate", achievement_expr),
    ("Auto_Score", auto_expr),
    ("Final_Score", final_expr),
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

for name, expr in UPDATES:
    payload = json.dumps({"type": "formula", "name": name, "expression": expr}, ensure_ascii=False)
    try:
        r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", name,
                 "--json", payload, "--yes", "--i-have-read-guide"])
        print(f"{name}: ok={r.get('ok')}")
    except RuntimeError as exc:
        print(f"{name}: FAILED -> {exc}")
