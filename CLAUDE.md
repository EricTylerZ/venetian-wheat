# Venetian Wheat — Automotive Accountability Intelligence Platform

> **Ecosystem role:** Fish + Bird hybrid (channel scanning → analytical partnership). See [`../DOMINION.md`](../DOMINION.md) for Eric Zosso's agent ecosystem architecture.

## What is this?
An intelligence collection and civil escalation platform focused on automotive
safety and compliance in Englewood, Colorado. Uses AI agents to monitor 16
automotive accountability fields plus a marketing/outreach field.

## Mission
Help people follow the rules. Help those harmed by rule-breakers get justice
through civil channels. Subsidiarity first — address concerns at the lowest
effective level before escalating.

## Architecture

### Fields (17 total — 16 automotive + marketing)
Each field is an area of automotive accountability with its own AI agent(s):
- Fleet Compliance, Tow Companies, Used Car Dealers, Dealer Finance
- Auto Repair, Auto Insurance, School Zone Safety, Pedestrian/Cyclist
- Commercial Trucking, Rideshare/Delivery, Parking/Booting
- Emissions/Environmental, Road/Intersection Safety, Title/Registration
- Exhaust/Noise, Window Tint, Marketing/SEO

### Channels (15 data pipelines)
Reusable data ingestion pipelines that feed multiple fields:
- REVIEWS: Google, Yelp, BBB
- REGULATORY: CFPB, CO AG, PUC
- NEWS: Local RSS, press
- SOCIAL: Nextdoor, Reddit, shop social media
- PUBLIC_RECORDS: FMCSA, CDOT, DMV, 311
- COURT: Arapahoe County civil filings
- COMMUNITY: Direct resident reports

### Daily Cycle (Mon-Sat, no Sunday)
```
PHASE 1: GROK SCANS    — Grok agents scan channels for new signals
PHASE 2: FIELD ANALYSIS — Claude Code agents analyze signals per field
PHASE 3: CORRELATION    — Cross-field entity detection + escalation check
PHASE 4: BRIEFING       — Daily intelligence report (text + JSON + email)
```

### Escalation Engine (Subsidiarity)
```
SEED → SPROUT → NOTICE → VIRTUE → COMMUNITY → DEMAND → CIVIL → HARVEST
```
Cannot skip stages unless severity >= 5 (imminent danger).

## Key Files
- `daily_runner.py` — Full daily intelligence cycle orchestrator
- `projects.json` — All 17 field definitions with prompts and laws
- `channels.json` — 15 data channel definitions
- `wheat/channels.py` — Channel pipeline logic
- `wheat/escalation.py` — Subsidiarity escalation engine + case tracking
- `wheat/grok_tasks.py` — Grok API daily scanning tasks
- `wheat/field_manager.py` — Field analysis orchestration
- `wheat/sower.py` — Task generation (strategist phase)
- `wheat/wheat_seed.py` — Seed execution (analyst phase)
- `wheat/providers.py` — LLM provider abstraction (Venice, Grok, Claude Code)
- `wheat/templates/` — Notice templates (first contact, demand letter, intake form)
- `app.py` — Flask web UI for field management
- `reports/briefings/` — Daily briefing output

## Usage
```
python daily_runner.py                    # Full daily cycle
python daily_runner.py --dry-run          # Preview what would run
python daily_runner.py --scan-only        # Grok scans only
python daily_runner.py --analyze-only     # Claude analysis only
python daily_runner.py --field fleet_compliance  # Single field
python daily_runner.py --report-only      # Briefing from existing data
python daily_runner.py --email            # Include email delivery
python daily_runner.py --channels         # Show channel status
python -m wheat.grok_tasks --list         # List all channels
python -m wheat.grok_tasks --dry-run      # Preview Grok scans
```

## Rules
- No Sunday runs (Sabbath rest)
- Subsidiarity: always try the lowest level first
- Never skip escalation stages without severity justification
- Community reports are the most valuable data source
- Shops advertising illegal mods are targets, not individual vehicle owners
- Focus on companies and entities, not individuals
- Civil remedies only — never criminal pursuit
- All evidence must be from public sources or voluntary reports
