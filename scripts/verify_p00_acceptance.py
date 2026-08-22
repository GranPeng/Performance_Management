#!/usr/bin/env python3
"""完工验收：V05 产物可解析、计数一致、V04 基线未被修改（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "data/output/绩效框架结构化规则_V05.json").read_text(encoding="utf-8"))
print("V05 positions:", len(d["positions"]), "metrics:", sum(len(p["metrics"]) for p in d["positions"]))
print("V05 rule_sheets:", {k: len(v["rows"]) for k, v in d["rule_sheets"].items()})
e = json.loads((ROOT / "data/output/V05与V04差异明细.json").read_text(encoding="utf-8"))
print("diff conclusions:", len(e["kpi_conclusions"]), "diff entries:", len(e["diffs"]))
concl = {}
for c in e["kpi_conclusions"]:
    concl[c["conclusion"]] = concl.get(c["conclusion"], 0) + 1
print("conclusion dist:", concl)
v4 = json.loads((ROOT / "data/output/绩效框架结构化规则.json").read_text(encoding="utf-8"))
print("V04 baseline metrics:", sum(len(p["metrics"]) for p in v4["positions"]),
      "sha256:", v4["source"]["sha256"])
assert v4["source"]["sha256"] == "5342d3dda5097460cba2f4d6e2cb0628c2fbf6e22a5e111cc91369e1a4953250"
assert len(e["kpi_conclusions"]) == 45
assert len(d["positions"]) == 9 and len(d["rule_sheets"]) == 2
print("ACCEPTANCE OK")
