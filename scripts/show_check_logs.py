#!/usr/bin/env python3
"""打印 V04/V05 提取校验日志的逐 sheet 计数证据（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for tag, p in [("V04", "data/output/绩效框架提取校验日志.json"), ("V05", "data/output/绩效框架提取校验日志_V05.json")]:
    d = json.loads((ROOT / p).read_text(encoding="utf-8"))
    print(tag, "sha256:", d["source_sha256"], "metric_count:", d["metric_count"])
    for c in d["checks"]:
        print("  ", c["sheet"], "KPI=", c["metric_count"], "合计行=", c["source_total_row"],
              "权重公式=", c["weight_total_formula"], "得分公式=", c["total_score_formula"])
    if "rule_sheet_checks" in d:
        for c in d["rule_sheet_checks"]:
            print("  ", c["sheet"], "数据行=", c["row_count"], "备注=", c.get("note_count"))
