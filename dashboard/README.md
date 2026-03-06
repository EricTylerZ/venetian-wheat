# Venetian Wheat Dashboard

Vercel-deployed web dashboard for [venetian-wheat](https://github.com/EricTylerZ/venetian-wheat) — manage your client projects from your phone.

## What it does

- **Dashboard**: See all client branches at a glance (last commit, time since activity)
- **Project detail**: View recent commits and the full CLAUDE.md for each client
- **Edit CLAUDE.md**: Update client context directly from your phone — commits via GitHub API
- **Create projects**: Add new client branches with CLAUDE.md templates from the web UI

## Deploy to Vercel

1. Push this repo to GitHub
2. Import it in [Vercel](https://vercel.com/new)
3. Set environment variables:

| Variable | Value |
|----------|-------|
| `GITHUB_TOKEN` | Fine-grained PAT with `Contents` read/write on `venetian-wheat` |
| `GITHUB_OWNER` | `EricTylerZ` |
| `GITHUB_REPO` | `venetian-wheat` |
| `DASHBOARD_PASSWORD` | A password only you know — required to access the dashboard |

4. Deploy. Access from your phone at your Vercel URL.
5. Enter your password once — you'll get a cookie that lasts 30 days.

## Create a GitHub Token

1. Go to https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Name: `venetian-wheat-dashboard`
4. Repository access: Select `venetian-wheat` only
5. Permissions: `Contents` → Read and write, `Metadata` → Read
6. Generate and copy to Vercel env vars

## Architecture

```
Phone browser
  → Vercel (Next.js)
    → GitHub API (reads branches, commits, files)
    → GitHub API (creates branches, edits CLAUDE.md)

Your machine (separately)
  → Claude Code CLI (the actual work)
  → git push (results appear in dashboard)
```

The dashboard is read/write for project management but Claude Code still runs on your machine. The dashboard lets you set up and monitor projects from anywhere.

## Local dev

```bash
cp .env.example .env.local
# Fill in your GitHub token
npm install
npm run dev
```
