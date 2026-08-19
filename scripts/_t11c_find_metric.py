#!/usr/bin/env python3
"""T11c helper: find Performance_Result rows linked to ACT000056 (EDIT-003) or by metric."""
import json, sys

path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
for r in rows:
    # snapshot lacks Actual_ID; find by Result_ID range around EDIT-003 metric (metric recvsgqAO9sss4)
    pass
# alternative: dump rows whose Metric_ID == target metric record id
target_metric = sys.argv[2] if len(sys.argv) > 2 else "recvsgqAO9sss4"
for r in rows:
    ml = r.get("Metric_ID")
    if ml and ml[0]["id"] == target_metric:
        print(json.dumps(r, ensure_ascii=False))
