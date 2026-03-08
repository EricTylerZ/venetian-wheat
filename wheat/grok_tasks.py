"""
Grok Daily Tasks — Automated intelligence gathering via Grok API.

These tasks run daily (Mon-Sat) via cron or manual trigger, using the Grok
(xAI) API for web-aware scanning. Each task queries a channel's sources,
extracts signals, and deposits structured output into the intake pipeline
for the relevant fields to process.

Grok is ideal for this because it has web access and real-time awareness.
Claude Code agents then do the deeper analysis on the ingested data.

Architecture:
  Grok (scanner) → intake/ → Claude Code agents (analyst) → cases → escalation

Usage:
  python -m wheat.grok_tasks                    # Run all daily tasks
  python -m wheat.grok_tasks --channel google_reviews_auto  # One channel
  python -m wheat.grok_tasks --list             # List all tasks
  python -m wheat.grok_tasks --email            # Include results in email
"""

import json
import os
import sys
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from wheat.channels import load_channels, get_fields_for_channel
from wheat.providers import APIProvider

INTAKE_DIR = os.path.join(PROJECT_ROOT, "intake")
GROK_RESULTS_DIR = os.path.join(PROJECT_ROOT, "intake", "grok_scans")

# Grok scanning prompts per channel type
CHANNEL_PROMPTS = {
    "REVIEWS": """You are an intelligence scanner monitoring consumer reviews for automotive businesses in Englewood, Colorado (zip codes 80110, 80111, 80112).

Search for recent Google/Yelp/BBB reviews and complaints about: {sources}

Focus on reviews that mention:
- Fraud, deception, or dishonesty
- Overcharging or hidden fees
- Damage to vehicles
- Illegal practices or violations
- Safety concerns
- Refusal to provide estimates or receipts

For each relevant complaint found, extract:
- Business name and location
- Date of review (approximate)
- Key complaint (one sentence)
- Specific law or regulation potentially violated
- Severity (1-5, where 5 is most severe)
- Source URL if available

Output as JSON array of signals. If no relevant reviews found, return empty array.
Return ONLY valid JSON, no other text.""",

    "REGULATORY": """You are an intelligence scanner monitoring regulatory databases for automotive compliance in Colorado, focusing on Englewood area.

Check these sources for recent activity: {sources}

Look for:
- New complaints filed
- Enforcement actions taken
- Violations recorded
- License suspensions or revocations
- Fines or penalties

For each finding, extract:
- Entity name
- Type of violation or action
- Date
- Specific regulation cited
- Severity (1-5)
- Source URL

Output as JSON array. Return ONLY valid JSON.""",

    "NEWS": """You are an intelligence scanner monitoring local news for automotive safety issues in Englewood, Colorado and the South Denver metro area.

Scan these sources for recent stories: {sources}

Look for stories about:
- Traffic accidents, especially involving commercial vehicles
- Consumer complaints about auto businesses
- Legislative changes affecting automotive regulation
- Enforcement actions or crackdowns
- School zone safety concerns
- Pedestrian or cyclist incidents
- Tow company controversies
- Auto dealer fraud cases

For each relevant story, extract:
- Headline/title
- Source and date
- Key entities mentioned
- Relevance to which field (fleet_compliance, tow_companies, used_car_dealers, etc.)
- Severity of issue (1-5)
- URL

Output as JSON array. Return ONLY valid JSON.""",

    "SOCIAL": """You are an intelligence scanner monitoring social media and community forums for automotive safety concerns in Englewood, Colorado.

Scan these sources: {sources}

Look for:
- Complaints about specific businesses or vehicles
- Reports of dangerous driving or unsafe conditions
- Auto shops advertising illegal modifications (muffler deletes, illegal tint, DPF deletes)
- Community frustration about noise, speeding, or safety
- Patterns of repeated complaints about the same entity

For each relevant post/comment, extract:
- Platform and approximate date
- Key complaint or concern
- Entity mentioned (if any)
- Location mentioned
- Relevance to which field
- Severity (1-5)

Output as JSON array. Return ONLY valid JSON.""",

    "PUBLIC_RECORDS": """You are an intelligence scanner checking public records for automotive compliance in Englewood, Colorado and Arapahoe County.

Check these sources: {sources}

Look for:
- Expired registrations or licenses
- Lapsed insurance
- Failed inspections
- Outstanding violations
- New filings or records

For each finding, extract:
- Entity name
- Record type
- Issue identified
- Applicable law or regulation
- Severity (1-5)
- Source

Output as JSON array. Return ONLY valid JSON.""",

    "COURT": """You are an intelligence scanner monitoring court records in Arapahoe County, Colorado for automotive-related civil cases.

Check: {sources}

Look for:
- Lawsuits against auto dealers, repair shops, tow companies
- Consumer protection cases
- Insurance disputes
- Lemon law cases
- Wage theft in auto industry
- Pattern litigants (same defendant multiple times)

For each relevant case, extract:
- Case number (if available)
- Parties involved
- Nature of complaint
- Filing date
- Relevance to which field
- Severity (1-5)

Output as JSON array. Return ONLY valid JSON.""",
}


def run_grok_scan(channel_id, channel_data, dry_run=False):
    """Run a Grok scan for a specific channel."""
    channel_type = channel_data.get("channel_type", "NEWS")
    prompt_template = CHANNEL_PROMPTS.get(channel_type, CHANNEL_PROMPTS["NEWS"])

    sources_text = "\n".join(f"- {s}" for s in channel_data.get("sources", []))
    prompt = prompt_template.format(sources=sources_text)

    if dry_run:
        print(f"  [DRY RUN] Would scan: {channel_data['name']}")
        print(f"  Type: {channel_type}")
        print(f"  Sources: {len(channel_data.get('sources', []))}")
        print(f"  Feeds fields: {', '.join(channel_data.get('fields', []))}")
        return None

    print(f"  Scanning: {channel_data['name']}...")

    # Use Grok provider
    grok_config = {
        "llm_api": "grok",
        "grok_api_url": "https://api.xai.com/grok/v1/chat",
    }

    try:
        provider = APIProvider(
            api_url=grok_config["grok_api_url"],
            api_type="grok",
        )

        text, usage = provider.generate(
            prompt=prompt,
            model="grok-3-mini",
            max_tokens=4000,
        )

        # Parse response
        try:
            # Try to extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            signals = json.loads(text)
        except json.JSONDecodeError:
            signals = [{"raw_response": text, "parse_error": True}]

        # Save scan results
        os.makedirs(GROK_RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(
            GROK_RESULTS_DIR, f"{channel_id}_{timestamp}.json"
        )
        result = {
            "channel_id": channel_id,
            "channel_name": channel_data["name"],
            "channel_type": channel_type,
            "scanned_at": datetime.now().isoformat(),
            "target_fields": channel_data.get("fields", []),
            "signals": signals,
            "token_usage": usage,
        }
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

        signal_count = len(signals) if isinstance(signals, list) else 0
        print(f"    Found {signal_count} signals → {result_file}")
        return result

    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def run_daily_scans(channel_filter=None, dry_run=False):
    """Run all daily Grok scans."""
    if date.today().weekday() == 6:
        print("Sunday — no scans today.")
        return {}

    channels = load_channels()
    results = {}

    # Filter to daily-frequency channels (or the specific one requested)
    for cid, cdata in channels.items():
        if channel_filter and cid != channel_filter:
            continue
        freq = cdata.get("frequency", "daily")
        if freq == "daily" or channel_filter:
            results[cid] = run_grok_scan(cid, cdata, dry_run=dry_run)
        elif freq == "weekly" and date.today().weekday() == 0:
            # Run weekly channels on Mondays
            results[cid] = run_grok_scan(cid, cdata, dry_run=dry_run)

    return results


def aggregate_scan_results(results):
    """Aggregate scan results into a summary for the daily briefing."""
    total_signals = 0
    by_field = {}

    for cid, result in results.items():
        if not result or not result.get("signals"):
            continue
        signals = result["signals"]
        if isinstance(signals, list):
            total_signals += len(signals)
            for field in result.get("target_fields", []):
                if field not in by_field:
                    by_field[field] = []
                by_field[field].extend(signals)

    summary = f"Grok Scan Summary — {date.today().isoformat()}\n"
    summary += f"  Channels scanned: {len(results)}\n"
    summary += f"  Total signals: {total_signals}\n"
    if by_field:
        summary += f"  Signals by field:\n"
        for field, signals in sorted(by_field.items()):
            summary += f"    {field}: {len(signals)} signals\n"

    return summary, by_field


def get_pending_intake():
    """List unprocessed intake files from Grok scans."""
    if not os.path.exists(GROK_RESULTS_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(GROK_RESULTS_DIR) if f.endswith(".json")],
        reverse=True,
    )
    return [os.path.join(GROK_RESULTS_DIR, f) for f in files]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grok Daily Intelligence Scans")
    parser.add_argument("--channel", help="Scan a specific channel only")
    parser.add_argument("--list", action="store_true", help="List all channels")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    args = parser.parse_args()

    if args.list:
        channels = load_channels()
        print(f"\nConfigured Channels ({len(channels)}):\n")
        for cid, cdata in channels.items():
            freq = cdata.get("frequency", "daily")
            print(f"  {cid}")
            print(f"    {cdata['name']}")
            print(f"    Type: {cdata['channel_type']} | Freq: {freq}")
            print(f"    Feeds: {', '.join(cdata.get('fields', []))}")
            print()
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  GROK DAILY INTELLIGENCE SCAN")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    results = run_daily_scans(channel_filter=args.channel, dry_run=args.dry_run)

    if not args.dry_run:
        summary, by_field = aggregate_scan_results(results)
        print(f"\n{summary}")
