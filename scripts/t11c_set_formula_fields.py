#!/usr/bin/env python3
"""T11c: land Base formula changes for exemption branch (Q-10-01) and Commission_Amount (Q-10-02).

Changes:
- Auto_Score: prepend exemption branch — IF(Is_Exempt=TRUE(), 100, <original>)  (Q-10-01 得分=100)
- Weighted_Score: exemption rows weighted 0 — IF(Is_Exempt=TRUE(), 0, Weight×Final_Score)
  (Q-10-01 不纳入月度加权; Monthly_Total=SUM(Weighted_Score) 因此自动排除豁免行)
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

# 豁免分支：Is_Exempt=TRUE() → 100；否则原逻辑
AUTO_EXEMPT = f'IF([Is_Exempt]=TRUE(),100,{ORIG_AUTO})'

# Weighted_Score：豁免行 0（不参与月度加权），否则 Weight×Final_Score
WEIGHTED_EXEMPT = 'IF([Is_Exempt]=TRUE(),0,IFBLANK([Weight],0)*IFBLANK([Final_Score],0))'

# Commission_Amount：公式 = Base × Ratio；任一为空则留空
AMOUNT_EXPR = 'IF(ISBLANK([Commission_Base])||ISBLANK([Commission_Ratio]),"",[Commission_Base]*[Commission_Ratio])'

def main():
    results = []
    # 1) Auto_Score: update with exemption branch
    r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", "fld8Pmyvpb",
             "--json", json.dumps({"type": "formula", "name": "Auto_Score", "expression": AUTO_EXEMPT}, ensure_ascii=False),
             "--yes", "--i-have-read-guide"])
    results.append({"op": "update", "field": "Auto_Score", "ok": r.get("ok")})
    # 2) Weighted_Score: exemption rows weighted 0
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
