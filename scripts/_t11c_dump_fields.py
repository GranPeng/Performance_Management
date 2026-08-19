#!/usr/bin/env python3
"""T11c helper: dump table fields as compact lines."""
import json, subprocess, sys, shutil
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args):
    p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}") from exc
    if p.returncode != 0 or not result.get("ok"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result["data"]

def main():
    table_id = sys.argv[1]
    d = cli(["+table-get", "--base-token", BASE, "--table-id", table_id])
    for f in d.get("fields", []):
        prop = json.dumps(f.get("property", {}), ensure_ascii=False)
        print(f"{f['id']} | {f['name']} | {f['type']} | {prop[:300]}")

if __name__ == "__main__":
    main()
