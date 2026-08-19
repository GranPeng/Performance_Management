#!/usr/bin/env python3
"""T15b 无副作用配置读取单测：验证基数改为0.004时无需改公式/脚本即可产出新比例。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from t11c_generate_results import compute_commission_snapshots

result_rows = [{"_record_id": "r1", "Employee_ID": [{"id": "emp1"}], "Metric_ID": [{"id": "met1"}], "Monthly_Total": 95}]
metric_records = [{"_record_id": "met1", "Position_ID": [{"id": "posrec1"}]}]
tier_rows = [{"Commission_Tier_ID": "CT-TEST", "Position_ID": [{"id": "posrec1"}], "Status": "Active", "Score_Lower": 90, "Coefficient": 0.6, "Ratio_Value": None, "Base_Rate": 0.004}]
result = compute_commission_snapshots(result_rows, {"met1": "POS000013"}, {}, metric_records, [], tier_rows)
actual = result["r1"]["Commission_Ratio"]
assert actual == 0.0024, actual
print({"status": "PASS", "base_rate": 0.004, "coefficient": 0.6, "commission_ratio": actual, "formula_change": False})
