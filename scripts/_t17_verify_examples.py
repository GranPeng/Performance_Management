#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T17 落文数字示例验证（只读，无副作用）"""
results = []

# 1. 直播中控（D-013）
part1 = 5000 * 1.00
part2 = 3_000_000 * 0.001 / 3
total = part1 + part2
results.append(("直播中控收入", [part1, part2, total], [5000, 1000, 6000]))

# 2. GSV 分摊（D-014）
sup_comm = 2_800_000 * (0.003 * 0.8)
op_comm = 2_000_000 * (0.003 * 0.6)
results.append(("高级主管提成", [sup_comm], 6720))
results.append(("运营提成", [op_comm], 3600))

# 3. 制作部-视频剪辑
per_capita = 1_000_000 / 5
threshold = per_capita * 0.9
rate = 160_000 / threshold
score = 0 if rate <= 0.8 else (90 if rate <= 1.0 else None)
edit_comm = 160_000 * 0.003
results.append(("剪辑人均门槛", [per_capita, threshold], [200000, 180000]))
results.append(("剪辑个人贡献率", [rate], 16/18))
results.append(("剪辑评分", [score], 90))
results.append(("剪辑提成", [edit_comm], 480))

# 4. 编导达成率
results.append(("编导达成率", [900_000 / 1_000_000], 0.9))

# 5. 摄影师达成率
results.append(("摄影师达成率", [10 / 10], 1.0))

# 6. 广告投放提成
results.append(("广告投放提成", [156_000 * 0.001], 156))

ok = True
for name, vals, expect in results:
    if isinstance(expect, list):
        match = all(abs(a - b) < 1e-9 for a, b in zip(vals, expect))
    else:
        match = all(abs(v - expect) < 1e-9 for v in vals)
    if not match:
        ok = False
    print(f"[{'OK' if match else 'MISMATCH'}] {name}: 计算={vals} 预期={expect}")

print("\n全部数字示例验证:", "PASS" if ok else "FAIL")
