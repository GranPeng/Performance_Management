#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T17b 验证：D-016 编导双口径 + D-017 摄影师边界 + D-017.1 广告投放提成的数字示例"""
import sys

fails = []

def check(name, got, exp):
    ok = abs(got - exp) < 1e-9 if isinstance(exp, (int, float)) else got == exp
    print(f"[{'OK' if ok else 'FAIL'}] {name}: 计算={got} 预期={exp}")
    if not ok:
        fails.append(name)

# ---- D-016 编导打分（总消耗口径，G8 公式）----
project_total = 900_000      # 项目组总消耗（含近90天成片 60万 + 历史素材 30万）
budget_target = 1_000_000    # 项目预算目标消耗值
achieve = project_total / budget_target   # 90/100 = 0.9
check("编导打分达成率（总消耗口径）", achieve, 0.9)
# 评分标准：≤80%→0；80%<x≤100%→90；≥100%→按实际封顶1.5
def dir_score(x):
    if x <= 0.8: return 0
    if x <= 1.0: return 90
    return round(x * 100, 2)
check("编导打分得分", dir_score(achieve), 90)

# 旧 F8 近90天成片口径对照（已作废）：60万/100万=60%
old_f8 = 600_000 / budget_target
check("旧F8近90天成片口径达成率（已作废对照）", old_f8, 0.6)
print("   - 历史素材占比 =", f"{300000/900000:.0%}", "（若按旧口径将拉低达成率，D-016 作废）")

# ---- D-016 编导提成（个人口径）----
personal_90d = 400_000       # 个人近90天成片消耗
dir_tier3_ratio = 0.003      # 档3 [80,100)
commission = personal_90d * dir_tier3_ratio
check("编导提成（个人近90天成片×档位比例）", commission, 1200)
historical = 100_000
print(f"   - 个人历史素材消耗 {historical/10000:.0f} 万不计提成（历史素材不提成）")

# ---- D-017 摄影师评分边界 ----
def cam_score(rate):
    return 0 if rate < 1.0 else 100
check("摄影师 10/10=100% → 100分", cam_score(10/10), 100)
check("摄影师 9/10=90% <100% → 0分", cam_score(9/10), 0)

# ---- D-017.1 广告投放提成（投放账户广告消耗，4档0.001）----
ads_consume = 156_000
check("广告投放提成（投放账户广告消耗×0.001）", ads_consume * 0.001, 156)

# 4 档全 0.001（V04 原文 I17:M20）
tiers = [0.001, 0.001, 0.001, 0.001]
check("广告投放 4 档比例全为 0.001", len(set(tiers)), 1)
print(f"   - 4 档比例: {tiers}")

print()
if fails:
    print("FAILED:", fails)
    sys.exit(1)
print("T17b D-016/D-017 数字示例验证: PASS")
