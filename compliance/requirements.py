"""
Compliance requirements for Venetian Wheat.

Structured to match auto-agent's ComplianceRequirement schema
so requirements can be synced to the garden-level tracker.

Two layers:
  vw-claude-*  — Claude/Anthropic TOS (garden-wide risk)
  vw-ops-*     — Operational compliance (intelligence collection)
"""

REQUIREMENTS = [
    # =====================================================================
    # LAYER 1: Claude TOS (garden-wide — failure here threatens everything)
    # =====================================================================
    {
        "id": "vw-claude-1",
        "project_id": "venetian-wheat",
        "domain": "regulatory",
        "title": "AI-generated analysis disclosed",
        "description": (
            "When Claude Sonnet/Opus generates field analysis, channel scans, "
            "or escalation recommendations, outputs must be identifiable as "
            "AI-generated. Stakeholders must know the source."
        ),
        "priority": 8,
        "check_method": "manual",
        "check_target": None,
        "citation": "Anthropic Acceptable Use Policy — AI disclosure",
    },
    {
        "id": "vw-claude-2",
        "project_id": "venetian-wheat",
        "domain": "regulatory",
        "title": "Not positioned as legal authority",
        "description": (
            "Escalation notices are informational, not legal advice. "
            "Civil escalation recommendations do not constitute legal "
            "counsel or official regulatory filings."
        ),
        "priority": 9,
        "check_method": "manual",
        "check_target": None,
        "citation": "Anthropic AUP — Professional Advice",
    },

    # =====================================================================
    # LAYER 2: Operational (intelligence collection and reporting)
    # =====================================================================
    {
        "id": "vw-ops-1",
        "project_id": "venetian-wheat",
        "domain": "security",
        "title": "No secrets in version control",
        "description": (
            "API keys for channel integrations stored in .env only. "
            ".gitignore excludes all secret-containing files."
        ),
        "priority": 9,
        "check_method": "file_exists",
        "check_target": ".gitignore",
        "citation": "Eric Zosso Internal Security — Credential Management",
    },
    {
        "id": "vw-ops-2",
        "project_id": "venetian-wheat",
        "domain": "operational",
        "title": "Intelligence data handled responsibly",
        "description": (
            "Field analysis and channel scan data stored locally. "
            "No external database exposure. Data used for community "
            "safety monitoring, not surveillance."
        ),
        "priority": 7,
        "check_method": "manual",
        "check_target": None,
        "citation": "Responsible data handling for civic intelligence",
    },
    {
        "id": "vw-ops-3",
        "project_id": "venetian-wheat",
        "domain": "operational",
        "title": "Escalation follows subsidiarity",
        "description": (
            "Civil escalation paths respect institutional hierarchy. "
            "Local channels first, then state, then federal. No "
            "skip-level escalation without documented justification."
        ),
        "priority": 6,
        "check_method": "manual",
        "check_target": None,
        "citation": "Subsidiarity principle — civic engagement",
    },
]
