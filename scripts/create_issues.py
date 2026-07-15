#!/usr/bin/env python3
"""
Creates the eight sector issues from docs/system-diagnosis.md on GitHub.

Why this exists: `gh` is authenticated in YOUR terminal but not in the one
Claude runs commands in, and handing over your token isn't on the table. So
Claude wrote the issues; you run this once and they appear.

Usage (from the project root, in your own terminal):

    python3 scripts/create_issues.py            # show what would be created
    python3 scripts/create_issues.py --create   # actually create them

Safe to re-run: --create refuses to make a duplicate of an issue whose title
already exists on the repo. Delete this file once the issues are up.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = "Zdzz16/TradingResearch"
DIAGNOSIS = Path(__file__).resolve().parent.parent / "docs" / "system-diagnosis.md"

# Matches:  `[System Cleanup & Upgrade] Whatever`   then the next ```markdown block
PATTERN = re.compile(
    r"^`(\[System Cleanup & Upgrade\][^`]+)`\s*\n+\*\*Issue body:\*\*\s*\n+```markdown\n(.*?)\n```",
    re.MULTILINE | re.DOTALL,
)


def parse_sectors(text):
    return [(m.group(1).strip(), m.group(2).strip()) for m in PATTERN.finditer(text)]


def existing_titles():
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "all",
         "--limit", "100", "--json", "title", "--jq", ".[].title"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        sys.exit(f"gh failed — is it logged in? ({out.stderr.strip()})")
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true",
                    help="actually create the issues (default is a dry run)")
    args = ap.parse_args()

    if not DIAGNOSIS.is_file():
        sys.exit(f"Not found: {DIAGNOSIS}")

    sectors = parse_sectors(DIAGNOSIS.read_text())
    if not sectors:
        sys.exit("Parsed 0 sectors — has docs/system-diagnosis.md changed format?")

    print(f"Found {len(sectors)} sector issues in {DIAGNOSIS.name}\n")

    if not args.create:
        for title, body in sectors:
            print(f"  • {title}  ({len(body.splitlines())} lines of body)")
        print("\nDry run. Re-run with --create to publish them:")
        print("    python3 scripts/create_issues.py --create")
        return

    already = existing_titles()
    created = skipped = 0
    for title, body in sectors:
        if title in already:
            print(f"  ↷ skipped (already exists): {title}")
            skipped += 1
            continue
        res = subprocess.run(
            ["gh", "issue", "create", "--repo", REPO,
             "--title", title, "--body-file", "-"],
            input=body, capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"  ✗ FAILED: {title}\n    {res.stderr.strip()}")
        else:
            print(f"  ✓ {title}\n    {res.stdout.strip()}")
            created += 1

    print(f"\nDone — {created} created, {skipped} skipped.")


if __name__ == "__main__":
    main()
