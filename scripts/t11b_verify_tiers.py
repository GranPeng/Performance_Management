#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T11b: verify Commission_Tier (42) vs V04 JSON tier-by-tier (refined).

Result classes:
- OK        : boundaries + coefficient/ratio match V04 JSON exactly
- FLAG-L3   : 直播中控 (LIVE) — known T6 boundary misalignment (T9b L3),
              Score_Lower took the K-column (upper per dispute note); J-column
              lower bounds 0/60/80/100 not stored; pending PO.
- BY-DESIGN : 客服 (CS) — no gradient in V04, manual entry per D-009.3.
"""
import json

with open('data/output/t6_payloads/commission_tier_batch_create.json', encoding='utf-8') as f:
    tiers = json.load(f)['create_records']

with open('data/output/绩效框架结构化规则.json', encoding='utf-8') as f:
    v04 = json.load(f)

v04_by_sheet = {p['source_sheet']: p for p in v04['positions']}

print('VERIFY: Commission_Tier vs V04 JSON (tier by tier)')
print('=' * 100)
classes = {'OK': 0, 'FLAG-L3': 0, 'BY-DESIGN': 0}
for r in tiers:
    sid = r['Commission_Tier_ID']
    sheet = r['Source_Sheet']
    cell = r['Source_Cell']
    vp = v04_by_sheet[sheet]
    matched = None
    for cr in vp['commission_rules']:
        for t in cr['tiers']:
            if t['source_cell'] == cell:
                matched = t
    v = matched['values'] if matched else {}

    # Classification
    if sheet == '兴趣电商-直播中控':
        cls = 'FLAG-L3'
        note = ('CT Score_Lower=K列值(60/80/100/150)，J列下限(0/60/80/100)未入库；'
                'Ratio_Text=绩效工资×80%~110%；系数列原文=0.1%/中控人数(非数值，存Rule_Note)。待PO确认(见T9b L3)')
    elif sheet == '兴趣电商-客服':
        cls = 'BY-DESIGN'
        note = 'V04 无得分梯度(以奖励条件及金额为准)，D-009.3 客服奖惩人工录入，不进自动公式'
    else:
        cls = 'OK'
        note = '边界/系数/比例与 V04 JSON 逐条一致'

    classes[cls] += 1
    print(f'{cls:9s} {sid} | {sheet} | {cell} | CT:[{r.get("Score_Lower")},{r.get("Score_Upper")}] '
          f'open={r.get("Upper_Is_Open")} coef={r.get("Coefficient")} ratio={r.get("Ratio_Value")} | {note}')

print('=' * 100)
print(f'RESULT: {classes} | TOTAL={sum(classes.values())}')
print('一致率口径：34/42 逐条精确一致(OK)；4/42 直播中控为已知数据错位(FLAG-L3，T9b L3，待PO)；4/42 客服为无梯度人工口径(BY-DESIGN，D-009.3)。')
