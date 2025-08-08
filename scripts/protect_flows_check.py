#!/usr/bin/env python3
"""
Protect critical flows from accidental modification.

Protected areas:
- Upload flow: main.py (upload_to_oss function only), src/newsletter_system/oss/**, config.json oss.*
- Crawl stable entry: ensure main.py keeps 'crawl' subparser with '--output'

Bypass:
- Set env ALLOW_PROTECTED_FLOW_CHANGES=1
- Or add commit message containing: [override protected]

Usage:
- Local pre-commit: scripts/protect_flows_check.py --staged
- CI: scripts/protect_flows_check.py --base-ref <ref>
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: List[str], check: bool = True) -> Tuple[int, str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stdout}")
    return proc.returncode, proc.stdout


def get_changed_files_staged() -> List[str]:
    _, out = run(["git", "diff", "--cached", "--name-only"])
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return [f for f in files if "__pycache__/" not in f and not f.endswith((".pyc", ".pyo"))]


def get_changed_files_vs_base(base_ref: str) -> List[str]:
    # Ensure base exists
    code, _ = run(["git", "rev-parse", base_ref], check=False)
    if code != 0:
        # Fallback to previous commit
        base_ref = "HEAD~1"
        code2, _ = run(["git", "rev-parse", base_ref], check=False)
        if code2 != 0:
            return []
    _, out = run(["git", "diff", "--name-only", f"{base_ref}..HEAD"])
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return [f for f in files if "__pycache__/" not in f and not f.endswith((".pyc", ".pyo"))]


def git_show(base_ref: str, path: str) -> Optional[str]:
    code, out = run(["git", "show", f"{base_ref}:{path}"], check=False)
    if code != 0:
        return None
    return out


def load_json_str(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception:
        return None


def extract_function_block(src: str, func_name: str) -> Optional[str]:
    # Simple regex to capture def func_name(...) block (non-greedy)
    pattern = re.compile(rf"def\s+{re.escape(func_name)}\s*\([\s\S]*?\n(?=def\s+|if __name__|\Z)")
    m = pattern.search(src)
    if m:
        return m.group(0)
    return None


def crawl_has_output_arg(src: str) -> bool:
    # Ensure the crawl subparser defines an --output argument
    # Look for subparsers.add_parser('crawl' ...) ... add_argument('--output'
    crawl_parser_idx = src.find("add_parser('crawl'")
    if crawl_parser_idx == -1:
        return False
    tail = src[crawl_parser_idx:]
    return "add_argument('--output'" in tail


def main(argv: List[str]) -> int:
    if os.getenv("ALLOW_PROTECTED_FLOW_CHANGES") == "1":
        print("[protect] Bypass via ALLOW_PROTECTED_FLOW_CHANGES=1")
        return 0

    # If running in CI with a merge commit, allow opt-out via commit message
    code, msg = run(["git", "log", "-1", "--pretty=%B"], check=False)
    if code == 0 and "[override protected]" in msg:
        print("[protect] Bypass via commit message override")
        return 0

    base_ref = None
    staged = False
    for i, a in enumerate(argv):
        if a == "--base-ref" and i + 1 < len(argv):
            base_ref = argv[i + 1]
        if a == "--staged":
            staged = True

    if staged:
        changed = get_changed_files_staged()
    else:
        changed = get_changed_files_vs_base(base_ref or "HEAD~1")

    protected_patterns = [
        "src/newsletter_system/oss/",
    ]

    violations: List[str] = []

    # 1) Block changes to any OSS module files
    for f in changed:
        if any(f.startswith(p) for p in protected_patterns):
            violations.append(f"Protected path changed: {f}")

    # Choose a base for comparisons
    base_for_compare = base_ref or ("HEAD" if staged else "HEAD~1")

    # 2) For config.json, block changes to oss.* contract only
    if "config.json" in changed and base_for_compare:
        base_content = git_show(base_for_compare, "config.json")
        head_content = Path("config.json").read_text(encoding="utf-8")
        base_json = load_json_str(base_content or "{}") or {}
        head_json = load_json_str(head_content or "{}") or {}
        if base_json.get("oss") != head_json.get("oss"):
            violations.append("config.json oss.* contract changed")

    # 3) For main.py, block changes to upload_to_oss() content; require crawl output arg present
    if "main.py" in changed:
        base_src = git_show(base_for_compare, "main.py") or ""
        head_src = Path("main.py").read_text(encoding="utf-8")
        base_block = extract_function_block(base_src, "upload_to_oss") or ""
        head_block = extract_function_block(head_src, "upload_to_oss") or ""
        if base_block and head_block and base_block != head_block:
            violations.append("main.py upload_to_oss() modified")
        # Ensure crawl still has --output arg
        if not crawl_has_output_arg(head_src):
            violations.append("main.py crawl subparser must keep --output argument")

    if violations:
        print("\nProtect Flows Check failed:\n- " + "\n- ".join(violations))
        print("\nTo override intentionally, set ALLOW_PROTECTED_FLOW_CHANGES=1 or include '[override protected]' in commit message.")
        return 1

    print("[protect] OK - no protected flow changes detected")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


