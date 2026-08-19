#!/usr/bin/env python3
"""T11c helper: verify Commission_Ratio matches tier table rule per business_rules.md §3.

For each row with Monthly_Total + position:
  find tier with highest Score_Lower <= Monthly_Total (Status=Active)
  运营族 (has Coefficient): expected_ratio = Commission_Tier.Base_Rate × Coefficient
  其他族: expected_ratio = Ratio_Value
Compare with stored Commission_Ratio.
"""
import argparse, json, sys
from collections import defaultdict

base = "FCxObLU6yao5jgsciZfcWHKwnjh"
import shutil, subprocess, time
from pathlib import Path
from base_rate_config import resolve_base_rate

parser = argparse.ArgumentParser(description="提成比例只读复核；--base-rate 仅覆盖预期值，不写入 Base。")
parser.add_argument("result_json", help="待复核的 Performance_Result JSON 文件")
parser.add_argument("--base-rate", type=float, help="只读验证用 Base_Rate 覆盖值")
args = parser.parse_args()

CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=5):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last

# pull tier table fresh
tier_rows = []
offset = 0
while True:
    d = cli(["+record-list", "--base-token", base, "--table-id", "tblkZUoHYwBIvDYe", "--limit", "200", "--format", "json"]
            + [a for f in ["Commission_Tier_ID", "Position_ID", "Score_Lower", "Coefficient", "Ratio_Value", "Base_Rate", "Status"] for a in ("--field-id", f)]
            + (["--offset", str(offset)] if offset else []))
    names = d["fields"]; ids = d["record_id_list"]
    for rid, vals in zip(ids, d["data"]):
        row = dict(zip(names, vals)); row["_rid"] = rid; tier_rows.append(row)
    if not d.get("has_more"):
        break
    offset += len(ids)

# position record id -> text
pos_rows = []
offset = 0
while True:
    d = cli(["+record-list", "--base-token", base, "--table-id", "tbldzvsg9Op6pK29", "--limit", "200", "--format", "json"]
            + [a for f in ["Position_ID"] for a in ("--field-id", f)]
            + (["--offset", str(offset)] if offset else []))
    names = d["fields"]; ids = d["record_id_list"]
    for rid, vals in zip(ids, d["data"]):
        row = dict(zip(names, vals)); row["_rid"] = rid; pos_rows.append(row)
    if not d.get("has_more"):
        break
    offset += len(ids)
pos_text = {r["_rid"]: r.get("Position_ID") for r in pos_rows}

# metric record id -> position text
metric_rows = []
offset = 0
while True:
    d = cli(["+record-list", "--base-token", base, "--table-id", "tbldKtdIVv8nnTyX", "--limit", "200", "--format", "json"]
            + [a for f in ["Metric_ID", "Position_ID"] for a in ("--field-id", f)]
            + (["--offset", str(offset)] if offset else []))
    names = d["fields"]; ids = d["record_id_list"]
    for rid, vals in zip(ids, d["data"]):
        row = dict(zip(names, vals)); row["_rid"] = rid; metric_rows.append(row)
    if not d.get("has_more"):
        break
    offset += len(ids)
metric_pos_text = {}
for m in metric_rows:
    pl = m.get("Position_ID")
    if pl:
        metric_pos_text[m["_rid"]] = pos_text.get(pl[0]["id"])

rows = json.load(open(args.result_json, encoding="utf-8"))
checked = 0
fails = []
for r in rows:
    mt = r.get("Monthly_Total")
    if mt in (None, ""):
        continue
    ml = r.get("Metric_ID")
    if not ml:
        continue
    pos = metric_pos_text.get(ml[0]["id"])
    if not pos:
        continue
    mtf = float(mt)
    # tier match by position text -> need tier rows with position record id
    tiers = []
    for t in tier_rows:
        pl = t.get("Position_ID")
        if pl and pos_text.get(pl[0]["id"]) == pos and t.get("Status") == "Active":
            tiers.append(t)
    matched = None
    for t in tiers:
        low = t.get("Score_Lower")
        if low is not None and float(low) <= mtf:
            if matched is None or float(t["Score_Lower"]) > float(matched["Score_Lower"]):
                matched = t
    if matched is None:
        # no tier matched; stored ratio should be blank
        if r.get("Commission_Ratio") not in (None, ""):
            fails.append({"Result_ID": r["Result_ID"], "issue": "expected blank ratio", "ratio": r.get("Commission_Ratio"), "pos": pos, "mt": mt})
        continue
    coef = matched.get("Coefficient")
    rv = matched.get("Ratio_Value")
    if coef is not None:
        exp = round(resolve_base_rate(tier_rows, matched["Position_ID"][0]["id"], args.base_rate) * float(coef), 6)
    elif rv is not None:
        exp = float(rv)
    else:
        exp = None
    if exp is None:
        continue
    got = r.get("Commission_Ratio")
    if got in (None, ""):
        fails.append({"Result_ID": r["Result_ID"], "issue": "expected ratio but blank", "pos": pos, "mt": mt, "exp": exp, "tier": matched.get("Commission_Tier_ID")})
        continue
    checked += 1
    if abs(float(got) - exp) > 1e-9:
        fails.append({"Result_ID": r["Result_ID"], "issue": "ratio mismatch", "exp": exp, "got": got, "pos": pos, "mt": mt, "tier": matched.get("Commission_Tier_ID")})
print(f"ratio checked {checked} rows")
if fails:
    print("FAILS:", len(fails))
    for f in fails[:20]:
        print(json.dumps(f, ensure_ascii=False))
    sys.exit(1)
else:
    print("ALL COMMISSION_RATIO MANUAL RECHECK PASSED")
