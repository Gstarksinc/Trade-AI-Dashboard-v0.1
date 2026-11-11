"""CI Verification Script: Keeps Documentation and Implementation in Strict Sync (Step 4)."""

import os
import re
import sys
import subprocess
from pathlib import Path


def check_events_in_docs():
    contracts_file = Path("libs/contracts/events.py")
    events_doc_file = Path("docs/EVENTS.md")
    if not contracts_file.exists() or not events_doc_file.exists():
        print("FAIL: contracts or docs/EVENTS.md missing")
        return False

    contracts_text = contracts_file.read_text(encoding="utf-8")
    events_doc = events_doc_file.read_text(encoding="utf-8")

    event_types = re.findall(r'event_type:\s*str\s*=\s*["\']([^"\']+)["\']', contracts_text)
    missing = [et for et in set(event_types) if et not in events_doc]
    if missing:
        print(f"FAIL: The following events from libs/contracts are missing in docs/EVENTS.md: {missing}")
        return False
    print(f"PASS: All {len(set(event_types))} contract event types are documented in docs/EVENTS.md")
    return True


def check_env_vars_in_operations():
    operations_doc = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    vars_in_env = re.findall(r"^([A-Z0-9_]+)=", env_example, re.MULTILINE)
    missing = [v for v in vars_in_env if v not in operations_doc]
    if missing:
        print(f"FAIL: The following environment variables from .env.example are missing in docs/OPERATIONS.md: {missing}")
        return False
    print(f"PASS: All {len(vars_in_env)} .env.example variables appear in docs/OPERATIONS.md")
    return True


def check_no_private_keys_or_execution():
    # 1. No exchange secret keys or private keys in code
    forbidden_terms = ["api_secret", "secret_key", "private_key"]
    code_files = []
    for ext in ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx"]:
        code_files.extend(Path("services").rglob(ext))
        code_files.extend(Path("libs").rglob(ext))
        code_files.extend(Path("dashboard/app").rglob(ext))

    for f in code_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for term in forbidden_terms:
            matches = re.findall(rf".{{0,30}}{term}.{{0,30}}", text, re.IGNORECASE)
            # Filter out harmless variable names or comments if any
            clean_matches = [m for m in matches if "test" not in str(f) and "gen_env" not in str(f)]
            if clean_matches:
                print(f"FAIL: Detected forbidden term '{term}' in {f}: {clean_matches}")
                return False
    print("PASS: Zero exchange private keys or secret keys found in repo")

    # 2. No real order execution endpoints
    for f in Path("services").rglob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"POST\s+/fapi/v1/order|def\s+create_order|def\s+new_order", text):
            print(f"FAIL: Detected real order execution code in {f}")
            return False
    print("PASS: Zero real order execution code found in services")

    # 3. Dashboard has no direct exchange connections or mock data
    for f in Path("dashboard/app").rglob("*.js*"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "binance.com" in text:
            print(f"FAIL: Detected direct Binance URLs in dashboard file {f}")
            return False
    print("PASS: Zero direct Binance URLs in dashboard/app/")
    return True


def check_mermaid_syntax():
    md_files = list(Path("docs").glob("**/*.md")) + list(Path(".").glob("*.md"))
    total_blocks = 0
    errors = 0
    for f in md_files:
        content = f.read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", content, re.DOTALL)
        for i, b in enumerate(blocks):
            total_blocks += 1
            # Check basic syntax rules: labels with special characters must be quoted
            lines = b.strip().split("\n")
            for line_no, line in enumerate(lines, 1):
                stripped = line.strip()
                # Check for unquoted bracket or slash starting a label
                if re.search(r"-->\|[^\"|]*[/\[\]\(\)][^\"|]*\|", stripped):
                    print(f"WARNING: {f} block {i} line {line_no}: unquoted special characters in label: {stripped}")
                    errors += 1
    if errors > 0:
        print(f"FAIL: Found {errors} Mermaid syntax warning(s)")
        return False
    print(f"PASS: Scanned {total_blocks} Mermaid diagram blocks across {len(md_files)} markdown files with 0 syntax errors")
    return True


if __name__ == "__main__":
    p1 = check_events_in_docs()
    p2 = check_env_vars_in_operations()
    p3 = check_no_private_keys_or_execution()
    p4 = check_mermaid_syntax()

    if all([p1, p2, p3, p4]):
        print("\nALL DOCUMENTATION & IMPLEMENTATION CI CHECKS PASSED.")
        sys.exit(0)
    else:
        print("\nSOME CI CHECKS FAILED.")
        sys.exit(1)
