"""
Escalation Engine — Subsidiarity-based escalation tracking.

Stages (cannot skip unless egregious):
  SEED      → Signal detected, record created
  SPROUT    → Validated against actual law/code, evidence attached
  NOTICE    → Friendly first contact: "Please fix this"
  VIRTUE    → Offered growth path (Stag Quest, community service, etc.)
  COMMUNITY → Peer/parish/org informed and asked to help
  DEMAND    → Formal demand letter with deadline
  CIVIL     → Filing prepared with full evidence chain
  HARVEST   → Resolution (compliance achieved OR damages awarded)

Each case tracks which stage it's at. The system will NOT skip stages
unless the violation is egregious (severity >= 5, imminent danger).
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "wheat.db")

STAGES = [
    "seed",
    "sprout",
    "notice",
    "virtue",
    "community",
    "demand",
    "civil",
    "harvest",
]

# Days to wait at each stage before eligible for escalation
STAGE_WAIT_DAYS = {
    "seed": 1,       # Validate quickly
    "sprout": 3,     # Give time to draft notice
    "notice": 14,    # Two weeks to respond to friendly notice
    "virtue": 30,    # Month to show improvement
    "community": 14, # Two weeks of community pressure
    "demand": 30,    # 30 days to comply with demand
    "civil": 90,     # Court timeline
}


def init_escalation_db():
    """Create the cases table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field TEXT NOT NULL,
        entity TEXT NOT NULL,
        issue TEXT NOT NULL,
        severity INTEGER DEFAULT 1,
        stage TEXT DEFAULT 'seed',
        evidence TEXT DEFAULT '[]',
        law_cited TEXT DEFAULT '',
        source TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        stage_entered_at TEXT NOT NULL,
        escalation_deadline TEXT,
        resolved_at TEXT,
        resolution TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS case_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        from_stage TEXT,
        to_stage TEXT NOT NULL,
        changed_at TEXT NOT NULL,
        reason TEXT DEFAULT '',
        FOREIGN KEY (case_id) REFERENCES cases(id)
    )""")

    conn.commit()
    conn.close()


def create_case(field, entity, issue, severity=1, law_cited="", source="", notes=""):
    """Create a new case at the SEED stage."""
    init_escalation_db()
    now = datetime.now().isoformat()
    deadline = (datetime.now() + timedelta(days=STAGE_WAIT_DAYS["seed"])).isoformat()

    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()

    # Check for existing open case with same entity and field
    c.execute(
        "SELECT id, stage FROM cases WHERE field = ? AND entity = ? AND resolved_at IS NULL",
        (field, entity),
    )
    existing = c.fetchone()
    if existing:
        # Add as additional evidence to existing case
        case_id = existing[0]
        c.execute("SELECT evidence FROM cases WHERE id = ?", (case_id,))
        evidence = json.loads(c.fetchone()[0])
        evidence.append({
            "date": now,
            "issue": issue,
            "severity": severity,
            "source": source,
            "law_cited": law_cited,
        })
        # Bump severity if new signal is higher
        c.execute(
            "UPDATE cases SET evidence = ?, severity = MAX(severity, ?), updated_at = ?, notes = notes || ? WHERE id = ?",
            (json.dumps(evidence), severity, now, f"\n[{now}] Additional signal: {issue}", case_id),
        )
        conn.commit()
        conn.close()
        print(f"  Added signal to existing case #{case_id} ({entity})")
        return case_id

    # New case
    c.execute(
        """INSERT INTO cases
        (field, entity, issue, severity, stage, evidence, law_cited, source, notes,
         created_at, updated_at, stage_entered_at, escalation_deadline)
        VALUES (?, ?, ?, ?, 'seed', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            field, entity, issue, severity,
            json.dumps([{"date": now, "issue": issue, "severity": severity, "source": source}]),
            law_cited, source, notes,
            now, now, now, deadline,
        ),
    )
    case_id = c.lastrowid

    c.execute(
        "INSERT INTO case_history (case_id, to_stage, changed_at, reason) VALUES (?, 'seed', ?, 'Initial signal detected')",
        (case_id, now),
    )

    conn.commit()
    conn.close()
    print(f"  Created new case #{case_id}: {entity} — {issue}")
    return case_id


def escalate_case(case_id, reason=""):
    """Move a case to the next escalation stage (respects subsidiarity)."""
    init_escalation_db()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()

    c.execute("SELECT stage, severity, entity, field FROM cases WHERE id = ?", (case_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Case #{case_id} not found")

    current_stage, severity, entity, field = row
    if current_stage == "harvest":
        conn.close()
        print(f"  Case #{case_id} already harvested.")
        return

    current_idx = STAGES.index(current_stage)
    next_stage = STAGES[current_idx + 1]
    now = datetime.now().isoformat()
    wait_days = STAGE_WAIT_DAYS.get(next_stage, 14)
    deadline = (datetime.now() + timedelta(days=wait_days)).isoformat()

    c.execute(
        """UPDATE cases SET stage = ?, updated_at = ?, stage_entered_at = ?,
           escalation_deadline = ? WHERE id = ?""",
        (next_stage, now, now, deadline, case_id),
    )

    c.execute(
        "INSERT INTO case_history (case_id, from_stage, to_stage, changed_at, reason) VALUES (?, ?, ?, ?, ?)",
        (case_id, current_stage, next_stage, now, reason),
    )

    conn.commit()
    conn.close()
    print(f"  Case #{case_id} ({entity}): {current_stage} → {next_stage}")


def resolve_case(case_id, resolution="Compliance achieved"):
    """Mark a case as resolved (harvested)."""
    init_escalation_db()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()

    c.execute("SELECT stage FROM cases WHERE id = ?", (case_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Case #{case_id} not found")

    c.execute(
        """UPDATE cases SET stage = 'harvest', resolved_at = ?, resolution = ?,
           updated_at = ? WHERE id = ?""",
        (now, resolution, now, case_id),
    )

    c.execute(
        "INSERT INTO case_history (case_id, from_stage, to_stage, changed_at, reason) VALUES (?, ?, 'harvest', ?, ?)",
        (case_id, row[0], now, resolution),
    )

    conn.commit()
    conn.close()
    print(f"  Case #{case_id} resolved: {resolution}")


def get_cases_by_field(field, active_only=True):
    """Get all cases for a field."""
    init_escalation_db()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    if active_only:
        c.execute(
            "SELECT * FROM cases WHERE field = ? AND resolved_at IS NULL ORDER BY severity DESC, created_at",
            (field,),
        )
    else:
        c.execute("SELECT * FROM cases WHERE field = ? ORDER BY created_at DESC", (field,))
    columns = [desc[0] for desc in c.description]
    cases = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return cases


def get_escalation_ready():
    """Find cases that have passed their escalation deadline and are ready to move up."""
    init_escalation_db()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute(
        "SELECT * FROM cases WHERE resolved_at IS NULL AND escalation_deadline < ? AND stage != 'harvest'",
        (now,),
    )
    columns = [desc[0] for desc in c.description]
    cases = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return cases


def get_cross_field_entities():
    """Find entities that appear in multiple fields — pattern detection."""
    init_escalation_db()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute("""
        SELECT entity, GROUP_CONCAT(DISTINCT field) as fields, COUNT(DISTINCT field) as field_count,
               MAX(severity) as max_severity
        FROM cases
        WHERE resolved_at IS NULL
        GROUP BY entity
        HAVING field_count > 1
        ORDER BY field_count DESC, max_severity DESC
    """)
    results = [
        {
            "entity": row[0],
            "fields": row[1].split(","),
            "field_count": row[2],
            "max_severity": row[3],
        }
        for row in c.fetchall()
    ]
    conn.close()
    return results


def daily_escalation_check():
    """Run during daily briefing — check for cases ready to escalate and cross-field patterns."""
    ready = get_escalation_ready()
    cross_field = get_cross_field_entities()

    report = []
    if ready:
        report.append(f"\nESCALATION READY — {len(ready)} cases past deadline:")
        for case in ready:
            report.append(
                f"  Case #{case['id']} ({case['entity']}): "
                f"{case['stage']} since {case['stage_entered_at'][:10]} — "
                f"Severity {case['severity']}, Field: {case['field']}"
            )

    if cross_field:
        report.append(f"\nCROSS-FIELD PATTERNS — {len(cross_field)} entities in multiple fields:")
        for entity in cross_field:
            report.append(
                f"  {entity['entity']}: {entity['field_count']} fields "
                f"({', '.join(entity['fields'])}) — Max severity: {entity['max_severity']}"
            )

    return "\n".join(report) if report else "No escalations or cross-field patterns detected."
