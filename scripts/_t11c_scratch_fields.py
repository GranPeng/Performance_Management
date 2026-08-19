#!/usr/bin/env python3
"""T11c helper: show scratch table field list with expressions."""
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
    d = cli(["+table-get", "--base-token", BASE, "--table-id", table_id])
    for f in d.get("fields", []):
        print(json.dumps({k: f.get(k) for k in ("id", "name", "type", "expression")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
