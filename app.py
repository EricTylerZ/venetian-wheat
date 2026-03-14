# app.py
from flask import Flask, request, render_template, jsonify, Response, redirect, url_for
from wheat.field_manager import FieldManager
from wheat.paths import load_config, load_projects, save_projects, load_project_config
from wheat.channels import load_channels, get_channels_for_field, process_intake
from wheat.escalation import (
    init_escalation_db, create_case, escalate_case, resolve_case,
    get_cases_by_field, get_escalation_ready, get_cross_field_entities,
    daily_escalation_check, get_all_cases, get_case_history,
    get_stage_distribution, get_field_list, STAGES,
)
import sqlite3
import os
import json
import threading
import time
from datetime import datetime, date
import shutil
import re
from tools.stewards_map import get_stewards_map, get_map_as_string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db")


# ---------------------------------------------------------------------------
# Thread-safe state registry — one entry per active project
# ---------------------------------------------------------------------------

class FieldState:
    """Thread-safe registry of per-project field managers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._projects = {}  # project_id -> {"manager", "sowing", "tending_thread"}

    def _ensure_project(self, project_id):
        """Get or create state for a project. Must be called under _lock."""
        if project_id not in self._projects:
            config = load_project_config(project_id)
            self._projects[project_id] = {
                "manager": FieldManager(project_id=project_id, config=config),
                "sowing": False,
                "tending_thread": None,
            }
        return self._projects[project_id]

    def manager(self, project_id):
        with self._lock:
            return self._ensure_project(project_id)["manager"]

    def try_start_sowing(self, project_id):
        with self._lock:
            p = self._ensure_project(project_id)
            if p["sowing"]:
                return False
            p["sowing"] = True
            return True

    def finish_sowing(self, project_id):
        with self._lock:
            if project_id in self._projects:
                self._projects[project_id]["sowing"] = False

    def reset_manager(self, project_id):
        with self._lock:
            config = load_project_config(project_id)
            self._projects[project_id] = {
                "manager": FieldManager(project_id=project_id, config=config),
                "sowing": False,
                "tending_thread": None,
            }

    def ensure_tending(self, project_id):
        with self._lock:
            p = self._ensure_project(project_id)
            if p["tending_thread"] and p["tending_thread"].is_alive():
                return
            t = threading.Thread(target=p["manager"].tend_field, daemon=True)
            p["tending_thread"] = t
            t.start()

    def clear(self, project_id):
        with self._lock:
            if project_id in self._projects:
                self._projects[project_id]["manager"].seeds = []
                self._projects[project_id]["tending_thread"] = None

    def active_projects(self):
        """Return list of project_ids that have a running tending thread."""
        with self._lock:
            return [pid for pid, p in self._projects.items()
                    if p["tending_thread"] and p["tending_thread"].is_alive()]


state = FieldState()


# ---------------------------------------------------------------------------
# Database setup with migration
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        log TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        project_id TEXT DEFAULT 'default'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        seed_id TEXT,
        task TEXT,
        status TEXT,
        output TEXT,
        code_file TEXT,
        test_result TEXT,
        project_id TEXT DEFAULT 'default',
        FOREIGN KEY (run_id) REFERENCES runs(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed_id INTEGER,
        request_file TEXT,
        response_file TEXT,
        FOREIGN KEY (seed_id) REFERENCES seeds(id)
    )''')

    # Migration: add project_id to existing tables if missing
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    if "project_id" not in existing_cols:
        c.execute("ALTER TABLE runs ADD COLUMN project_id TEXT DEFAULT 'default'")
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(seeds)").fetchall()}
    if "project_id" not in existing_cols:
        c.execute("ALTER TABLE seeds ADD COLUMN project_id TEXT DEFAULT 'default'")

    conn.commit()
    conn.close()


init_db()
init_escalation_db()

REPORTS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "reports")
BRIEFINGS_DIR = os.path.join(REPORTS_DIR, "briefings")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_latest_run(project_id="default"):
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, log FROM runs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,))
    run = c.fetchone()
    if run:
        run_id, timestamp, log = run
        c.execute("SELECT seed_id, task, status, output, code_file, test_result FROM seeds WHERE run_id = ? AND project_id = ?", (run_id, project_id))
        seeds = c.fetchall()
        conn.close()
        return log, {"timestamp": timestamp, "seeds": {row[0]: {"task": row[1], "status": row[2], "output": json.loads(row[3]) if row[3] else [], "code_file": row[4], "test_result": row[5]} for row in seeds}}
    conn.close()
    return None, None


# ---------------------------------------------------------------------------
# Routes: Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    projects = load_projects()
    active = state.active_projects()
    channels = load_channels()

    # Enrich fields with latest run info and channel counts
    field_list = []
    for pid, pdata in projects.items():
        log, status_data = get_latest_run(pid)
        seeds = status_data["seeds"] if status_data else {}
        fruitful = sum(1 for s in seeds.values() if s["status"] == "Fruitful")
        barren = sum(1 for s in seeds.values() if s["status"] == "Barren")
        growing = sum(1 for s in seeds.values() if s["status"] in ("Growing", "Repairing"))

        field_channels = get_channels_for_field(pid)

        field_list.append({
            "id": pid,
            "name": pdata.get("name", pid),
            "description": pdata.get("description", ""),
            "active": pid in active,
            "fruitful": fruitful,
            "barren": barren,
            "growing": growing,
            "total_seeds": len(seeds),
            "channel_count": len(field_channels),
        })

    # Channel list for channels tab
    channel_list = [
        {
            "id": cid,
            "name": cdata.get("name", cid),
            "channel_type": cdata.get("channel_type", ""),
            "frequency": cdata.get("frequency", "daily"),
            "fields": cdata.get("fields", []),
        }
        for cid, cdata in channels.items()
    ]

    # Cases
    all_cases = []
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute("SELECT * FROM cases WHERE resolved_at IS NULL ORDER BY severity DESC, created_at")
    columns = [desc[0] for desc in c.description] if c.description else []
    all_cases = [dict(zip(columns, row)) for row in c.fetchall()] if columns else []
    conn.close()

    escalation_ready_cases = get_escalation_ready()
    cross_field = get_cross_field_entities()

    # Latest briefing
    latest_briefing = None
    if os.path.exists(BRIEFINGS_DIR):
        briefing_files = sorted(
            [f for f in os.listdir(BRIEFINGS_DIR) if f.endswith(".txt")],
            reverse=True,
        )
        if briefing_files:
            with open(os.path.join(BRIEFINGS_DIR, briefing_files[0]), "r") as f:
                latest_briefing = f.read()

    # Today's community reports
    intake_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "intake")
    today_intake = 0
    today_str = date.today().strftime("%Y%m%d")
    if os.path.exists(intake_dir):
        today_intake = sum(
            1 for f in os.listdir(intake_dir)
            if f.startswith("report_") and f.endswith(".json") and today_str in f
        )

    return render_template(
        "dashboard.html",
        fields=field_list,
        channels=channel_list,
        cases=all_cases,
        active_cases=len(all_cases),
        escalation_ready=len(escalation_ready_cases),
        cross_field_entities=cross_field,
        latest_briefing=latest_briefing,
        today_intake=today_intake,
    )


# ---------------------------------------------------------------------------
# Routes: Project-scoped
# ---------------------------------------------------------------------------

@app.route("/projects/<project_id>")
def project_field(project_id):
    projects = load_projects()
    if project_id not in projects:
        return "Project not found", 404
    log, status_data = get_latest_run(project_id)
    log = log or "Field not yet sowed."
    status = status_data["seeds"] if status_data else {}
    config = load_project_config(project_id)
    project = projects[project_id]
    field_channels = get_channels_for_field(project_id)
    field_cases = get_cases_by_field(project_id)
    return render_template("field.html",
                           log=log, status=status,
                           config=config,
                           field_config=project,
                           field_channels=field_channels,
                           field_cases=field_cases,
                           config_json=json.dumps(project, indent=2),
                           project_id=project_id,
                           project_name=project.get("name", project_id),
                           active=project_id in state.active_projects())


@app.route("/projects/<project_id>/sow", methods=["POST"])
def project_sow(project_id):
    if not state.try_start_sowing(project_id):
        return jsonify({"message": "Sowing already in progress."}), 400
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance") or "No user input—sow tasks to improve wheat seeds."

        get_stewards_map(include_params=True, include_descriptions=True)
        stewards_map_str = get_map_as_string(include_params=True, include_descriptions=True)

        config = load_project_config(project_id)

        strategist_prompt = config["strategist_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            seeds_per_run=config["seeds_per_run"],
            guidance=guidance
        )
        coder_prompt_template = config["coder_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            task="{task}"
        )

        state.reset_manager(project_id)
        state.manager(project_id).sow_field(guidance, strategist_prompt=strategist_prompt, coder_prompt=coder_prompt_template)
        state.ensure_tending(project_id)
        return jsonify({"message": f"Seeds sowed for {project_id} with guidance: '{guidance}'"})
    except Exception as e:
        print(f"[{project_id}] Sowing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Sowing failed: {str(e)}"}), 500
    finally:
        state.finish_sowing(project_id)


@app.route("/projects/<project_id>/stream")
def project_stream(project_id):
    def event_stream():
        while True:
            log, status_data = get_latest_run(project_id)
            log = log or "Field not yet sowed."
            status = status_data["seeds"] if status_data else {}
            html = render_template("partials/field_status.html", log=log, status=status)
            escaped = html.replace("\n", "\ndata: ")
            yield f"data: {escaped}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/projects/<project_id>/pause")
def project_pause(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    open(os.path.join(wheat_dir, f"pause_{project_id}.txt"), "w").close()
    return "Paused."


@app.route("/projects/<project_id>/resume")
def project_resume(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, f"pause_{project_id}.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.ensure_tending(project_id)
    return "Resumed."


@app.route("/projects/<project_id>/clear")
def project_clear(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, f"pause_{project_id}.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.clear(project_id)
    return "Cleared experiments."


@app.route("/projects/<project_id>/success")
def project_success(project_id):
    log, status_data = get_latest_run(project_id)
    summary = "No successful seeds found."
    if status_data:
        successful = [f"Seed {sid}: {info['task']} - {info['output'][-1] if info['output'] else 'No output'}"
                      for sid, info in status_data["seeds"].items() if info["status"] == "Fruitful"]
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_seeds": summary})


@app.route("/projects/<project_id>/integrate", methods=["POST"])
def project_integrate(project_id):
    from wheat.paths import project_dir
    pdir = project_dir(project_id)
    success_dir = os.path.join(pdir, "successful_seeds")
    helpers_dir = os.path.join(pdir, "helpers")
    log, status_data = get_latest_run(project_id)
    integrated = []
    integrated_info = {}

    registry_file = os.path.join(helpers_dir, "script_registry.json")
    if os.path.exists(registry_file):
        with open(registry_file, "r", encoding="utf-8") as f:
            integrated_info = json.load(f)

    if status_data:
        os.makedirs(success_dir, exist_ok=True)
        os.makedirs(helpers_dir, exist_ok=True)
        for seed_id, info in status_data["seeds"].items():
            if info["status"] == "Fruitful" and info["code_file"] and os.path.exists(info["code_file"]):
                filename = f"seed_{seed_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                shutil.copy(info["code_file"], os.path.join(success_dir, filename))
                shutil.copy(info["code_file"], os.path.join(helpers_dir, filename))
                integrated.append(filename)
                with open(info["code_file"], "r", encoding="utf-8") as f:
                    content = f.read()
                    func_match = re.search(r'def (\w+)\((.*?)\):', content)
                    func_name = func_match.group(1) if func_match else "unknown"
                    params = func_match.group(2).strip() if func_match else ""
                    purpose_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                    purpose = purpose_match.group(1).strip() if purpose_match else "Unknown"
                integrated_info[filename] = {"function": func_name, "purpose": purpose, "parameters": params}
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(integrated_info, f, indent=2)

    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} seeds."})


@app.route("/projects/<project_id>/config", methods=["POST"])
def project_update_config(project_id):
    try:
        new_settings = request.get_json()
        projects = load_projects()
        if project_id not in projects:
            return jsonify({"message": "Project not found"}), 404
        # Merge new settings into project
        projects[project_id].update(new_settings)
        save_projects(projects)
        state.reset_manager(project_id)
        return jsonify({"message": f"Config updated for {project_id}."})
    except Exception as e:
        return jsonify({"message": f"Failed: {str(e)}"}), 400


# ---------------------------------------------------------------------------
# Routes: Project management
# ---------------------------------------------------------------------------

@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    if request.method == "GET":
        return render_template("new_project.html")

    data = request.get_json() or request.form.to_dict()
    project_id = data.get("project_id", "").strip().lower().replace(" ", "_")
    if not project_id or project_id == "new":
        return jsonify({"message": "Invalid project ID"}), 400

    projects = load_projects()
    if project_id in projects:
        return jsonify({"message": f"Project '{project_id}' already exists"}), 400

    project = {
        "name": data.get("name", project_id),
        "description": data.get("description", ""),
        "active": True,
        "llm_api": data.get("llm_api", "venice"),
        "models": {
            "strategist": data.get("model_strategist", ""),
            "coder": data.get("model_coder", ""),
            "rescuer": data.get("model_rescuer", ""),
        },
        "seeds_per_run": int(data.get("seeds_per_run", 3)),
    }
    # Only include non-empty model entries (fall back to base config)
    project["models"] = {k: v for k, v in project["models"].items() if v}
    if data.get("strategist_prompt"):
        project["strategist_prompt"] = data["strategist_prompt"]
    if data.get("coder_prompt"):
        project["coder_prompt"] = data["coder_prompt"]

    projects[project_id] = project
    save_projects(projects)
    return jsonify({"message": f"Project '{project_id}' created", "redirect": f"/projects/{project_id}"})


@app.route("/models")
def get_models():
    from wheat.sower import Sower
    sower = Sower()
    models = sower.get_available_models()
    return jsonify({"models": models})


# ---------------------------------------------------------------------------
# API Routes: Intelligence Operations
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Daily cycle — run with live log streaming
# ---------------------------------------------------------------------------

CYCLE_LOG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "reports", "cycle_logs")
_cycle_state = {"running": False, "log_file": None, "started": None, "pid": None}


@app.route("/api/daily-cycle", methods=["POST"])
def api_daily_cycle():
    """Trigger a full daily cycle in a background thread with log capture."""
    if _cycle_state["running"]:
        return jsonify({"message": "Daily cycle already running.", "status": "running"}), 409

    os.makedirs(CYCLE_LOG_DIR, exist_ok=True)
    log_file = os.path.join(CYCLE_LOG_DIR, f"cycle_{date.today().isoformat()}.log")
    _cycle_state["log_file"] = log_file
    _cycle_state["started"] = datetime.now().isoformat()
    _cycle_state["running"] = True

    def run_cycle():
        import subprocess
        try:
            with open(log_file, "w") as lf:
                proc = subprocess.Popen(
                    ["python", "-u", "daily_runner.py"],
                    cwd=os.path.dirname(os.path.realpath(__file__)),
                    stdout=lf, stderr=subprocess.STDOUT,
                    text=True,
                )
                _cycle_state["pid"] = proc.pid
                proc.wait()
        finally:
            _cycle_state["running"] = False
            _cycle_state["pid"] = None

    t = threading.Thread(target=run_cycle, daemon=True)
    t.start()
    return jsonify({"message": "Daily cycle started. Open the log panel to watch progress.", "status": "started"})


@app.route("/api/daily-cycle/status")
def api_daily_cycle_status():
    """Check daily cycle status."""
    return jsonify({
        "running": _cycle_state["running"],
        "started": _cycle_state["started"],
        "log_file": _cycle_state["log_file"],
    })


@app.route("/api/daily-cycle/stream")
def api_daily_cycle_stream():
    """SSE stream of the daily cycle log file."""
    log_file = _cycle_state["log_file"]

    def event_stream():
        if not log_file or not os.path.exists(log_file):
            yield "data: Waiting for cycle to start...\n\n"

        # Wait for file to appear
        for _ in range(10):
            if log_file and os.path.exists(log_file):
                break
            time.sleep(1)
            yield "data: .\n\n"

        if not log_file or not os.path.exists(log_file):
            yield "data: [No log file found]\n\n"
            return

        with open(log_file, "r") as f:
            while True:
                line = f.readline()
                if line:
                    # Escape for SSE
                    escaped = line.rstrip("\n").replace("\n", " ")
                    yield f"data: {escaped}\n\n"
                elif not _cycle_state["running"]:
                    yield "data: \n\ndata: === CYCLE COMPLETE ===\n\n"
                    return
                else:
                    time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/scan", methods=["POST"])
@app.route("/api/grok-scan", methods=["POST"])  # legacy alias
def api_scan():
    """Trigger channel scans (Claude Sonnet)."""
    channel_filter = request.args.get("channel")
    field_filter = request.args.get("field")

    def run_scan():
        from wheat.scan_tasks import run_daily_scans
        if field_filter:
            field_channels = get_channels_for_field(field_filter)
            for cid in field_channels:
                run_daily_scans(channel_filter=cid)
        else:
            run_daily_scans(channel_filter=channel_filter)

    t = threading.Thread(target=run_scan, daemon=True)
    t.start()
    target = channel_filter or field_filter or "all channels"
    return jsonify({"message": f"Channel scan started for {target}."})


@app.route("/api/briefing")
def api_briefing():
    """Generate or retrieve the latest briefing."""
    # Check for existing briefing
    os.makedirs(BRIEFINGS_DIR, exist_ok=True)
    today = date.today().isoformat()
    today_file = os.path.join(BRIEFINGS_DIR, f"briefing_{today}.txt")

    if os.path.exists(today_file):
        with open(today_file, "r") as f:
            return jsonify({"briefing": f.read(), "date": today})

    # Generate from current data
    projects = load_projects()
    lines = [
        f"DAILY INTELLIGENCE BRIEFING — {today}",
        f"Venetian Wheat — Englewood, CO",
        "=" * 50,
        "",
    ]

    total_cases = 0
    for pid, pdata in projects.items():
        log, status_data = get_latest_run(pid)
        seeds = status_data["seeds"] if status_data else {}
        cases = get_cases_by_field(pid)
        total_cases += len(cases)
        fruitful = sum(1 for s in seeds.values() if s["status"] == "Fruitful")
        lines.append(f"{pid}: {fruitful} fruitful seeds, {len(cases)} active cases")

    lines.append("")
    lines.append(f"Total active cases: {total_cases}")

    esc = daily_escalation_check()
    if esc:
        lines.append("")
        lines.append(esc)

    briefing = "\n".join(lines)

    with open(today_file, "w") as f:
        f.write(briefing)

    return jsonify({"briefing": briefing, "date": today})


@app.route("/api/cases/<int:case_id>/escalate", methods=["POST"])
def api_escalate_case(case_id):
    """Escalate a case to the next stage."""
    data = request.get_json() or {}
    reason = data.get("reason", "Manual escalation from dashboard")
    try:
        escalate_case(case_id, reason=reason)
        return jsonify({"message": f"Case #{case_id} escalated."})
    except ValueError as e:
        return jsonify({"message": str(e)}), 404


@app.route("/api/cases/<int:case_id>/resolve", methods=["POST"])
def api_resolve_case(case_id):
    """Resolve a case."""
    data = request.get_json() or {}
    resolution = data.get("resolution", "Compliance achieved")
    try:
        resolve_case(case_id, resolution=resolution)
        return jsonify({"message": f"Case #{case_id} resolved: {resolution}"})
    except ValueError as e:
        return jsonify({"message": str(e)}), 404


@app.route("/api/intake", methods=["POST"])
def api_intake():
    """Accept a community report."""
    data = request.get_json()
    if not data or not data.get("description"):
        return jsonify({"message": "Description is required."}), 400
    result = process_intake(data)
    return jsonify({
        "message": f"Report received — Case #{result['case_id']} created in {result['target_field']}. Thank you.",
        "target_field": result["target_field"],
        "report_file": result["report_file"],
        "case_id": result["case_id"],
    })


@app.route("/escalation")
def escalation_dashboard():
    """Escalation status dashboard — case overview by stage, field, and readiness."""
    filter_field = request.args.get("field")
    show_resolved = request.args.get("resolved") == "1"

    if filter_field:
        cases = get_cases_by_field(filter_field, active_only=not show_resolved)
    else:
        cases = get_all_cases(active_only=not show_resolved)

    stage_dist = get_stage_distribution(active_only=not show_resolved)
    ready = get_escalation_ready()
    cross_field = get_cross_field_entities()
    fields = get_field_list()

    return render_template(
        "escalation.html",
        cases=cases,
        stage_distribution=stage_dist,
        stages=STAGES,
        escalation_ready=ready,
        cross_field_entities=cross_field,
        fields=fields,
        filter_field=filter_field,
        show_resolved=show_resolved,
        total_active=sum(1 for c in cases if not c.get("resolved_at")),
    )


@app.route("/api/escalation")
def api_escalation():
    """JSON API for escalation dashboard data."""
    cases = get_all_cases(active_only=True)
    return jsonify({
        "cases": cases,
        "stage_distribution": get_stage_distribution(),
        "escalation_ready": get_escalation_ready(),
        "cross_field_entities": get_cross_field_entities(),
        "fields": get_field_list(),
        "total_active": len(cases),
    })


@app.route("/api/cases/<int:case_id>/history")
def api_case_history(case_id):
    """Get escalation history for a case."""
    return jsonify({"history": get_case_history(case_id)})


if __name__ == "__main__":
    app.run(port=5001, threaded=True)
