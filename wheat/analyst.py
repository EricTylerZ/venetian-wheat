"""
Analyst Brain — LLM-powered intelligence synthesis layer.

Sits between scanning (Phase 1) and field analysis (Phase 2) in the daily cycle.
Reviews ALL scan signals across all channels, deduplicates, cross-references
entities, and produces enriched per-field intake with prioritized signals.

Also powers the Phase 4 briefing: synthesizes all field results, escalation
state, and cross-field patterns into an actual intelligence narrative.

Current provider: Claude Code Pro Max (Opus) via ClaudeCodeProvider.
The analyst_provider() factory is designed to be swappable — if a better LLM
comes along or costs change, update get_analyst_provider() to route elsewhere.
The rest of the pipeline doesn't care which LLM powers the analyst.

Architecture:
  Sonnet (scanner) → Analyst Brain (Opus) → Field Seeds (Opus) → Briefing (Opus)
"""

import json
import os
from datetime import date, datetime

from wheat.providers import get_provider, ClaudeCodeProvider

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def get_analyst_provider(config=None):
    """
    Factory for the analyst LLM provider.

    Currently returns ClaudeCodeProvider with Opus (default CLI model).
    To switch to a different provider in the future, change this function.
    The rest of the analyst pipeline is provider-agnostic — it only calls
    provider.generate(prompt, ...) and expects (text, usage_dict) back.

    Examples of future swaps:
      - A cheaper/faster model for overnight batch runs
      - A different API provider if Claude Code pricing changes
      - A local model for sensitive data that shouldn't leave the machine
    """
    if config and config.get("analyst_provider"):
        # Allow explicit override via config
        return get_provider(config["analyst_provider"])

    # Default: Claude Code CLI with Opus (deepest reasoning for synthesis)
    analyst_model = None  # None = CLI default (currently Opus)
    if config:
        analyst_model = config.get("analyst_model")
    return ClaudeCodeProvider(timeout=600, model=analyst_model)


# ---------------------------------------------------------------------------
# Phase 1.5: Scan Correlation — review all Sonnet scan results with Opus
# ---------------------------------------------------------------------------

CORRELATION_PROMPT = """You are an intelligence analyst for the Venetian Wheat automotive accountability platform in Englewood, Colorado.

You have received raw scan signals from multiple intelligence channels. Your job is to:

1. DEDUPLICATE: Identify signals that refer to the same entity or incident across channels
2. CROSS-REFERENCE: Flag entities that appear in multiple channels (higher confidence)
3. ENRICH: For each signal, note which specific Colorado laws or regulations may apply
4. PRIORITIZE: Assign a confidence score (1-5) based on source quality and corroboration
5. ROUTE: Assign each signal to the correct field(s) for deeper analysis

Fields available: fleet_compliance, tow_companies, used_car_dealers, dealer_financing,
auto_repair, auto_insurance, school_zone_safety, pedestrian_cyclist, commercial_trucking,
rideshare_delivery, parking_booting, emissions_environmental, road_intersection_safety,
title_registration, exhaust_noise, window_tint

Rules:
- Focus on COMPANIES and ENTITIES, not individual vehicle owners
- Shops advertising illegal mods are targets (not customers)
- Civil remedies only — never criminal pursuit
- Community reports are the most valuable data source
- Flag any severity >= 4 signals for immediate attention

Here are today's raw scan results from all channels:

{scan_data}

{existing_cases}

Produce a JSON response with this structure:
{{
  "analysis_date": "{run_date}",
  "total_raw_signals": <count>,
  "deduplicated_signals": <count>,
  "cross_channel_entities": [
    {{
      "entity": "<name>",
      "channels_seen": ["<channel_id>", ...],
      "signals": ["<summary>", ...],
      "recommended_fields": ["<field_id>", ...],
      "confidence": <1-5>,
      "severity": <1-5>,
      "laws_applicable": ["<law>", ...],
      "immediate_attention": <true/false>
    }}
  ],
  "field_intake": {{
    "<field_id>": [
      {{
        "entity": "<name>",
        "signal_summary": "<one sentence>",
        "source_channels": ["<channel_id>", ...],
        "confidence": <1-5>,
        "severity": <1-5>,
        "law_cited": "<specific law or regulation>",
        "recommended_action": "<what the field agent should investigate>"
      }}
    ]
  }},
  "immediate_alerts": [
    "<any severity >= 4 findings that need same-day attention>"
  ],
  "analyst_notes": "<brief overall assessment of today's intelligence picture>"
}}

Return ONLY valid JSON."""


def correlate_scans(scan_results, existing_cases=None, config=None):
    """
    Phase 1.5: Analyst Brain reviews all scan results, deduplicates,
    cross-references, and produces enriched per-field intake.

    Args:
        scan_results: dict of channel_id -> scan result from run_daily_scans()
        existing_cases: optional list of active cases for context
        config: optional config dict (for provider override)

    Returns:
        (analysis_dict, raw_text) — parsed JSON analysis and raw LLM response
    """
    # Build scan data summary for the prompt
    scan_data_parts = []
    total_signals = 0
    for cid, result in scan_results.items():
        if not result:
            continue
        signals = result.get("signals", [])
        if not isinstance(signals, list):
            continue
        total_signals += len(signals)
        scan_data_parts.append(
            f"\n--- Channel: {result.get('channel_name', cid)} ({result.get('channel_type', 'UNKNOWN')}) ---\n"
            f"Signals ({len(signals)}):\n"
            + json.dumps(signals, indent=2)
        )

    if total_signals == 0:
        print("  Analyst: No signals to correlate.")
        return {"field_intake": {}, "analyst_notes": "No signals detected today."}, ""

    scan_data_text = "\n".join(scan_data_parts)

    # Include existing cases for context (so analyst knows what's already tracked)
    cases_text = ""
    if existing_cases:
        cases_summary = []
        for case in existing_cases[:20]:  # Cap at 20 to keep prompt reasonable
            cases_summary.append(
                f"  - Case #{case['id']}: {case['entity']} ({case['field']}) "
                f"— stage: {case['stage']}, severity: {case['severity']}"
            )
        cases_text = (
            "\nExisting active cases (for dedup — don't re-create these, add evidence instead):\n"
            + "\n".join(cases_summary)
        )

    prompt = CORRELATION_PROMPT.format(
        scan_data=scan_data_text,
        existing_cases=cases_text,
        run_date=date.today().isoformat(),
    )

    print(f"  Analyst: Correlating {total_signals} signals across {len(scan_data_parts)} channels...")

    provider = get_analyst_provider(config)
    try:
        text, usage = provider.generate(prompt=prompt, max_tokens=8000)

        # Parse JSON from response
        try:
            if "```json" in text:
                text_clean = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text_clean = text.split("```")[1].split("```")[0].strip()
            else:
                text_clean = text.strip()
            analysis = json.loads(text_clean)
        except json.JSONDecodeError:
            print("  Analyst: Warning — could not parse JSON response, returning raw text.")
            analysis = {
                "field_intake": {},
                "analyst_notes": text[:500],
                "parse_error": True,
            }

        # Save analysis
        analysis_dir = os.path.join(PROJECT_ROOT, "intake", "analysis")
        os.makedirs(analysis_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_file = os.path.join(analysis_dir, f"correlation_{date.today().isoformat()}_{timestamp}.json")
        with open(analysis_file, "w") as f:
            json.dump(analysis, f, indent=2)
        print(f"  Analyst: Correlation saved to {analysis_file}")

        # Report immediate alerts
        alerts = analysis.get("immediate_alerts", [])
        if alerts:
            print(f"  Analyst: {len(alerts)} IMMEDIATE ALERT(S):")
            for alert in alerts:
                print(f"    !! {alert}")

        return analysis, text

    except Exception as e:
        print(f"  Analyst: ERROR in correlation — {e}")
        return {"field_intake": {}, "analyst_notes": f"Correlation failed: {e}"}, ""


def build_field_guidance(field_id, analysis):
    """
    Extract enriched guidance for a specific field from the analyst's correlation.

    Returns a guidance string that replaces the old truncated-JSON-snippets approach.
    """
    field_intake = analysis.get("field_intake", {}).get(field_id, [])
    if not field_intake:
        return "Daily scan — no new signals detected for this field today. Review existing cases for escalation readiness."

    lines = [f"Analyst identified {len(field_intake)} signal(s) for this field today:\n"]
    for sig in field_intake:
        lines.append(f"- Entity: {sig.get('entity', 'Unknown')}")
        lines.append(f"  Signal: {sig.get('signal_summary', 'N/A')}")
        lines.append(f"  Confidence: {sig.get('confidence', '?')}/5 | Severity: {sig.get('severity', '?')}/5")
        if sig.get("law_cited"):
            lines.append(f"  Law: {sig['law_cited']}")
        if sig.get("recommended_action"):
            lines.append(f"  Action: {sig['recommended_action']}")
        if sig.get("source_channels"):
            lines.append(f"  Sources: {', '.join(sig['source_channels'])}")
        lines.append("")

    # Cross-channel entities relevant to this field
    cross = analysis.get("cross_channel_entities", [])
    relevant_cross = [e for e in cross if field_id in e.get("recommended_fields", [])]
    if relevant_cross:
        lines.append("Cross-channel entities flagged for this field:")
        for entity in relevant_cross:
            lines.append(
                f"  - {entity['entity']} (seen in {len(entity.get('channels_seen', []))} channels, "
                f"confidence {entity.get('confidence', '?')}/5)"
            )
        lines.append("")

    analyst_notes = analysis.get("analyst_notes", "")
    if analyst_notes:
        lines.append(f"Analyst notes: {analyst_notes}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 4: Briefing Synthesis — Opus writes the actual intelligence narrative
# ---------------------------------------------------------------------------

BRIEFING_PROMPT = """You are the intelligence briefing officer for the Venetian Wheat automotive accountability platform in Englewood, Colorado.

Write today's daily intelligence briefing. Be concise, actionable, and direct.

Date: {run_date}

SCAN RESULTS (Phase 1):
{scan_summary}

COMMUNITY REPORTS (most valuable source):
{community_reports}

ANALYST CORRELATION (Phase 1.5):
{correlation_summary}

FIELD ANALYSIS RESULTS (Phase 2):
{field_results}

ESCALATION STATUS (Phase 3):
{escalation_report}

CROSS-FIELD PATTERNS:
{cross_field}

Write the briefing in this format:

# DAILY INTELLIGENCE BRIEFING — {run_date}
## Venetian Wheat — Englewood, CO Automotive Accountability

### Executive Summary
(2-3 sentences: what happened today, what matters most, what needs action)

### Immediate Attention Required
(Any severity >= 4 findings or escalation-ready cases. If none, say "None today.")

### Key Findings by Field
(Only fields with actual findings — skip empty ones. For each, 1-2 bullet points.)

### Cross-Field Patterns
(Entities appearing in multiple fields. If none, say "No new patterns detected.")

### Escalation Status
(Cases ready to move up, approaching deadlines, or newly created.)

### Analyst Assessment
(Brief overall picture: is the intelligence picture improving? Any blind spots? Recommendations for tomorrow's scan focus.)

---
Generated: {timestamp}
Next run: {next_run}

Keep the entire briefing under 800 words. Be specific — name entities, cite laws, give dates."""


def synthesize_briefing(
    scan_results=None,
    correlation_analysis=None,
    field_results=None,
    escalation_report=None,
    cross_field_entities=None,
    config=None,
):
    """
    Phase 4: Have the analyst LLM write an actual intelligence briefing
    instead of just counting fruitful/barren seeds.

    Returns (briefing_text, briefing_file_path)
    """
    run_date = date.today().isoformat()
    reports_dir = os.path.join(PROJECT_ROOT, "reports", "briefings")
    os.makedirs(reports_dir, exist_ok=True)

    # Build scan summary
    scan_summary = "No scans run today."
    if scan_results:
        channels_scanned = len([r for r in scan_results.values() if r])
        total_signals = sum(
            len(r.get("signals", [])) for r in scan_results.values()
            if r and isinstance(r.get("signals"), list)
        )
        scan_summary = f"Scanned {channels_scanned} channels, detected {total_signals} raw signals."

    # Community reports (direct resident intake — most valuable source)
    community_reports_text = "No community reports received today."
    intake_dir = os.path.join(PROJECT_ROOT, "intake")
    if os.path.exists(intake_dir):
        today_reports = []
        for fname in sorted(os.listdir(intake_dir)):
            if fname.startswith("report_") and fname.endswith(".json") and run_date.replace("-", "") in fname:
                try:
                    with open(os.path.join(intake_dir, fname), "r") as f:
                        report = json.load(f)
                    today_reports.append(report)
                except (json.JSONDecodeError, IOError):
                    continue
        if today_reports:
            parts = [f"{len(today_reports)} report(s) received today:"]
            for r in today_reports:
                entity = r.get("entity", "Unknown")
                cat = r.get("category", "unknown")
                sev = r.get("severity", "?")
                loc = r.get("location", "")
                desc = r.get("description", "")[:150]
                parts.append(f"  - Entity: {entity} | Category: {cat} | Severity: {sev} | Location: {loc}\n    {desc}")
            community_reports_text = "\n".join(parts)

    # Correlation summary
    correlation_summary = "No correlation analysis performed."
    if correlation_analysis:
        deduped = correlation_analysis.get("deduplicated_signals", "?")
        cross_ents = len(correlation_analysis.get("cross_channel_entities", []))
        alerts = len(correlation_analysis.get("immediate_alerts", []))
        notes = correlation_analysis.get("analyst_notes", "")
        correlation_summary = (
            f"Deduplicated to {deduped} signals. "
            f"{cross_ents} cross-channel entities identified. "
            f"{alerts} immediate alert(s).\n"
            f"Analyst notes: {notes}"
        )

    # Field results summary
    field_summary_parts = []
    if field_results:
        for pid, status in field_results.items():
            if not status:
                continue
            seeds = status.get("seeds", [])
            fruitful = sum(1 for s in seeds if s.get("status") == "Fruitful")
            barren = sum(1 for s in seeds if s.get("status") == "Barren")
            if fruitful == 0 and barren == 0:
                continue
            field_summary_parts.append(f"  {pid}: {fruitful} fruitful / {barren} barren / {len(seeds)} total")
            for s in seeds:
                if s.get("status") == "Fruitful" and s.get("output"):
                    last_output = s["output"][-1] if isinstance(s["output"], list) else str(s["output"])
                    field_summary_parts.append(f"    → {str(last_output)[:200]}")
    field_results_text = "\n".join(field_summary_parts) if field_summary_parts else "No field analysis data available."

    # Cross-field
    cross_field_text = "No cross-field patterns detected."
    if cross_field_entities:
        parts = []
        for entity in cross_field_entities:
            parts.append(
                f"  {entity['entity']}: {entity['field_count']} fields "
                f"({', '.join(entity['fields'])}) — Max severity: {entity['max_severity']}"
            )
        cross_field_text = "\n".join(parts)

    prompt = BRIEFING_PROMPT.format(
        run_date=run_date,
        scan_summary=scan_summary,
        community_reports=community_reports_text,
        correlation_summary=correlation_summary,
        field_results=field_results_text,
        escalation_report=escalation_report or "No escalation data.",
        cross_field=cross_field_text,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        next_run="Monday" if date.today().weekday() == 5 else "Tomorrow",
    )

    print(f"\n  Analyst: Writing intelligence briefing...")

    provider = get_analyst_provider(config)
    try:
        briefing_text, usage = provider.generate(prompt=prompt, max_tokens=4000)

        # Save briefing
        briefing_file = os.path.join(reports_dir, f"briefing_{run_date}.md")
        with open(briefing_file, "w", encoding="utf-8") as f:
            f.write(briefing_text)

        # Also save structured data alongside for machine parsing
        json_file = os.path.join(reports_dir, f"briefing_{run_date}.json")
        briefing_json = {
            "date": run_date,
            "generated_at": datetime.now().isoformat(),
            "provider": "analyst_brain",
            "scan_results_count": len(scan_results) if scan_results else 0,
            "correlation": correlation_analysis,
            "field_results": {
                pid: {
                    "fruitful": sum(1 for s in (st or {}).get("seeds", []) if s.get("status") == "Fruitful"),
                    "barren": sum(1 for s in (st or {}).get("seeds", []) if s.get("status") == "Barren"),
                    "total": len((st or {}).get("seeds", [])),
                }
                for pid, st in (field_results or {}).items()
            },
            "cross_field_entities": cross_field_entities,
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(briefing_json, f, indent=2)

        print(briefing_text)
        print(f"\n  Briefing saved to: {briefing_file}")
        print(f"  JSON saved to: {json_file}")

        return briefing_text, briefing_file

    except Exception as e:
        print(f"  Analyst: ERROR writing briefing — {e}")
        # Fall back to mechanical briefing
        fallback = f"# BRIEFING — {run_date}\n\nAnalyst synthesis failed: {e}\n\n"
        fallback += field_results_text
        fallback_file = os.path.join(reports_dir, f"briefing_{run_date}_fallback.txt")
        with open(fallback_file, "w") as f:
            f.write(fallback)
        return fallback, fallback_file
