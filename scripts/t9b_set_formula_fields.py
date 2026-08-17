#!/usr/bin/env python3
"""T9b: update/create Performance_Result formula fields (Achievement_Rate, Weight, Auto_Score, Final_Score)."""
import json, shutil, subprocess, sys
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result

# 1) Achievement_Rate: Actual_Value / Target_Value (达成率 = 实际/目标)
achievement_expr = (
    'IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])) || ISBLANK(FIRST([Target_ID].[Target_Value])), '
    'BLANK(), FIRST([Actual_ID].[Actual_Value]) / FIRST([Target_ID].[Target_Value]))'
)

# 2) Weight: lookup Metric.Weight
weight_expr = 'FIRST([Metric_ID].[Weight])'

# 3) Auto_Score: 按 Scoring_Type 分档（5 类模板）。参数来自辅助列快照。
#    达成率/进度型: IF(rate>=Rate_T1, IF(Score_T1=0, MIN(rate*100, Score_Cap), Score_T1), IF(rate>=Rate_T2, Score_T2, IF(rate>=Rate_T3, Score_T3, Score_Floor)))
#    次数阈值型: IF(count<=Rate_T1, Score_T1, IF(count<Rate_T2, Score_T2, Score_Floor))
#    扣分制: MAX(100 - count*Deduct_Per, Score_Floor)
#    定性等级型/奖惩制: BLANK（Auto_Score 留空，Manual_Score 人工）
auto_expr = (
    'SWITCH(FIRST([Metric_ID].[Scoring_Type]), '
    '"达成率/进度型", IF(ISBLANK([Achievement_Rate]), BLANK(), '
    'IF([Achievement_Rate] >= [Rate_T1], IF([Score_T1] = 0, MIN([Achievement_Rate] * 100, [Score_Cap]), [Score_T1]), '
    'IF([Achievement_Rate] >= [Rate_T2], [Score_T2], IF([Achievement_Rate] >= [Rate_T3], [Score_T3], [Score_Floor])))), '
    '"次数阈值型", IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), BLANK(), '
    'IF(FIRST([Actual_ID].[Actual_Value]) <= [Rate_T1], [Score_T1], '
    'IF(FIRST([Actual_ID].[Actual_Value]) < [Rate_T2], [Score_T2], [Score_Floor]))), '
    '"扣分制", IF(ISBLANK(FIRST([Actual_ID].[Actual_Value])), BLANK(), '
    'MAX(100 - FIRST([Actual_ID].[Actual_Value]) * [Deduct_Per], [Score_Floor])), '
    'BLANK())'
)

# 4) Final_Score: Auto_Score + Manual_Score（双部分 D-009.3；都空则空）
final_expr = (
    'IF(ISBLANK([Auto_Score]) && ISBLANK([Manual_Score]), BLANK(), '
    'IFBLANK([Auto_Score], 0) + IFBLANK([Manual_Score], 0))'
)

# 5) Weighted_Score 辅助公式列：Weight * Final_Score（加权汇总中间量）
weighted_expr = 'IFBLANK([Weight], 0) * IFBLANK([Final_Score], 0)'

# 6) Monthly_Total: 同员工+期间 的 Weighted_Score 之和（岗位月度总分）
monthly_expr = (
    'SUM([Performance_Result].FILTER(CurrentValue.[Employee_ID] = [Employee_ID] && CurrentValue.[Period] = [Period]).'
    '[Weighted_Score].LISTCOMBINE())'
)

# 7) Commission_Tier_Level: 按总分对照 Commission_Tier 取档（D-009.5 超上限按最高档兜底由 SORTBY desc + FIRST 天然实现）
tier_expr = (
    'FIRST([Commission_Tier].FILTER('
    'CurrentValue.[Position_ID] = FIRST([Metric_ID].[Position_ID]) && '
    'CurrentValue.[Score_Lower] <= [Monthly_Total] && '
    'CurrentValue.[Status] = "Active"'
    ').SORTBY([Commission_Tier].[Tier_Level], FALSE).[Tier_Level])'
)

UPDATES = [
    {"field": "Achievement_Rate", "json": {"type": "formula", "name": "Achievement_Rate", "expression": achievement_expr}},
    {"field": "Weight", "json": {"type": "formula", "name": "Weight", "expression": weight_expr}},
    {"field": "Auto_Score", "json": {"type": "formula", "name": "Auto_Score", "expression": auto_expr}},
    {"field": "Final_Score", "json": {"type": "formula", "name": "Final_Score", "expression": final_expr}},
]
CREATES = [
    {"type": "formula", "name": "Weighted_Score", "expression": weighted_expr,
     "description": "辅助公式列 · Weight×Final_Score，供加权汇总"},
    {"type": "formula", "name": "Monthly_Total", "expression": monthly_expr,
     "description": "岗位月度总分 · 同员工+期间 Weighted_Score 之和（加权汇总）"},
    {"type": "formula", "name": "Commission_Tier_Level", "expression": tier_expr,
     "description": "提成梯度匹配 · 按 Monthly_Total 对照 Commission_Tier 取档（D-009.5 超上限按最高档兜底）"},
]

def main():
    results = []
    for u in UPDATES:
        r = cli(["+field-update", "--base-token", BASE, "--table-id", TABLE, "--field-id", u["field"],
                 "--json", json.dumps(u["json"], ensure_ascii=False), "--yes", "--i-have-read-guide"])
        results.append({"op": "update", "field": u["field"], "ok": r.get("ok"), "type": r["data"]["field"].get("type")})
    for c in CREATES:
        r = cli(["+field-create", "--base-token", BASE, "--table-id", TABLE,
                 "--json", json.dumps(c, ensure_ascii=False), "--i-have-read-guide"])
        created = r["data"].get("field", {})
        results.append({"op": "create", "field": c["name"], "ok": r.get("ok"), "type": created.get("type")})
    print(json.dumps({"status": "FORMULA_FIELDS_SET", "results": results}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
