# Venetian Wheat

Automotive accountability intelligence platform. AI agents monitor 16 fields
of transportation safety compliance, detect violations, and escalate through
civil channels using a subsidiarity model — help first, sue last.

Built for Englewood, Colorado. Forkable for any city.

## What it does

- **16 automotive fields** — fleet compliance, tow companies, used car dealers,
  dealer financing, auto repair, insurance, school zones, pedestrian safety,
  trucking, rideshare, parking/booting, emissions, road safety, title/registration,
  exhaust/noise, window tint
- **1 marketing field** — SEO, outreach, community building
- **15 data channels** — Google reviews, Yelp/BBB, CFPB, FMCSA, CDOT, DMV,
  PUC, local news, 311, Nextdoor, court records, AG complaints, emissions,
  shop social media, community reports
- **Graduated escalation** — seed → sprout → notice → virtue → community →
  demand → civil → harvest (never skips stages)
- **Daily intelligence briefings** — scans, analysis, cross-field correlation
- **No Sunday runs** — Sabbath rest

## Quick Start (Ubuntu)

Every command you need, in order:

```bash
# 1. Clone and install
git clone https://github.com/EricTylerZ/venetian-wheat.git
cd venetian-wheat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Claude Code auth (required — all LLM work runs through Claude Code Pro Max)
npm install -g @anthropic-ai/claude-code
claude   # Follow auth prompts, then exit

# 3. Launch the dashboard
source venv/bin/activate
python app.py
# Open http://localhost:5001
```

That's it. The database initializes automatically on first run.

### What you see in the dashboard

- **Fields tab** — All 17 accountability fields. Click any field to scan it,
  view its cases, or run analysis.
- **Channels tab** — All 15 data channels. Click "Scan Now" on any channel
  to run a scan.
- **Cases tab** — All active cases across fields, with escalation controls.
  Escalate or resolve cases right from the table.
- **Briefing tab** — Daily intelligence briefing. Click "Generate Briefing"
  to create one from current data.
- **Submit Report tab** — Community intake form. Anyone can submit a concern
  and it routes to the right field, creates an escalation case automatically.

### Top-level buttons

- **Run Daily Cycle** — Full cycle (Sonnet scan → Opus correlation → field analysis → briefing) with live log
- **Channel Scan Only** — Just scan channels for new signals (Sonnet)
- **Generate Briefing** — Create briefing from existing data

### Set up daily automation (optional)

```bash
# Runs at 6am Mon-Sat, skips Sunday automatically:
crontab -e
# Add:
0 6 * * 1-6 cd /path/to/venetian-wheat && venv/bin/python daily_runner.py --email >> reports/daily_runner.log 2>&1
```

### Email briefings (optional)

```bash
cat > email_config.json << 'EOF'
{
  "to": "you@example.com",
  "from": "wheat@yourdomain.com",
  "method": "smtp",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "you@gmail.com",
  "smtp_pass": "your_app_password"
}
EOF
```

## Fork for Your City

1. Fork this repo
2. Edit `projects.json` — change jurisdiction, laws, and sources for your state/city
3. Edit `channels.json` — update source URLs for your local news, courts, agencies
4. Update law citations in each field's `strategist_prompt` to match your jurisdiction
5. Run `python daily_runner.py --dry-run` to verify your config

Key things to localize:
- **Zip codes** in prompts (currently 80110/80111/80112)
- **State laws** (currently Colorado CRS citations)
- **Court jurisdiction** (currently Arapahoe County)
- **News sources** (currently Englewood Herald, Denver Post, etc.)
- **Government agencies** (currently CO DMV, CO PUC, CDPHE, etc.)
- **311/municipal systems** (currently City of Englewood)

Federal sources (FMCSA, CFPB, FTC, EPA, ADA) work nationwide — no changes needed.

## Architecture

```
CHANNELS (15 pipelines)          FIELDS (17 agents)
┌─────────────────┐             ┌──────────────────┐
│ Google Reviews   │──┐         │ Fleet Compliance  │
│ Yelp/BBB         │──┤    ┌───▶│ Tow Companies     │
│ CFPB             │──┤    │    │ Used Car Dealers  │
│ FMCSA            │──┤    │    │ Dealer Finance    │
│ CDOT Crash       │──┼────┤    │ Auto Repair       │
│ CO DMV           │──┤    │    │ ... 12 more       │
│ Local News       │──┤    │    └──────┬───────────┘
│ Nextdoor/Social  │──┤    │           │
│ Court Records    │──┘    │    ESCALATION ENGINE
│ Community Reports│───────┘    ┌──────▼───────────┐
└─────────────────┘             │ seed → sprout →  │
                                │ notice → virtue →│
  SONNET (daily scan)            │ community →      │
  ──or──                        │ demand → civil → │
  COMMUNITY (web form)          │ harvest          │
                                └──────────────────┘
```

### Daily Cycle (Mon-Sat)

1. **SCAN** — Claude Sonnet scans channels (reviews, news, social, records)
1.5. **CORRELATE** — Claude Opus deduplicates, cross-references, enriches signals
2. **ANALYZE** — Claude Opus field agents analyze enriched signals
3. **ESCALATE** — Cross-field entity detection + escalation check
4. **BRIEF** — Claude Opus writes intelligence narrative (text + JSON + email)

### Escalation (Subsidiarity)

| Stage | What happens | Wait time |
|-------|-------------|-----------|
| Seed | Signal detected | 1 day |
| Sprout | Validated against law, evidence attached | 3 days |
| Notice | Friendly first contact letter | 14 days |
| Virtue | Offered growth path | 30 days |
| Community | Peer/parish pressure | 14 days |
| Demand | Formal demand letter with deadline | 30 days |
| Civil | Filing with full evidence chain | 90 days |
| Harvest | Resolution achieved | — |

## Key Files

| File | Purpose |
|------|---------|
| `daily_runner.py` | Daily cycle orchestrator |
| `projects.json` | 17 field definitions with prompts and laws |
| `channels.json` | 15 data channel definitions |
| `wheat/channels.py` | Channel routing and intake logic |
| `wheat/escalation.py` | Case tracking and escalation engine |
| `wheat/scan_tasks.py` | Channel scanning (Claude Sonnet) |
| `wheat/analyst.py` | Analyst brain: correlation + briefing synthesis |
| `wheat/field_manager.py` | Field analysis orchestration |
| `wheat/providers.py` | LLM provider abstraction (Claude Code active) |
| `wheat/templates/` | Notice and demand letter templates |
| `app.py` | Flask web dashboard |

## Philosophy

> "I came not to bring peace, but a sword" — and yet the goal is peace.

This platform exists to help people follow the rules and to help those harmed
by rule-breakers find justice through civil channels. It operates on the
principle of subsidiarity: handle problems at the lowest effective level first.

- A friendly notice before a demand letter
- A demand letter before a lawsuit
- A lawsuit only when everything else has failed
- Never criminal pursuit — always civil remedy
- Focus on companies and entities, not individuals
- Shops that profit from noncompliance are the primary targets

## License

MIT
