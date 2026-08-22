#!/usr/bin/env python3
"""打印 V05/V04 差异明细（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "data/output/V05与V04差异明细.json").read_text(encoding="utf-8"))
for x in d["diffs"]:
    print("=" * 70)
    print(x["sheet"], "|", x["kpi"], "|", x["field"], "|", x["kind"], "|", x["severity"])
    print("V04:", json.dumps(x["v04"], ensure_ascii=False)[:800])
    print("V05:", json.dumps(x["v05"], ensure_ascii=False)[:800])
