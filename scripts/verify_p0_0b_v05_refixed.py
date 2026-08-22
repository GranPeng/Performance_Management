#!/usr/bin/env python3
"""P0-0b 实测核对：修复后 V05 提取结果与 D-032 两项一致性检查。
1) 提成比例与绩效工资核算规则 sheet F32:F45（源行 32-45）提成比例基数全部 = 0.003
2) 新规则 sheet 第 15 行 = 编导爆款激励行（爆款定义/激励金额，覆盖编导）
只读核对，不写任何文件。
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "data/output/绩效框架结构化规则_V05.json").read_text(encoding="utf-8"))
rows = d["rule_sheets"]["提成比例与绩效工资核算规则"]["rows"]

print("source sha256:", d["source"]["sha256"])
print("规则 sheet 数据行数:", len(rows))
print()

# 检查1: F32:F45 基数=0.003
bad = [(r["source_row"], r["岗位"], r["提成比例基数"]) for r in rows
       if 32 <= r["source_row"] <= 45 and r["提成比例基数"] != 0.003]
c1 = not bad
print("[检查1] F32:F45 基数=0.003:", "PASS" if c1 else f"FAIL {bad}")

# 全文不得再有 0.03 基数
b30 = [(r["source_row"], r["岗位"]) for r in rows if r["提成比例基数"] == 0.03]
print("        全表基数=0.03 残留:", b30 if b30 else "无")
print("        全表基数取值集合:", sorted({r["提成比例基数"] for r in rows if r["提成比例基数"] is not None}))
print()

# 检查2: 第 15 行编导爆款激励
r15 = next((r for r in rows if r["source_row"] == 15), None)
print("[检查2] 源行15:", json.dumps(r15, ensure_ascii=False))
ok15 = r15 is not None and "编导" in str(r15.get("岗位") or "") and (
    "爆款" in str(r15.get("提成来源") or "") or "爆款" in str(r15.get("特殊项说明") or "")
    or "1500" in str(r15.get("特殊项说明") or "") or "50万" in str(r15.get("特殊项说明") or ""))
print("        编导爆款激励行存在:", "PASS" if ok15 else "FAIL")
print()

# 爆款相关行全量（供报告引用）
print("爆款相关行全量:")
for r in rows:
    blob = json.dumps(r, ensure_ascii=False)
    if "爆款" in blob or "1500" in blob:
        print(" ", r["source_row"], "|", r["岗位"], "|", r["提成来源"], "|", r["特殊项说明"])
print()

# 与旧版（b1c380f3 备份）行数对比
bak = ROOT / "data/output/绩效框架结构化规则_V05.json.bak-b1c380f3"
if bak.exists():
    old = json.loads(bak.read_text(encoding="utf-8"))
    orows = old["rule_sheets"]["提成比例与绩效工资核算规则"]["rows"]
    print("旧版(b1c380f3)规则 sheet 行数:", len(orows), "→ 新版:", len(rows), "（差异仅限新增编导爆款行则应为 +1）")
    old15 = next((r for r in orows if r["source_row"] == 15), None)
    print("旧版源行15:", json.dumps(old15, ensure_ascii=False))

sys.exit(0 if (c1 and ok15 and not b30) else 1)
