#!/usr/bin/env python3
"""Require an add-on version bump when installed add-on code changes in a PR."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

CONFIG = "home_agent/config.yaml"
VERSION_RE = re.compile(r'^version:\\s*["\\']?(\\d+)\\.(\\d+)\\.(\\d+)["\\']?\\s*$', re.MULTILINE)

def parse_version(content):
    match = VERSION_RE.search(content)
    if not match:
        raise ValueError("Missing or invalid MAJOR.MINOR.PATCH version in " + CONFIG)
    return tuple(map(int, match.groups()))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Git commit/ref for PR target")
    args = parser.parse_args()
    current = parse_version(Path(CONFIG).read_text(encoding="utf-8"))
    base_config = subprocess.check_output(["git", "show", f"{args.base}:{CONFIG}"], text=True)
    base = parse_version(base_config)
    changes = subprocess.check_output(["git", "diff", "--name-only", f"{args.base}...HEAD"], text=True).splitlines()
    runtime_changed = any(p.startswith("home_agent/") and p != CONFIG for p in changes)
    if runtime_changed and current <= base:
        raise SystemExit(f"Add-on code changed; version must increase: base={base}, current={current}")
    if current < base:
        raise SystemExit(f"Add-on version cannot decrease: base={base}, current={current}")
    print(f"Version guard passed: base={base}, current={current}, runtime_changed={runtime_changed}")

if __name__ == "__main__":
    main()
