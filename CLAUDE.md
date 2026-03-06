# Venetian Wheat — Project Context

## What is this?
Multi-client project management using Claude Code. Each client gets a git branch
with their own CLAUDE.md that gives Claude context for that client's work.

## How it works
```
python wheat.py list                 # See all clients
python wheat.py new acme_corp       # Create client branch + CLAUDE.md
python wheat.py work acme_corp      # Switch to branch + launch Claude
python wheat.py status              # See recent commits across all clients
```

Each client branch has its own CLAUDE.md that tells Claude:
- Who the client is and what they need
- Current priorities (update as work progresses)
- Key files and architecture
- Rules and constraints

## Key files
- `wheat.py` — Client launcher (list, new, switch, status, work)
- `clients.json` — Registry of client projects
- `CLAUDE.md` — Per-branch context file (this one is for the main branch)

## Rules
- Keep `wheat.py` simple — it's a launcher, not a framework
- Each client branch is independent — don't merge between client branches
- CLAUDE.md is the single source of truth for each client's context
- Commits are the "seeds" — small, focused, tested
