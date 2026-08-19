#!/usr/bin/env python3
"""T11c helper: extract formula expressions for named fields."""
import json, subprocess, sys, shutil
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=4):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError as exc:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}")
            import time; time.sleep(2)
            continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            import time; time.sleep(2)
            continue
        return result["data"]
    raise last

def main():
    table_id = sys.argv[1]
    names = sys.argv[2:]
    d = cli(["+table-get", "--base-token", BASE, "--table-id", table_id])
    for f in d.get("fields", []):
        if f["name"] in names:
            print(f"### {f['name']} ({f['id']})")
            print(json.dumps(f, ensure_ascii=False, indent=2))
            print()

if __name__ == "__main__":
    main()
