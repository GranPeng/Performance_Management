#!/usr/bin/env python3
"""T9b: update Achievement_Rate formula to branch on Target_ID blankness."""
import json, shutil, subprocess
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

achievement_expr = (
    'IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), "", '
    'IFERROR(FIRST([Actual_ID].[Actual_Value]) / '
    'IF(ISBLANK([Target_ID]), [Target_Value_Snapshot], FIRST([Target_ID].[Target_Value])), ""))'
)

def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result

payload = json.dumps({"type": "formula", "name": "Achievement_Rate", "expression": achievement_expr}, ensure_ascii=False)
r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", "Achievement_Rate",
         "--json", payload, "--yes", "--i-have-read-guide"])
print(f"Achievement_Rate update ok={r.get('ok')}")
