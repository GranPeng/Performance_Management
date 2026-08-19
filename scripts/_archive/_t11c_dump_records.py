#!/usr/bin/env python3
"""T11c helper: dump records (selected fields) for a table, ndjson-ish lines."""
import json, subprocess, sys, shutil, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=4):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last

def main():
    table_id = sys.argv[1]
    fields = sys.argv[2:]
    args = ["+record-list", "--base-token", BASE, "--table-id", table_id, "--limit", "200", "--format", "json"]
    for f in fields:
        args += ["--field-id", f]
    out = []
    offset = 0
    while True:
        d = cli(args + (["--offset", str(offset)] if offset else []))
        names = d.get("fields", [])
        ids = d.get("record_id_list", [])
        rows = d.get("data", [])
        for rid, values in zip(ids, rows):
            out.append((rid, dict(zip(names, values))))
        if not d.get("has_more"):
            break
        offset += len(ids)
    print(f"# {len(out)} records, fields={names}")
    for rid, row in out:
        compact = {k: v for k, v in row.items() if v not in (None, "", [], {})}
        print(json.dumps({"_id": rid, **compact}, ensure_ascii=False))

if __name__ == "__main__":
    main()
