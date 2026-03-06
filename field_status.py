#!/usr/bin/env python3
"""
field_status — Quick overview of all client fields.

Run from anywhere: python field_status.py
Works great over SSH from your phone.

Shows:
  - All client branches with last commit
  - Current branch highlighted
  - Files changed since last commit
  - Quick diff stats
"""
import subprocess
import json
import os
import sys


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def color(text, code):
    """ANSI color — works in phone SSH clients too."""
    return f"\033[{code}m{text}\033[0m"


def main():
    current = run("git branch --show-current")
    branches = run("git branch --list 'client/*' --format='%(refname:short)'")
    branches = [b.strip() for b in branches.split("\n") if b.strip()]

    clients_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "clients.json")
    clients = {}
    if os.path.exists(clients_file):
        with open(clients_file) as f:
            clients = json.load(f)

    print()
    print(color("  ╔══════════════════════════════════════╗", "33"))
    print(color("  ║     VENETIAN WHEAT — Field Status    ║", "33"))
    print(color("  ╚══════════════════════════════════════╝", "33"))
    print()

    if not branches and not clients:
        print("  No client fields yet.")
        print(f"  Create one: python wheat.py new <client_id>")
        print()
        return

    for branch in branches:
        cid = branch.replace("client/", "")
        is_current = branch == current
        client_info = clients.get(cid, {})
        name = client_info.get("name", cid)

        # Branch indicator
        marker = color("●", "32") if is_current else " "
        branch_display = color(name, "1") if is_current else name

        print(f"  {marker} {branch_display}")

        # Last 3 commits
        commits = run(f"git log {branch} --oneline --format='%h %s' -n 3 2>/dev/null")
        if commits:
            for line in commits.split("\n"):
                if line.strip():
                    hash_part, msg = line.split(" ", 1)
                    print(f"      {color(hash_part, '90')} {msg[:60]}")

        # If current branch, show working state
        if is_current:
            status = run("git status --short")
            if status:
                changed = len(status.split("\n"))
                print(f"      {color(f'{changed} uncommitted changes', '33')}")

            # Show diff stats
            diff_stat = run("git diff --stat HEAD 2>/dev/null | tail -1")
            if diff_stat:
                print(f"      {color(diff_stat.strip(), '90')}")

        print()

    # Show main branch too if we're on it
    if current and not current.startswith("client/"):
        print(f"  {color('●', '32')} {color(f'[{current}]', '1')} (not a client branch)")
        print()

    # Quick summary
    total = len(branches)
    print(f"  {total} client field{'s' if total != 1 else ''} total")
    print(f"  Current: {color(current, '1')}")
    print()
    print(f"  Switch:  python wheat.py switch <client>")
    print(f"  Work:    python wheat.py work <client>")
    print()


if __name__ == "__main__":
    main()
