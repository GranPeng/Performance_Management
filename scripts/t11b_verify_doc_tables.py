#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T11b: verify business_rules.md coefficient tables match Commission_Tier payload (42 rows)."""
import json, re

DOC = 'docs/business_rules.md'

with open(DOC, encoding='utf-8') as f:
    text = f.read()

with open('data/output/t6_payloads/commission_tier_batch_create.json', encoding='utf-8') as f:
    tiers = json.load(f)['create_records']

# Build expected map: ID -> (lower, upper, open, coef, ratio)
exp = {}
for r in tiers:
    exp[r['Commission_Tier_ID']] = {
        'lower': r.get('Score_Lower'),
        'upper': r.get('Score_Upper'),
        'open': r.get('Upper_Is_Open'),
        'coef': r.get('Coefficient'),
        'ratio': r.get('Ratio_Value'),
        'sheet': r.get('Source_Sheet'),
        'cell': r.get('Source_Cell'),
    }

# Find all Commission_Tier_ID occurrences in the doc
ids_in_doc = re.findall(r'CT-V04-[A-Z0-9-]+', text)
from collections import Counter
cnt = Counter(ids_in_doc)
print('IDs in doc:', len(cnt), 'unique;', sum(cnt.values()), 'occurrences')
dups = {k: v for k, v in cnt.items() if v > 1}
print('duplicated IDs:', dups if dups else 'none')

# Check every expected ID appears
missing = [k for k in exp if k not in cnt]
print('missing IDs:', missing if missing else 'none')

# Check extras
extra = [k for k in cnt if k not in exp]
print('extra IDs (non-CT):', extra if extra else 'none')

# Row-level numeric check: for each ID, find its table row in doc and compare
# Extract table rows containing the ID
rows = {}
for line in text.splitlines():
    line = line.strip()
    if not line.startswith('|'):
        continue
    m = re.search(r'(CT-V04-[A-Z0-9-]+)', line)
    if not m:
        continue
    cid = m.group(1)
    cells = [c.strip() for c in line.strip('|').split('|')]
    rows.setdefault(cid, []).append(cells)

print()
print('Row-level check (compare doc numbers vs Commission_Tier payload):')
problems = 0
for cid in sorted(exp.keys()):
    if cid not in rows:
        print(f'  MISSING ROW: {cid}')
        problems += 1
        continue
    # take first row for this id (should be unique)
    cells = rows[cid][0]
    rowtext = ' | '.join(cells)
    e = exp[cid]
    # Find numbers in the row
    def has_val(val):
        if val is None:
            return True  # absence of numeric expected -> check text does not contain as standalone number where it matters
        return str(val) in rowtext
    ok = True
    notes = []
    if e['lower'] is not None and str(e['lower']) not in rowtext:
        ok = False; notes.append(f'lower={e["lower"]} not in row')
    if e['upper'] is not None and str(e['upper']) not in rowtext:
        ok = False; notes.append(f'upper={e["upper"]} not in row')
    if e['coef'] is not None and str(e['coef']) not in rowtext:
        ok = False; notes.append(f'coef={e["coef"]} not in row')
    if e['ratio'] is not None and str(e['ratio']) not in rowtext:
        ok = False; notes.append(f'ratio={e["ratio"]} not in row')
    if not ok:
        problems += 1
        print(f'  PROBLEM {cid}: {"; ".join(notes)} | row: {rowtext[:120]}')

print()
print(f'Total IDs checked: {len(exp)}, problems: {problems}')
print('Doc table coverage vs Commission_Tier 42 rows: PASS' if problems == 0 else 'FAIL')
