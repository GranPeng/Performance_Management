#!/usr/bin/env python3
"""只读查看 Commission_Tier T6 建库快照（现库配置基线），供 V05 映射核对。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "data/output/t6_payloads/commission_tier_batch_create.json").read_text(encoding="utf-8"))
recs = d["create_records"]
print("total:", len(recs))
for r in recs:
    print(json.dumps({k: r.get(k) for k in [
        "Commission_Tier_ID", "Position_ID", "Source_Sheet", "Source_Cell",
        "Score_Lower", "Score_Upper", "Upper_Is_Open", "Coefficient",
        "Ratio_Value", "Ratio_Text", "Base_Rate", "Status", "Rule_Version"
    ] if k in r}, ensure_ascii=False))
