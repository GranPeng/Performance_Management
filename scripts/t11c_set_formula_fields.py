#!/usr/bin/env python3
"""T11c/T14: land Base scoring and Commission_Amount formulas.

Changes:
- D-010-R1: Is_Exempt is a commission eligibility marker only. Auto_Score and
  Weighted_Score always calculate under the normal V04 scoring path.
- Commission_Amount: number storage -> formula = Commission_Base × Commission_Ratio (Q-10-02)
  (Base/Ratio 为脚本写快照；Amount 由公式产出，空值留空不伪造 0)
"""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=5):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result
    raise last

# Original Auto_Score expression (current live value, verified via +table-get)
ORIG_AUTO = (
    'SWITCH(FIRST([Metric_ID].[Scoring_Type]),'
    '"达成率/进度型",IF(ISBLANK([Achievement_Rate]),"",IF([Achievement_Rate]>=[Rate_T1],IF([Score_T1]=0,MIN([Achievement_Rate]*100,[Score_Cap]),[Score_T1]),IF([Achievement_Rate]>=[Rate_T2],[Score_T2],IF([Achievement_Rate]>=[Rate_T3],[Score_T3],[Score_Floor])))),'
    '"次数阈值型",IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])),"",IF(FIRST([Actual_ID].[Actual_Value])<=[Rate_T1],[Score_T1],IF(FIRST([Actual_ID].[Actual_Value])<[Rate_T2],[Score_T2],[Score_Floor]))),'
    '"扣分制",IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])),"",MAX(100-FIRST([Actual_ID].[Actual_Value])*[Deduct_Per],[Score_Floor])))'
)

# D-010-R1：豁免不改变绩效打分或加权，提成分支另行处理。
AUTO_EXEMPT = ORIG_AUTO
WEIGHTED_EXEMPT = 'IFBLANK([Weight],0)*IFBLANK([Final_Score],0)'

# Commission_Amount：公式 = Base × Ratio；任一为空则留空
AMOUNT_EXPR = 'IF(ISBLANK([Commission_Base])||ISBLANK([Commission_Ratio]),"",[Commission_Base]*[Commission_Ratio])'

def main():
    results = []
    # 1) Auto_Score: normal V04 scoring; D-010-R1 does not override the score.
    r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", "fld8Pmyvpb",
             "--json", json.dumps({"type": "formula", "name": "Auto_Score", "expression": AUTO_EXEMPT}, ensure_ascii=False),
             "--yes", "--i-have-read-guide"])
    results.append({"op": "update", "field": "Auto_Score", "ok": r.get("ok")})
    # 2) Weighted_Score: normal weighted score; D-010-R1 does not exclude it.
    r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", "fld1pK4z70",
             "--json", json.dumps({"type": "formula", "name": "Weighted_Score", "expression": WEIGHTED_EXEMPT}, ensure_ascii=False),
             "--yes", "--i-have-read-guide"])
    results.append({"op": "update", "field": "Weighted_Score", "ok": r.get("ok")})
    # 3) Commission_Amount: number -> formula
    r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", "fldmadr7wT",
             "--json", json.dumps({"type": "formula", "name": "Commission_Amount", "expression": AMOUNT_EXPR,
                                   "description": "提成金额（公式）· Commission_Base × Commission_Ratio；Base/Ratio 为脚本按 D-009 写入快照（T11c）。Q-10-02"}, ensure_ascii=False),
             "--yes", "--i-have-read-guide"])
    results.append({"op": "update", "field": "Commission_Amount", "ok": r.get("ok"), "type": r["data"]["field"].get("type")})
    print(json.dumps({"status": "FORMULA_FIELDS_SET", "results": results}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
