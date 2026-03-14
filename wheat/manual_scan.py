#!/usr/bin/env python3
"""
Manual Scan Interface — Copy-paste stopgap for before full automation.

When you don't have API keys set up or want to manually run scans:
1. This script generates the prompts for each channel/field
2. You copy the prompt into Grok/ChatGPT/Claude
3. Paste the response back
4. The script parses it and deposits it into the intake pipeline

Usage:
  python -m wheat.manual_scan --list                    # List available prompts
  python -m wheat.manual_scan --channel google_reviews_auto  # Get prompt for a channel
  python -m wheat.manual_scan --field fleet_compliance  # Get prompt for a field
  python -m wheat.manual_scan --ingest fleet_compliance # Paste in a response

  # Or interactively:
  python -m wheat.manual_scan --interactive
"""

import json
import os
import sys
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from wheat.channels import load_channels, get_channels_for_field
from wheat.paths import load_projects, load_project_config
from wheat.scan_tasks import CHANNEL_PROMPTS

INTAKE_DIR = os.path.join(PROJECT_ROOT, "intake")
MANUAL_DIR = os.path.join(INTAKE_DIR, "manual_scans")


def get_channel_prompt(channel_id):
    """Generate the copy-paste prompt for a specific channel."""
    channels = load_channels()
    channel = channels.get(channel_id)
    if not channel:
        print(f"Channel '{channel_id}' not found.")
        return None

    channel_type = channel.get("channel_type", "NEWS")
    template = CHANNEL_PROMPTS.get(channel_type, CHANNEL_PROMPTS["NEWS"])
    sources_text = "\n".join(f"- {s}" for s in channel.get("sources", []))
    prompt = template.format(sources=sources_text)
    return prompt


def get_field_prompt(field_id):
    """Generate a combined scan prompt for all channels feeding a field."""
    projects = load_projects()
    if field_id not in projects:
        print(f"Field '{field_id}' not found.")
        return None

    field = projects[field_id]
    channels = get_channels_for_field(field_id)

    prompt = f"""You are an intelligence analyst scanning for issues related to: {field.get('name', field_id)}
{field.get('description', '')}

Jurisdiction: {field.get('jurisdiction', 'Englewood, CO')}

Sources to check:
"""
    for cid, cdata in channels.items():
        prompt += f"\n{cdata['name']}:\n"
        for src in cdata.get("sources", []):
            prompt += f"  - {src}\n"

    laws = field.get("laws", [])
    if laws:
        prompt += f"\nApplicable laws:\n"
        for law in laws:
            prompt += f"  - {law}\n"

    prompt += """
For each issue found, return a JSON array of signals:
[
  {
    "entity": "Business or entity name",
    "issue": "One-sentence description of the issue",
    "severity": 1-5,
    "source": "Where you found this",
    "law_cited": "Applicable law or regulation",
    "recommended_action": "What should be done",
    "escalation_stage": "seed"
  }
]

If no issues found, return an empty array: []
Return ONLY valid JSON, no other text.
"""
    return prompt


def save_manual_response(field_or_channel, response_text):
    """Parse and save a manually pasted response."""
    os.makedirs(MANUAL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Try to parse as JSON
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        signals = json.loads(response_text)
    except json.JSONDecodeError:
        signals = [{"raw_response": response_text, "parse_error": True}]
        print("Warning: Could not parse as JSON. Saved raw response.")

    result = {
        "source": field_or_channel,
        "scanned_at": datetime.now().isoformat(),
        "method": "manual_copy_paste",
        "signals": signals,
    }

    result_file = os.path.join(MANUAL_DIR, f"{field_or_channel}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    signal_count = len(signals) if isinstance(signals, list) else 0
    print(f"\nSaved {signal_count} signals to: {result_file}")
    return result_file


def interactive_mode():
    """Walk through fields interactively — generate prompt, accept paste."""
    projects = load_projects()

    print(f"\n{'='*60}")
    print(f"  MANUAL INTELLIGENCE SCAN")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    field_ids = list(projects.keys())
    for i, pid in enumerate(field_ids):
        print(f"  {i+1}. {pid}: {projects[pid].get('name', pid)}")

    print(f"\nEnter field number (or 'q' to quit): ", end="")
    choice = input().strip()
    if choice.lower() == 'q':
        return

    try:
        idx = int(choice) - 1
        field_id = field_ids[idx]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return

    prompt = get_field_prompt(field_id)
    if not prompt:
        return

    print(f"\n{'='*60}")
    print(f"  COPY THIS PROMPT INTO YOUR LLM:")
    print(f"{'='*60}\n")
    print(prompt)
    print(f"\n{'='*60}")
    print(f"  PASTE THE LLM RESPONSE BELOW (end with a line containing only 'END'):")
    print(f"{'='*60}\n")

    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)

    response = "\n".join(lines)
    if response.strip():
        save_manual_response(field_id, response)
    else:
        print("No response received.")

    print(f"\nScan another field? (y/n): ", end="")
    if input().strip().lower() == 'y':
        interactive_mode()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manual Intelligence Scan — Copy-Paste Interface")
    parser.add_argument("--list", action="store_true", help="List available fields and channels")
    parser.add_argument("--channel", help="Generate prompt for a specific channel")
    parser.add_argument("--field", help="Generate prompt for a specific field")
    parser.add_argument("--ingest", help="Paste a response for a field (reads from stdin)")
    parser.add_argument("--interactive", action="store_true", help="Interactive scan mode")
    args = parser.parse_args()

    if args.list:
        projects = load_projects()
        channels = load_channels()
        print(f"\nFields ({len(projects)}):")
        for pid, pdata in projects.items():
            field_channels = get_channels_for_field(pid)
            print(f"  {pid}: {pdata.get('name', pid)} ({len(field_channels)} channels)")
        print(f"\nChannels ({len(channels)}):")
        for cid, cdata in channels.items():
            print(f"  {cid}: {cdata['name']} [{cdata['channel_type']}]")

    elif args.channel:
        prompt = get_channel_prompt(args.channel)
        if prompt:
            print(f"\n{'='*60}")
            print(f"  PROMPT FOR: {args.channel}")
            print(f"  Copy this into Grok/ChatGPT/Claude:")
            print(f"{'='*60}\n")
            print(prompt)

    elif args.field:
        prompt = get_field_prompt(args.field)
        if prompt:
            print(f"\n{'='*60}")
            print(f"  PROMPT FOR: {args.field}")
            print(f"  Copy this into Grok/ChatGPT/Claude:")
            print(f"{'='*60}\n")
            print(prompt)

    elif args.ingest:
        print(f"Paste the LLM response for '{args.ingest}' (end with 'END' on its own line):")
        lines = []
        for line in sys.stdin:
            if line.strip() == "END":
                break
            lines.append(line.rstrip())
        response = "\n".join(lines)
        if response.strip():
            save_manual_response(args.ingest, response)
        else:
            print("No response received.")

    elif args.interactive:
        interactive_mode()

    else:
        parser.print_help()
