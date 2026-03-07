# Venetian Wheat — Namecheap Setup Guide
Windows-friendly. No manual FTP after this one-time setup.

---

## What you'll have when done
- Auto-deploy: push to GitHub → files land on Namecheap automatically
- IP access logging: every visitor logged to YOUR MySQL database
- Server Monitor tab in your Vercel dashboard
- cPanel data (domains, disk, SSL) readable from the dashboard
- Shared data API for cross-domain key/value storage

**Your details:**
- cPanel username: `zoseegkt`
- Primary domain: `zoseco.com`
- Wheat API domain: `ericzosso.com` → subfolder `/wheat-api/`

---

## Step 1 — Enable SSH on Namecheap

1. Log in to cPanel at `https://cpanel.namecheap.com`
2. Search for **SSH Access** (or Terminal)
3. Click **Manage SSH Keys** → **Generate New Key** → keep defaults → Generate
4. Click **Authorize** next to the new key
5. Note your SSH details:
   - Host: `server123.web-hosting.com` (find under **Server Information** in cPanel sidebar)
   - Username: `zoseegkt`
   - Port: `21098` (Namecheap shared hosting SSH port)

---

## Step 2 — Create MySQL Database

1. In cPanel → **MySQL Databases**
2. Create database: `wheat` → cPanel makes it `zoseegkt_wheat`
3. Create user: `wheat` + strong password → cPanel makes it `zoseegkt_wheat`
4. Add user to database, grant **ALL PRIVILEGES**
5. Note your password — you'll need it in Step 4

---

## Step 3 — Run the Schema

1. In cPanel → **phpMyAdmin**
2. Click on `zoseegkt_wheat` in the left panel
3. Click **Import** tab → choose file → select `server/schema.sql` from this repo
4. Click **Go**

You should see 4 tables: `access_log`, `blocked_ips`, `shared_data`, `wheat_projects`

---

## Step 4 — Upload config.php (one-time, manual)

This is the ONLY thing you manually upload. After this, everything auto-deploys.

1. Copy `server/config.php` to a temp location on your Windows PC
2. Edit it — fill in:
   ```
   DB_NAME  = 'zoseegkt_wheat'
   DB_USER  = 'zoseegkt_wheat'
   DB_PASS  = 'your-mysql-password'
   WHEAT_API_KEY = (generate below)
   DASHBOARD_ORIGIN = 'https://your-project.vercel.app'
   ```
3. **Generate API key** — open PowerShell and run:
   ```powershell
   -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
   ```
   Copy the output — this is your `WHEAT_API_KEY`
4. In cPanel → **File Manager** → navigate to:
   `public_html/ericzosso.com/wheat-api/` (create folders if needed)
5. Upload your edited `config.php` there
6. **Delete** the temp copy from your PC — don't leave credentials lying around

---

## Step 5 — Add GitHub Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `NAMECHEAP_HOST` | Your server hostname (e.g. `server123.web-hosting.com`) |
| `NAMECHEAP_USER` | `zoseegkt` |
| `NAMECHEAP_SSH_PASS` | Your cPanel/SSH password |

---

## Step 6 — Add Vercel Environment Variables

Go to [vercel.com](https://vercel.com) → your project → **Settings** → **Environment Variables**

Add these 2 variables:

| Variable | Value |
|----------|-------|
| `WHEAT_SERVER_URL` | `https://ericzosso.com/wheat-api` |
| `WHEAT_API_KEY` | The same key you put in config.php |

Click **Save** → Vercel will redeploy automatically.

---

## Step 7 — Trigger First Deploy

In PowerShell (Windows), navigate to the repo and push:

```powershell
cd path\to\venetian-wheat
git push origin claude/automate-server-deployment-AzdL7
```

Then go to **GitHub → Actions** tab — you should see the deploy workflow running.
It will SSH into Namecheap and upload the `server/` folder to `~/public_html/ericzosso.com/wheat-api/`.

---

## Step 8 — Test It

Open PowerShell and test the API:

```powershell
# Test the logger (replace YOUR_API_KEY)
$headers = @{ "X-Wheat-Key" = "YOUR_API_KEY"; "Content-Type" = "application/json" }
$body = '{"page":"/test","domain":"ericzosso.com","event":"test"}'
Invoke-RestMethod -Uri "https://ericzosso.com/wheat-api/log.php" -Method POST -Headers $headers -Body $body

# Expected: {"ok":true,"id":"1"}
```

Then open your Vercel dashboard → click **Server →** — you should see the test entry in the log table.

---

## Going Forward — Zero Manual Work

After this setup, your workflow is:

```
Edit code in Claude Code on Windows
    ↓
git push
    ↓
GitHub Actions deploys server/ to Namecheap SSH automatically
Vercel deploys dashboard/ automatically
    ↓
Open Vercel dashboard to see who's visiting, manage cPanel
```

To add a new PHP endpoint: create it in `server/`, push, done.
To add a new dashboard page: create it in `dashboard/src/app/`, push, done.

---

## Troubleshooting

**GitHub Actions fails with "connection refused"**
→ Double-check SSH is enabled in cPanel. Try port 22 if 21098 fails.

**`config.php` not found error**
→ You need to upload it manually (Step 4). It's intentionally excluded from git.

**"unauthorized" from the API**
→ WHEAT_API_KEY in Vercel env vars must exactly match the one in config.php.

**cPanel tab shows "Unavailable"**
→ The `uapi` command is only available on some hosts. On Namecheap shared hosting it should work via SSH, but the PHP script calls it via `shell_exec()` which may be disabled. Check cPanel → PHP → Disable Functions list.
