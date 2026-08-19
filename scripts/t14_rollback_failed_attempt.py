#!/usr/bin/env python3
"""T14 失败现场回滚：仅删除 Source=SIMULATED_T14_D010_NONZERO 的记录。"""
import json, shutil, subprocess
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
SOURCE = "SIMULATED_T14_D010_NONZERO"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/output/T14_D010失败现场回滚记录.json"
CLI = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")
TABLE = {"Performance_Result":"tbl6tFtVKExFUTWo","Actual":"tbli9VhcUFjVDeNd","Import_Batch":"tblHV3JoVR9AEETw","Project":"tbl1GO2vR9ZAqPbr"}

def call(args):
    p = subprocess.run([CLI,"base",*args,"--as","user"], text=True, capture_output=True)
    d = json.loads(p.stdout)
    if p.returncode or not d.get("ok"):
        raise RuntimeError(json.dumps(d, ensure_ascii=False))
    return d["data"]

def rows(table):
    out=[]; offset=0
    while True:
        d=call(["+record-list","--base-token",BASE,"--table-id",TABLE[table],"--limit","200","--format","json","--offset",str(offset),"--field-id","Source"])
        for rid, values in zip(d["record_id_list"],d["data"]):
            if values and values[0] == SOURCE: out.append(rid)
        if not d.get("has_more"): return out
        offset += len(d["record_id_list"])

def main():
    found={key:rows(key) for key in TABLE}
    for key in ["Performance_Result","Actual","Import_Batch","Project"]:
        for rid in found[key]:
            call(["+record-delete","--base-token",BASE,"--table-id",TABLE[key],"--record-id",rid,"--yes"])
    receipt={"task":"T14","type":"失败现场回滚","timestamp":datetime.now().astimezone().isoformat(),"source":SOURCE,"deleted":found,"order":["Performance_Result","Actual","Import_Batch","Project"],"verification":"逐表按 Source 精确筛选后删除；未触及其他来源记录。"}
    OUT.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"ROLLBACK_PASSED","record":str(OUT.relative_to(ROOT)),"deleted_counts":{k:len(v) for k,v in found.items()}},ensure_ascii=False))
if __name__ == "__main__": main()
