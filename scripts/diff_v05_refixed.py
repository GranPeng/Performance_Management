#!/usr/bin/env python3
"""只读对比：修复前(b1c380f3 备份) vs 修复后(8b6ea457) 的 V05 规则 sheet 逐行差异。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
new = json.loads((ROOT / "data/output/绩效框架结构化规则_V05.json").read_text(encoding="utf-8"))
old = json.loads((ROOT / "data/output/绩效框架结构化规则_V05.json.bak-b1c380f3").read_text(encoding="utf-8"))

def snap(d):
    return {r["source_row"]: r for r in d["rule_sheets"]["提成比例与绩效工资核算规则"]["rows"]}

O, N = snap(old), snap(new)
cols = ["岗位","提成来源","提成规则","绩效得分下限_包含","绩效得分上限_不包含","提成比例基数","对应提成比例系数","提成比例","对应绩效工资核算公式","特殊项说明"]

print("=== 提成比例与绩效工资核算规则：修复前 vs 修复后 ===")
for r in sorted(set(O) | set(N)):
    o, n = O.get(r), N.get(r)
    if o is None:
        print(f"行{r}: [新增] {n['岗位']} | {n['提成来源']} | {n['特殊项说明']}")
    elif n is None:
        print(f"行{r}: [删除] {o['岗位']} | {o['提成来源']} | {o['特殊项说明']}")
    else:
        diffs = [c for c in cols if o.get(c) != n.get(c)]
        if diffs:
            print(f"行{r}: [变更] 字段={diffs}")
            for c in diffs:
                print(f"    {c}: {o.get(c)!r} -> {n.get(c)!r}")
        else:
            print(f"行{r}: 同 ({n['岗位']}|{n['提成来源']}|基数={n['提成比例基数']}|系数={n['对应提成比例系数']})")

print()
print("=== 绩效豁免规则 sheet：修复前 vs 修复后 ===")
oe = old["rule_sheets"]["绩效豁免规则"]
ne = new["rule_sheets"]["绩效豁免规则"]
print("行数:", len(oe["rows"]), "->", len(ne["rows"]), "; 星注:", len(oe["source_notes"]), "->", len(ne["source_notes"]))
print("内容一致:", json.dumps(oe, ensure_ascii=False, sort_keys=True) == json.dumps(ne, ensure_ascii=False, sort_keys=True))

print()
print("=== 45 项 KPI 是否有变化 ===")
ok = True
for op, np_ in zip(old["positions"], new["positions"]):
    om = json.dumps(op["metrics"], ensure_ascii=False, sort_keys=True)
    nm = json.dumps(np_["metrics"], ensure_ascii=False, sort_keys=True)
    if om != nm:
        ok = False
        print("KPI 变化:", op["source_sheet"])
print("45 项 KPI 全部一致:", ok)
print("岗位 sheet 内 commission_rules 残留（修复后应全空）:",
      {p["source_sheet"]: len(p["commission_rules"]) for p in new["positions"] if p["commission_rules"]})
print("special_rules 残留（修复后）:",
      {p["source_sheet"]: len(p["special_rules"]["assessment_methods"]) for p in new["positions"] if p["special_rules"]["assessment_methods"]})
