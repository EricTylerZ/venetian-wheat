"""
Daily Intake Processor — batch processing of pending reports and scan signals.

The intake pipeline connects community reports and channel scans to the
escalation engine. Runs as part of the daily cycle:

  1. process_pending_reports() — Find unprocessed community reports, validate,
     route to fields, create/update escalation cases
  2. process_scan_results()   — Read channel scan output, extract signals,
     create cases for new findings
  3. run_daily_intake()       — Orchestrate the full pipeline, return summary
"""

import json
import os
from datetime import datetime

from wheat.channels import INTAKE_DIR, load_channels, get_default_channels
from wheat.escalation import create_case, init_escalation_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SCANS_DIR = os.path.join(INTAKE_DIR, "scans")

REQUIRED_REPORT_FIELDS = {"category", "entity", "description"}

# Same mapping as channels.py process_intake — canonical category→field routing
CATEGORY_TO_FIELD = {
    "dangerous_driving": "fleet_compliance",
    "commercial_vehicle": "fleet_compliance",
    "tow_company": "tow_companies",
    "used_car_dealer": "used_car_dealers",
    "auto_repair": "auto_repair",
    "noise_exhaust": "exhaust_noise",
    "school_zone": "school_zone_safety",
    "pedestrian_cyclist": "pedestrian_cyclist",
    "parking_booting": "parking_booting",
    "window_tint": "window_tint",
    "registration_plates": "title_registration",
    "emissions": "emissions_environmental",
    "intersection_road": "road_intersection_safety",
    "insurance": "auto_insurance",
    "dealer_financing": "dealer_financing",
    "rideshare_delivery": "rideshare_delivery",
}


def validate_report(report_data):
    """
    Validate a community report has required fields.
    Returns (is_valid, errors) tuple.
    """
    errors = []
    missing = REQUIRED_REPORT_FIELDS - set(report_data.keys())
    if missing:
        errors.append(f"Missing required fields: {', '.join(sorted(missing))}")

    if not report_data.get("entity", "").strip():
        errors.append("Entity name is empty")

    if not report_data.get("description", "").strip():
        errors.append("Description is empty")

    category = report_data.get("category", "")
    if category and category not in CATEGORY_TO_FIELD:
        errors.append(f"Unknown category: {category}")

    severity = report_data.get("severity")
    if severity is not None:
        try:
            sev = int(severity)
            if sev < 1 or sev > 10:
                errors.append(f"Severity must be 1-10, got {sev}")
        except (ValueError, TypeError):
            errors.append(f"Severity must be an integer, got {severity!r}")

    return (len(errors) == 0, errors)


def _load_report(filepath):
    """Load and parse a single report file. Returns (data, error)."""
    try:
        with open(filepath, "r") as f:
            return json.load(f), None
    except (json.JSONDecodeError, OSError) as e:
        return None, str(e)


def _save_report(filepath, data):
    """Write report data back to file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def get_pending_reports():
    """
    Find all intake reports with status 'pending'.
    Returns list of (filepath, report_data) tuples.
    """
    if not os.path.isdir(INTAKE_DIR):
        return []

    pending = []
    for fname in sorted(os.listdir(INTAKE_DIR)):
        if not fname.startswith("report_") or not fname.endswith(".json"):
            continue
        filepath = os.path.join(INTAKE_DIR, fname)
        if not os.path.isfile(filepath):
            continue
        data, error = _load_report(filepath)
        if error:
            continue
        if data.get("status") == "pending":
            pending.append((filepath, data))
    return pending


def process_pending_reports():
    """
    Process all pending community reports.

    For each pending report:
      1. Validate structure
      2. Route to field via category mapping
      3. Create escalation case (if not already created)
      4. Mark as 'processed' or 'invalid'

    Returns summary dict with counts and details.
    """
    pending = get_pending_reports()
    results = {
        "processed": 0,
        "invalid": 0,
        "skipped": 0,
        "errors": [],
        "cases_created": [],
    }

    if not pending:
        return results

    init_escalation_db()

    for filepath, report in pending:
        # Skip if already has a case_id (was processed by process_intake)
        if report.get("case_id"):
            report["status"] = "processed"
            _save_report(filepath, report)
            results["skipped"] += 1
            continue

        is_valid, errors = validate_report(report)
        if not is_valid:
            report["status"] = "invalid"
            report["validation_errors"] = errors
            _save_report(filepath, report)
            results["invalid"] += 1
            results["errors"].append({
                "file": os.path.basename(filepath),
                "errors": errors,
            })
            continue

        # Route to field
        category = report.get("category", "")
        target_field = CATEGORY_TO_FIELD.get(category, "fleet_compliance")

        # Build case issue
        entity = report.get("entity", "").strip() or "Unknown Entity"
        description = report.get("description", "")
        location = report.get("location", "")
        severity = int(report.get("severity", 1))
        case_issue = f"[{location}] {description}" if location else description

        # Create escalation case
        case_id = create_case(
            field=target_field,
            entity=entity,
            issue=case_issue,
            severity=severity,
            source="daily_intake",
            notes=f"Batch processed {datetime.now().isoformat()}",
        )

        report["status"] = "processed"
        report["case_id"] = case_id
        report["target_field"] = target_field
        report["processed_at"] = datetime.now().isoformat()
        _save_report(filepath, report)

        results["processed"] += 1
        results["cases_created"].append({
            "case_id": case_id,
            "entity": entity,
            "field": target_field,
            "severity": severity,
        })

    return results


def get_unprocessed_scans():
    """
    Find scan result files that haven't been processed yet.
    A scan is considered processed if it has a 'processed_at' field.
    Returns list of (filepath, scan_data) tuples.
    """
    if not os.path.isdir(SCANS_DIR):
        return []

    unprocessed = []
    for fname in sorted(os.listdir(SCANS_DIR)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(SCANS_DIR, fname)
        if not os.path.isfile(filepath):
            continue
        data, error = _load_report(filepath)
        if error:
            continue
        if not data.get("processed_at"):
            unprocessed.append((filepath, data))
    return unprocessed


def process_scan_results():
    """
    Process channel scan results into escalation cases.

    Each scan result may contain signals — actionable findings from
    channel monitoring. Each signal with an entity creates a case.

    Returns summary dict.
    """
    scans = get_unprocessed_scans()
    results = {
        "scans_processed": 0,
        "signals_found": 0,
        "cases_created": [],
    }

    if not scans:
        return results

    init_escalation_db()

    for filepath, scan in scans:
        signals = scan.get("signals", [])
        channel_id = scan.get("channel_id", "unknown")
        target_fields = scan.get("target_fields", [])
        primary_field = target_fields[0] if target_fields else "fleet_compliance"

        for signal in signals:
            entity = signal.get("entity", "").strip()
            if not entity:
                continue

            issue = signal.get("description", signal.get("summary", ""))
            if not issue:
                continue

            severity = int(signal.get("severity", 1))
            field = signal.get("field", primary_field)

            case_id = create_case(
                field=field,
                entity=entity,
                issue=issue,
                severity=severity,
                source=f"scan:{channel_id}",
                notes=f"From channel scan {scan.get('scanned_at', '')}",
            )

            results["signals_found"] += 1
            results["cases_created"].append({
                "case_id": case_id,
                "entity": entity,
                "field": field,
                "channel": channel_id,
            })

        # Mark scan as processed
        scan["processed_at"] = datetime.now().isoformat()
        _save_report(filepath, scan)
        results["scans_processed"] += 1

    return results


def intake_summary(report_results, scan_results):
    """Format a human-readable summary of intake processing."""
    lines = []
    lines.append(f"Daily Intake Summary — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    lines.append(f"\nCommunity Reports:")
    lines.append(f"  Processed: {report_results['processed']}")
    lines.append(f"  Invalid:   {report_results['invalid']}")
    lines.append(f"  Skipped:   {report_results['skipped']}")

    if report_results["cases_created"]:
        lines.append(f"  Cases created:")
        for c in report_results["cases_created"]:
            lines.append(f"    #{c['case_id']} {c['entity']} → {c['field']} (sev {c['severity']})")

    if report_results["errors"]:
        lines.append(f"  Validation errors:")
        for e in report_results["errors"]:
            lines.append(f"    {e['file']}: {'; '.join(e['errors'])}")

    lines.append(f"\nChannel Scans:")
    lines.append(f"  Scans processed: {scan_results['scans_processed']}")
    lines.append(f"  Signals found:   {scan_results['signals_found']}")

    if scan_results["cases_created"]:
        lines.append(f"  Cases from signals:")
        for c in scan_results["cases_created"]:
            lines.append(f"    #{c['case_id']} {c['entity']} → {c['field']} (via {c['channel']})")

    total_cases = len(report_results["cases_created"]) + len(scan_results["cases_created"])
    lines.append(f"\nTotal new cases: {total_cases}")

    return "\n".join(lines)


def run_daily_intake():
    """
    Run the full daily intake pipeline.
    Returns (summary_text, report_results, scan_results).
    """
    report_results = process_pending_reports()
    scan_results = process_scan_results()
    summary = intake_summary(report_results, scan_results)
    return summary, report_results, scan_results
