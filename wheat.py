#!/usr/bin/env python3
"""
wheat — Multi-client project launcher for Claude Code.

Usage:
    python wheat.py list                    # Show all client branches + status
    python wheat.py new <client_id>         # Create a new client branch with CLAUDE.md
    python wheat.py switch <client_id>      # Switch to a client branch
    python wheat.py status [client_id]      # Show recent work on a client (or all)
    python wheat.py work <client_id>        # Switch + launch Claude Code

Each client is a git branch with its own CLAUDE.md that acts as the
strategist prompt. Claude Code reads it automatically.

No Flask, no database, no API fees. Just git + Claude Code + Pro Max.
"""
import subprocess
import sys
import os
import json
from datetime import datetime


CLIENTS_FILE = "clients.json"


def run(cmd, capture=True, check=False):
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip() if capture else None


def load_clients():
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE) as f:
            return json.load(f)
    return {}


def save_clients(clients):
    with open(CLIENTS_FILE, "w") as f:
        json.dump(clients, f, indent=2)


def get_current_branch():
    return run("git branch --show-current")


def get_branch_commits(branch, n=5):
    """Get last n commits on a branch."""
    result = run(f'git log {branch} --oneline -n {n} 2>/dev/null')
    return result.split("\n") if result else []


def get_all_client_branches():
    """Find all branches that start with 'client/'."""
    result = run("git branch --list 'client/*' --format='%(refname:short)'")
    return [b.strip() for b in result.split("\n") if b.strip()]


# ---- Commands ----

def cmd_list():
    clients = load_clients()
    branches = get_all_client_branches()
    current = get_current_branch()

    if not clients and not branches:
        print("No clients yet. Create one with: python wheat.py new <client_id>")
        return

    print("\n  VENETIAN WHEAT — Client Fields\n")
    print(f"  {'Client':<20} {'Branch':<30} {'Provider':<15} {'Status'}")
    print(f"  {'─'*20} {'─'*30} {'─'*15} {'─'*20}")

    for cid, info in clients.items():
        branch = f"client/{cid}"
        is_current = "● " if branch == current else "  "
        exists = branch in branches
        provider = info.get("provider", "claude_code")

        if exists:
            commits = get_branch_commits(branch, 1)
            last = commits[0] if commits else "no commits"
            status = f"active — {last}"
        else:
            status = "branch missing"

        print(f"{is_current}{cid:<20} {branch:<30} {provider:<15} {status}")

    # Show branches without client entries
    for branch in branches:
        cid = branch.replace("client/", "")
        if cid not in clients:
            is_current = "● " if branch == current else "  "
            print(f"{is_current}{cid:<20} {branch:<30} {'unknown':<15} unregistered")

    print()


def cmd_new(client_id):
    clients = load_clients()
    branch = f"client/{client_id}"

    if client_id in clients:
        print(f"Client '{client_id}' already exists. Use: python wheat.py switch {client_id}")
        return

    # Create the branch
    current = get_current_branch()
    run(f"git checkout -b {branch}", check=True)

    # Generate CLAUDE.md
    claude_md = f"""# {client_id.replace('_', ' ').title()} — Project Context

## Who is this client?
<!-- Describe the client and what they need -->
[TODO: Describe the client, their business, what problem you're solving]

## What does this codebase do?
<!-- Claude Code reads this automatically every session -->
[TODO: Describe the codebase architecture, key files, tech stack]

## Current priorities
<!-- What should Claude focus on right now? Update this as work progresses. -->
1. [TODO: First priority]
2. [TODO: Second priority]
3. [TODO: Third priority]

## Rules and constraints
<!-- Things Claude should NOT do, security considerations, style preferences -->
- Do not modify files outside of this project's scope
- Run tests before committing
- Keep commits small and focused
- [TODO: Add client-specific rules]

## Key files
<!-- Help Claude navigate the codebase -->
- `CLAUDE.md` — this file (project context)
- [TODO: List important files]

## Recent decisions
<!-- Track architectural decisions so Claude has context across sessions -->
- {datetime.now().strftime('%Y-%m-%d')}: Project initialized
"""

    with open("CLAUDE.md", "w") as f:
        f.write(claude_md)

    # Register the client
    clients[client_id] = {
        "name": client_id.replace("_", " ").title(),
        "provider": "claude_code",
        "created": datetime.now().isoformat(),
        "branch": branch,
    }
    save_clients(clients)

    run("git add CLAUDE.md clients.json")
    run(f'git commit -m "Initialize client field: {client_id}"')

    print(f"""
  Created client field: {client_id}
  Branch: {branch}

  Next steps:
    1. Edit CLAUDE.md with this client's context
    2. Run: python wheat.py work {client_id}
       (or just run 'claude' — it reads CLAUDE.md automatically)
    3. Tell Claude what to build. It's the strategist AND the coder now.

  To switch back: python wheat.py switch {current}
""")


def cmd_switch(client_id):
    branch = f"client/{client_id}"
    branches = get_all_client_branches()

    if branch not in branches:
        # Check if it's a regular branch name
        result = run(f"git branch --list '{client_id}' --format='%(refname:short)'")
        if result.strip():
            branch = client_id
        else:
            print(f"No branch '{branch}' found. Create it with: python wheat.py new {client_id}")
            return

    run(f"git checkout {branch}", check=True)
    print(f"  Switched to: {branch}")

    # Show CLAUDE.md summary if it exists
    if os.path.exists("CLAUDE.md"):
        with open("CLAUDE.md") as f:
            lines = f.readlines()
        # Print first non-empty, non-comment line as context
        for line in lines:
            if line.strip() and not line.startswith("#") and not line.startswith("<!--"):
                print(f"  Context: {line.strip()[:80]}")
                break

    print(f"\n  Ready. Run 'claude' to start working.")


def cmd_status(client_id=None):
    if client_id:
        branches = [f"client/{client_id}"]
    else:
        branches = get_all_client_branches()

    if not branches:
        print("No client branches found.")
        return

    print("\n  VENETIAN WHEAT — Recent Work\n")

    for branch in branches:
        cid = branch.replace("client/", "")
        commits = get_branch_commits(branch, 8)
        print(f"  {cid}")
        print(f"  {'─' * 60}")
        if commits:
            for commit in commits:
                print(f"    {commit}")
        else:
            print("    (no commits)")
        print()


def cmd_work(client_id):
    cmd_switch(client_id)
    print("  Launching Claude Code...\n")
    os.execvp("claude", ["claude"])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "list":
        cmd_list()
    elif command == "new" and len(sys.argv) >= 3:
        cmd_new(sys.argv[2])
    elif command == "switch" and len(sys.argv) >= 3:
        cmd_switch(sys.argv[2])
    elif command == "status":
        cmd_status(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif command == "work" and len(sys.argv) >= 3:
        cmd_work(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
