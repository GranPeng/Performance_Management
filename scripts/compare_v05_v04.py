#!/usr/bin/env python3
"""V05 vs V04 逐 KPI 比对，产出结构化差异明细（只读两份 JSON，结果写新文件）。"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V04 = json.loads((ROOT / "data/output/绩效框架结构化规则.json").read_text(encoding="utf-8"))
V05 = json.loads((ROOT / "data/output/绩效框架结构化规则_V05.json").read_text(encoding="utf-8"))

# 字段 → 变更类别（业务含义）
FIELD_KIND = {
    "weight": "权重变更",
    "calculation_formula": "公式变更",
    "scoring_standard": "档位/评分标准变更",
    "dimension": "枚举变更-评价维度",
    "data_source": "枚举变更-数据来源",
    "evaluation_period": "枚举变更-评价周期",
    "unit": "枚举变更-单位",
    "name": "指标名称变更",
    "target": "文本表述-目标",
    "reward_condition": "档位/奖惩条件变更",
    "penalty_condition": "档位/处罚条件变更",
    "scoring_type": "评分类型重分类（技术字段）",
    "source_result_example": "示例数据（非规则事实）",
    "source_score_formula": "源得分公式",
}
# 影响引擎行为的字段（P0）；其余为文本表述（P3）
P0_FIELDS = {"weight", "calculation_formula", "scoring_standard", "reward_condition", "penalty_condition",
             "dimension", "data_source", "evaluation_period", "unit", "name"}

def norm(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.replace("\r\n", "\n").strip()
    return v

diffs = []          # 每项：sheet, kpi_key, field, kind, v04, v05, severity
kpi_conclusions = {}  # (sheet, number, name) -> 同/异/删/增

v04_pos = {p["source_sheet"]: p for p in V04["positions"]}
v05_pos = {p["source_sheet"]: p for p in V05["positions"]}

sheets_removed = sorted(set(v04_pos) - set(v05_pos))
sheets_added = sorted(set(v05_pos) - set(v04_pos))

for sheet in sorted(set(v04_pos) & set(v05_pos)):
    p4, p5 = v04_pos[sheet], v05_pos[sheet]
    # 岗位级公式
    for f, label in [("weight_total_formula", "权重合计公式"), ("total_score_formula", "最终得分合计公式")]:
        if norm(p4.get(f)) != norm(p5.get(f)):
            diffs.append({"sheet": sheet, "kpi": "(岗位级)", "field": f, "kind": "公式变更",
                          "v04": p4.get(f), "v05": p5.get(f), "severity": "P0"})
    m4 = {(str(m["source_metric_number"]), m["name"]): m for m in p4["metrics"]}
    m5 = {(str(m["source_metric_number"]), m["name"]): m for m in p5["metrics"]}
    # 编号可能相同但名称变更——先按编号对一遍找改名
    n4 = {str(m["source_metric_number"]): m for m in p4["metrics"]}
    n5 = {str(m["source_metric_number"]): m for m in p5["metrics"]}
    paired = {}  # v05 key -> v04 metric
    used4 = set()
    for k5, met5 in m5.items():
        num5 = k5[0]
        if k5 in m4:
            paired[k5] = m4[k5]; used4.add(k5)
        elif num5 in n4 and (num5, n4[num5]["name"]) not in used4:
            paired[k5] = n4[num5]; used4.add((num5, n4[num5]["name"]))
    for k5, met5 in m5.items():
        key5 = (sheet,) + k5
        if k5 not in paired:
            kpi_conclusions[key5] = "增"
            diffs.append({"sheet": sheet, "kpi": f"{k5[0]}:{k5[1]}", "field": "(整项)", "kind": "新增",
                          "v04": None, "v05": "整项新增", "severity": "P0"})
            continue
        met4 = paired[k5]
        changed = []
        for f in ["name", "dimension", "weight", "target", "calculation_formula", "unit",
                  "scoring_standard", "reward_condition", "penalty_condition",
                  "data_source", "evaluation_period", "scoring_type",
                  "source_result_example", "source_score_formula"]:
            v4v, v5v = norm(met4.get(f)), norm(met5.get(f))
            if v4v != v5v:
                kind = FIELD_KIND[f]
                sev = "P0" if f in P0_FIELDS else "P3"
                changed.append(f)
                diffs.append({"sheet": sheet, "kpi": f"{k5[0]}:{k5[1]}", "field": f, "kind": kind,
                              "v04": met4.get(f), "v05": met5.get(f), "severity": sev})
        kpi_conclusions[key5] = "异" if changed else "同"
    for k4, met4 in m4.items():
        if k4 not in used4:
            kpi_conclusions[(sheet,) + k4] = "删"
            diffs.append({"sheet": sheet, "kpi": f"{k4[0]}:{k4[1]}", "field": "(整项)", "kind": "删除",
                          "v04": "整项删除", "v05": None, "severity": "P0"})
    # 提成梯度比对（岗位 sheet 内嵌表）
    c4 = p4.get("commission_rules") or []
    c5 = p5.get("commission_rules") or []
    t4 = [json.dumps(t["values"], ensure_ascii=False, sort_keys=True) for cr in c4 for t in cr["tiers"]]
    t5 = [json.dumps(t["values"], ensure_ascii=False, sort_keys=True) for cr in c5 for t in cr["tiers"]]
    if t4 != t5:
        diffs.append({"sheet": sheet, "kpi": "(岗位提成梯度)", "field": "commission_rules", "kind": "档位变更-提成梯度",
                      "v04": t4, "v05": t5, "severity": "P0"})
    # 特殊规则比对
    s4 = json.dumps(p4.get("special_rules"), ensure_ascii=False, sort_keys=True)
    s5 = json.dumps(p5.get("special_rules"), ensure_ascii=False, sort_keys=True)
    if s4 != s5:
        diffs.append({"sheet": sheet, "kpi": "(特殊/补充规则)", "field": "special_rules", "kind": "特殊规则变更",
                      "v04": p4.get("special_rules"), "v05": p5.get("special_rules"), "severity": "P0"})

summary = {
    "v04_metric_count": sum(len(p["metrics"]) for p in V04["positions"]),
    "v05_metric_count": sum(len(p["metrics"]) for p in V05["positions"]),
    "sheets_added": sheets_added, "sheets_removed": sheets_removed,
    "kpi_same": sum(1 for v in kpi_conclusions.values() if v == "同"),
    "kpi_changed": sum(1 for v in kpi_conclusions.values() if v == "异"),
    "kpi_deleted": sum(1 for v in kpi_conclusions.values() if v == "删"),
    "kpi_added": sum(1 for v in kpi_conclusions.values() if v == "增"),
    "diff_entries": len(diffs),
    "p0_entries": sum(1 for d in diffs if d["severity"] == "P0"),
    "p3_entries": sum(1 for d in diffs if d["severity"] == "P3"),
}

out = {"summary": summary,
       "kpi_conclusions": [{"sheet": k[0], "number": k[1], "name": k[2], "conclusion": v}
                            for k, v in sorted(kpi_conclusions.items())],
       "diffs": diffs}
(ROOT / "data/output/V05与V04差异明细.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
