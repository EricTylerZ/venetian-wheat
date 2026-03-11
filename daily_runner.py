#!/usr/bin/env python3
"""
Daily Field Runner — Tends all active automotive accountability fields.

Runs each field's intelligence cycle:
  SCAN → FILTER → SEED → AGGREGATE → REPORT

Respects the Sabbath: no runs on Sunday.

Full daily cycle:
  1. SCAN       — Claude Sonnet scans channels (reviews, news, social, records)
  2. INGEST     — Route scan results to appropriate fields
  3. ANALYZE    — Claude Opus agents analyze signals per field
  4. CORRELATE  — Cross-field entity correlation
  5. ESCALATE   — Check cases ready for escalation
  6. BRIEF      — Generate daily intelligence briefing
  7. EMAIL      — Send briefing (optional)

Usage:
  python daily_runner.py                    # Full daily cycle
  python daily_runner.py --field fleet_compliance  # Run one field
  python daily_runner.py --scan-only        # Only run Grok scans
  python daily_runner.py --analyze-only     # Only run Claude analysis
  python daily_runner.py --dry-run          # Show what would run
  python daily_runner.py --report-only      # Generate briefing from existing data
  python daily_runner.py --email            # Email the daily briefing
"""

import argparse
import json
import os
import sys
import sqlite3
import threading
import time
from datetime import datetime, date

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from wheat.paths import load_projects, load_project_config, DB_PATH
from wheat.field_manager import FieldManager
from wheat.channels import load_channels, get_channels_for_field, channel_status_report
from wheat.escalation import daily_escalation_check, get_cross_field_entities, init_escalation_db
from wheat.scan_tasks import run_daily_scans, aggregate_scan_results
from tools.stewards_map import get_stewards_map, get_map_as_string

REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
BRIEFINGS_DIR = os.path.join(REPORTS_DIR, "briefings")


def is_sunday():
    """Check if today is Sunday (day of rest)."""
    return date.today().weekday() == 6


def get_field_status(project_id):
    """Get latest seed status for a field from the database."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute(
        "SELECT id FROM runs WHERE project_id = ? ORDER BY id DESC LIMIT 1",
        (project_id,),
    )
    run_row = c.fetchone()
    if not run_row:
        conn.close()
        return None

    c.execute(
        "SELECT seed_id, task, status, output, test_result FROM seeds WHERE run_id = ? AND project_id = ?",
        (run_row[0], project_id),
    )
    seeds = c.fetchall()
    conn.close()
    return {
        "run_id": run_row[0],
        "seeds": [
            {
                "seed_id": s[0],
                "task": s[1],
                "status": s[2],
                "output": json.loads(s[3]) if s[3] else [],
                "test_result": s[4] or "",
            }
            for s in seeds
        ],
    }


def run_field(project_id, config, guidance=None):
    """Run a single field's intelligence cycle."""
    print(f"\n{'='*60}")
    print(f"  TENDING FIELD: {config.get('name', project_id)}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    merged_config = load_project_config(project_id)

    # Build prompts with context
    stewards_map_str = get_map_as_string(
        include_params=True, include_descriptions=True
    )

    guidance = guidance or "Daily scan — check sources for new signals, review existing cases for escalation readiness."

    strategist_prompt = merged_config["strategist_prompt"].format(
        stewards_map=stewards_map_str,
        file_contents=stewards_map_str,
        seeds_per_run=merged_config["seeds_per_run"],
        guidance=guidance,
    )
    coder_prompt_template = merged_config["coder_prompt"].format(
        stewards_map=stewards_map_str,
        file_contents=stewards_map_str,
        task="{task}",
    )

    manager = FieldManager(project_id=project_id, config=merged_config)
    manager.sow_field(
        guidance,
        strategist_prompt=strategist_prompt,
        coder_prompt=coder_prompt_template,
    )

    # Run tend_field in a thread with a timeout
    tend_thread = threading.Thread(target=manager.tend_field, daemon=True)
    tend_thread.start()

    # Wait for seeds to complete or timeout
    timeout = merged_config.get("claude_code_timeout", 300) * merged_config.get("seeds_per_run", 2)
    start = time.time()
    while time.time() - start < timeout:
        if not manager.seeds:
            time.sleep(2)
            continue
        if all(s.progress["status"] in ("Fruitful", "Barren") for s in manager.seeds):
            break
        time.sleep(5)

    status = get_field_status(project_id)
    if status:
        fruitful = sum(1 for s in status["seeds"] if s["status"] == "Fruitful")
        barren = sum(1 for s in status["seeds"] if s["status"] == "Barren")
        print(f"  Result: {fruitful} fruitful, {barren} barren out of {len(status['seeds'])} seeds")
    else:
        print("  Result: No data")

    return status


def generate_briefing(results, run_date=None, scan_results=None, escalation_report=None):
    """Generate the daily intelligence briefing from all field results."""
    run_date = run_date or date.today().isoformat()
    os.makedirs(BRIEFINGS_DIR, exist_ok=True)

    total_signals = 0
    total_fruitful = 0
    total_barren = 0
    field_summaries = []

    for project_id, status in results.items():
        if not status:
            field_summaries.append(f"  {project_id}: No data")
            continue
        fruitful = sum(1 for s in status["seeds"] if s["status"] == "Fruitful")
        barren = sum(1 for s in status["seeds"] if s["status"] == "Barren")
        total_fruitful += fruitful
        total_barren += barren
        total_signals += len(status["seeds"])
        field_summaries.append(
            f"  {project_id}: {fruitful} fruitful / {barren} barren / {len(status['seeds'])} total"
        )

    # Scan results summary
    scan_summary = ""
    if scan_results:
        channels_scanned = len([r for r in scan_results.values() if r])
        total_scan_signals = sum(
            len(r.get("signals", [])) for r in scan_results.values()
            if r and isinstance(r.get("signals"), list)
        )
        scan_summary = f"""
GROK CHANNEL SCANS
  Channels scanned: {channels_scanned}
  Signals detected: {total_scan_signals}
"""

    # Escalation summary
    esc_summary = ""
    if escalation_report:
        esc_summary = f"""
ESCALATION STATUS
{escalation_report}
"""

    briefing = f"""
================================================================================
  DAILY INTELLIGENCE BRIEFING — {run_date}
  Venetian Wheat Automotive Accountability — Englewood, CO
================================================================================
{scan_summary}
FIELD ANALYSIS
  Fields analyzed: {len(results)}
  Total seeds: {total_signals}
  Fruitful: {total_fruitful}
  Barren: {total_barren}

FIELD DETAIL
{chr(10).join(field_summaries)}
{esc_summary}
"""

    # Add detailed output from fruitful seeds
    for project_id, status in results.items():
        if not status:
            continue
        fruitful_seeds = [s for s in status["seeds"] if s["status"] == "Fruitful"]
        if fruitful_seeds:
            briefing += f"\n--- {project_id.upper()} ---\n"
            for seed in fruitful_seeds:
                briefing += f"  Task: {seed['task']}\n"
                if seed["output"]:
                    briefing += f"  Output: {seed['output'][-1][:200]}\n"
                briefing += "\n"

    briefing += f"""
================================================================================
  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  Next run: {'Monday' if is_sunday() else 'Tomorrow'} (no Sunday runs)
================================================================================
"""

    # Save briefing
    briefing_file = os.path.join(BRIEFINGS_DIR, f"briefing_{run_date}.txt")
    with open(briefing_file, "w", encoding="utf-8") as f:
        f.write(briefing)

    # Also save as JSON for machine parsing
    briefing_json = {
        "date": run_date,
        "fields_scanned": len(results),
        "total_seeds": total_signals,
        "total_fruitful": total_fruitful,
        "total_barren": total_barren,
        "fields": {},
    }
    for project_id, status in results.items():
        if not status:
            briefing_json["fields"][project_id] = {"status": "no_data"}
            continue
        briefing_json["fields"][project_id] = {
            "seeds": status["seeds"],
            "fruitful": sum(1 for s in status["seeds"] if s["status"] == "Fruitful"),
            "barren": sum(1 for s in status["seeds"] if s["status"] == "Barren"),
        }
    json_file = os.path.join(BRIEFINGS_DIR, f"briefing_{run_date}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(briefing_json, f, indent=2)

    print(briefing)
    print(f"Briefing saved to: {briefing_file}")
    print(f"JSON saved to: {json_file}")

    return briefing, briefing_file


def send_email_briefing(briefing_text, briefing_file):
    """Send the daily briefing via email (uses system mail or configurable)."""
    email_config_path = os.path.join(PROJECT_ROOT, "email_config.json")
    if not os.path.exists(email_config_path):
        print("No email_config.json found. To enable email briefings, create it with:")
        print('  {"to": "you@example.com", "from": "wheat@yourdomain.com", "method": "smtp", "smtp_host": "...", "smtp_port": 587}')
        return

    with open(email_config_path, "r") as f:
        email_config = json.load(f)

    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(briefing_text)
    msg["Subject"] = f"Wheat Daily Briefing — {date.today().isoformat()}"
    msg["From"] = email_config.get("from", "wheat@localhost")
    msg["To"] = email_config["to"]

    try:
        if email_config.get("method") == "smtp":
            with smtplib.SMTP(email_config["smtp_host"], email_config.get("smtp_port", 587)) as server:
                server.starttls()
                if email_config.get("smtp_user"):
                    server.login(email_config["smtp_user"], email_config["smtp_pass"])
                server.send_message(msg)
            print(f"Briefing emailed to {email_config['to']}")
        else:
            # Fallback: save to outbox for manual send
            outbox_dir = os.path.join(REPORTS_DIR, "outbox")
            os.makedirs(outbox_dir, exist_ok=True)
            outbox_file = os.path.join(outbox_dir, f"briefing_{date.today().isoformat()}.eml")
            with open(outbox_file, "w") as f:
                f.write(msg.as_string())
            print(f"Briefing saved to outbox: {outbox_file}")
    except Exception as e:
        print(f"Email failed: {e}")
        print("Briefing is still saved locally.")


def main():
    parser = argparse.ArgumentParser(description="Daily Field Runner — Automotive Accountability Intelligence")
    parser.add_argument("--field", help="Run a specific field only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without running")
    parser.add_argument("--scan-only", action="store_true", help="Only run Grok channel scans")
    parser.add_argument("--analyze-only", action="store_true", help="Only run Claude field analysis")
    parser.add_argument("--report-only", action="store_true", help="Generate briefing from existing data")
    parser.add_argument("--email", action="store_true", help="Email the daily briefing")
    parser.add_argument("--guidance", help="Custom guidance for today's run")
    parser.add_argument("--force-sunday", action="store_true", help="Override Sunday check")
    parser.add_argument("--channels", action="store_true", help="Show channel status")
    args = parser.parse_args()

    # Sunday check
    if is_sunday() and not args.force_sunday:
        print("Today is Sunday. We rest on the Sabbath.")
        print("Use --force-sunday to override.")
        sys.exit(0)

    # Channel status
    if args.channels:
        print(f"\n{'='*60}")
        print("  INTELLIGENCE CHANNELS")
        print(f"{'='*60}\n")
        print(channel_status_report())
        sys.exit(0)

    # Initialize escalation DB
    init_escalation_db()

    projects = load_projects()
    automotive_fields = {
        pid: pdata
        for pid, pdata in projects.items()
        if pdata.get("active", False)
    }

    if args.field:
        if args.field not in automotive_fields:
            print(f"Field '{args.field}' not found. Available fields:")
            for pid in automotive_fields:
                print(f"  - {pid}")
            sys.exit(1)
        automotive_fields = {args.field: automotive_fields[args.field]}

    if args.dry_run:
        print(f"\nDRY RUN — Full daily cycle preview\n")

        print(f"PHASE 1: CHANNEL SCANS (Sonnet)")
        channels = load_channels()
        daily_channels = {cid: c for cid, c in channels.items() if c.get("frequency") == "daily"}
        weekly_channels = {cid: c for cid, c in channels.items() if c.get("frequency") == "weekly"}
        print(f"  Daily channels: {len(daily_channels)}")
        for cid, cdata in daily_channels.items():
            print(f"    {cid}: {cdata['name']} → {', '.join(cdata.get('fields', []))}")
        if date.today().weekday() == 0:
            print(f"  Weekly channels (Monday): {len(weekly_channels)}")
            for cid, cdata in weekly_channels.items():
                print(f"    {cid}: {cdata['name']} → {', '.join(cdata.get('fields', []))}")

        print(f"\nPHASE 2: FIELD ANALYSIS — {len(automotive_fields)} fields")
        for pid, pdata in automotive_fields.items():
            field_channels = get_channels_for_field(pid)
            print(f"  {pid}: {pdata.get('name', pid)}")
            print(f"    Seeds/run: {pdata.get('seeds_per_run', 2)} | Provider: {pdata.get('llm_api', 'claude_code')}")
            print(f"    Fed by {len(field_channels)} channels")

        print(f"\nPHASE 3: CORRELATION & ESCALATION")
        print(f"  Cross-field entity check")
        print(f"  Escalation deadline check")
        sys.exit(0)

    if args.report_only:
        results = {}
        for pid in automotive_fields:
            results[pid] = get_field_status(pid)
        briefing_text, briefing_file = generate_briefing(results)
        if args.email:
            send_email_briefing(briefing_text, briefing_file)
        sys.exit(0)

    # ===== FULL DAILY CYCLE =====
    print(f"\n{'#'*60}")
    print(f"  VENETIAN WHEAT — DAILY INTELLIGENCE RUN")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Fields: {len(automotive_fields)} | Channels: {len(load_channels())}")
    print(f"{'#'*60}")

    # ----- PHASE 1: CHANNEL SCANS (Sonnet) -----
    scan_results = {}
    if not args.analyze_only:
        print(f"\n{'='*60}")
        print(f"  PHASE 1: CHANNEL SCANS (Claude Sonnet)")
        print(f"{'='*60}")
        scan_results = run_daily_scans(dry_run=False)
        scan_summary, signals_by_field = aggregate_scan_results(scan_results)
        print(f"\n{scan_summary}")

    if args.scan_only:
        print("Scan-only mode — skipping field analysis.")
        sys.exit(0)

    # ----- PHASE 2: FIELD ANALYSIS -----
    print(f"\n{'='*60}")
    print(f"  PHASE 2: FIELD ANALYSIS (Claude Code Agents)")
    print(f"{'='*60}")

    # Initialize stewards map once
    get_stewards_map(include_params=True, include_descriptions=True)

    # Build guidance that includes scan results for each field
    results = {}
    for pid, pdata in automotive_fields.items():
        # Enrich guidance with Grok scan results for this field
        field_guidance = args.guidance or "Daily scan — check sources for new signals."

        # Check if we have Grok scan data for this field
        if scan_results:
            field_scan_data = []
            for cid, scan in scan_results.items():
                if scan and pid in scan.get("target_fields", []):
                    signals = scan.get("signals", [])
                    if isinstance(signals, list) and signals:
                        field_scan_data.extend(signals)
            if field_scan_data:
                field_guidance += f"\n\nGrok scan found {len(field_scan_data)} signals for this field today:\n"
                for sig in field_scan_data[:5]:  # Top 5 signals
                    if isinstance(sig, dict):
                        field_guidance += f"- {json.dumps(sig)[:200]}\n"

        try:
            results[pid] = run_field(pid, pdata, guidance=field_guidance)
        except Exception as e:
            print(f"  ERROR in {pid}: {e}")
            results[pid] = None

    # ----- PHASE 3: CORRELATION & ESCALATION -----
    print(f"\n{'='*60}")
    print(f"  PHASE 3: CORRELATION & ESCALATION CHECK")
    print(f"{'='*60}")

    escalation_report = daily_escalation_check()
    print(escalation_report)

    cross_field = get_cross_field_entities()
    if cross_field:
        print(f"\n  CROSS-FIELD ALERTS:")
        for entity in cross_field:
            print(f"    {entity['entity']}: flagged in {entity['field_count']} fields — AUTO-ESCALATION CANDIDATE")

    # ----- PHASE 4: BRIEFING -----
    briefing_text, briefing_file = generate_briefing(results, scan_results=scan_results, escalation_report=escalation_report)
    if args.email:
        send_email_briefing(briefing_text, briefing_file)


if __name__ == "__main__":
    main()
